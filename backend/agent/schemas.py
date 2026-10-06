"""Contrat de données du Module 1.

Ces modèles sont LE contrat avec le frontend (JSON renvoyé par l'API) et avec
les autres modules (Module 2 NLP lira `saved_path`). On évite de les changer
sans prévenir l'équipe.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from .parsing import normalize_sender_rule, sender_matches


class CVMetadata(BaseModel):
    message_id: str
    attachment_id: str
    filename: str
    saved_path: str  # chemin local du CV téléchargé
    sender_name: str
    sender_email: str
    subject: str
    received_at: datetime
    size_bytes: int
    sha256: str
    downloaded_at: datetime
    source: Literal["email", "upload"] = "email"  # d'où vient le CV
    body_excerpt: str = ""  # début du texte du mail (vide pour un import manuel)


class SkippedAttachment(BaseModel):
    """Une pièce jointe écartée, avec la raison (pour comprendre pourquoi un CV n'apparaît pas)."""

    filename: str
    sender_email: str = ""
    subject: str = ""
    reason: str


class SyncResult(BaseModel):
    started_at: datetime
    since: datetime | None = None  # début de la fenêtre utilisée (None = tout l'historique)
    truncated: bool = False  # limite par synchro atteinte : relancer pour continuer
    finished_at: datetime | None = None
    scanned_messages: int = 0
    new_cvs: list[CVMetadata] = Field(default_factory=list)
    duplicates_skipped: int = 0
    invalid_skipped: int = 0
    ignored_count: int = 0  # écartés par les règles de l'utilisateur (voir la liste « Ignorés »)
    skipped: list[SkippedAttachment] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


EventType = Literal[
    "connected", "disconnected", "watch_started", "watch_stopped", "new_cvs", "sync_error"
]


class AgentEvent(BaseModel):
    id: int
    type: EventType
    at: datetime
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class SyncConfig(BaseModel):
    """Quels emails l'agent doit-il prendre en compte ? (modifiable à tout moment)"""

    # --- Quelle période ? ---
    mode: Literal["new_only", "last_days", "since_date", "all"] = "last_days"
    days: int = Field(30, ge=1, le=3650)  # utilisé si mode = last_days
    since_date: date | None = None  # utilisé si mode = since_date (minuit UTC)
    unread_only: bool = False  # réglage avancé : ne prendre que les emails NON LUS (risqué, voir warnings)

    # --- Quoi ignorer ? (rien n'est ignoré en silence : tout apparaît dans la liste « Ignorés ») ---
    ignore_automatic: bool = True  # newsletters, notifications, réponses automatiques
    ignored_senders: list[str] = Field(default_factory=list, max_length=200)  # adresses ou domaines
    allowed_extensions: list[Literal["pdf", "docx"]] = Field(default_factory=lambda: ["pdf", "docx"], min_length=1)
    max_attachment_mb: int = Field(20, ge=1, le=50)
    folder: str | None = None  # dossier (IMAP) ou étiquette (Gmail) à lire ; vide = boîte de réception / tout

    @field_validator("ignored_senders")
    @classmethod
    def _clean_senders(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            rule = normalize_sender_rule(value)
            if rule and len(rule) <= 254 and rule not in cleaned:
                cleaned.append(rule)
        return cleaned

    @field_validator("allowed_extensions")
    @classmethod
    def _dedupe_extensions(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))

    @field_validator("folder")
    @classmethod
    def _clean_folder(cls, value: str | None) -> str | None:
        return (value or "").strip() or None

    @model_validator(mode="after")
    def _check(self) -> "SyncConfig":
        if self.mode == "since_date" and self.since_date is None:
            raise ValueError("since_date est obligatoire quand mode = since_date")
        return self

    def sender_ignored(self, address: str) -> str | None:
        """Retourne la règle qui correspond à cet expéditeur, ou None."""
        return next((rule for rule in self.ignored_senders if sender_matches(rule, address)), None)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def profile(self) -> str:
        """Nom du profil prédéfini correspondant, ou « custom » si les réglages ont été personnalisés."""
        mine = self._editable()
        for name, info in PROFILES.items():
            if info.config._editable() == mine:
                return name
        return "custom"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def description(self) -> str:
        return self.describe()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def warnings(self) -> list[str]:
        """Avertissements à afficher à côté des réglages risqués."""
        notes = []
        if self.unread_only:
            notes.append(
                "Si le recruteur ouvre un email avant la prochaine synchronisation, il n'est plus « non lu » et sera manqué. "
                "À réserver aux cas particuliers."
            )
        if self.mode == "new_only":
            notes.append("Les emails déjà présents dans la boîte ne seront pas importés : seuls les futurs emails le seront.")
        if self.mode == "all":
            notes.append("Tout l'historique de la boîte sera lu : la première synchronisation peut être longue.")
        if not self.ignore_automatic:
            notes.append("Les emails automatiques ne sont pas filtrés : des pièces jointes sans rapport avec des candidatures peuvent être importées.")
        return notes

    def _editable(self) -> dict:
        return {name: getattr(self, name) for name in type(self).model_fields}

    def describe(self) -> str:
        if self.mode == "new_only":
            period = "uniquement les emails reçus à partir de l'activation (tout ce qui est plus ancien est ignoré)"
        elif self.mode == "last_days":
            period = f"les emails reçus durant les {self.days} derniers jours"
        elif self.mode == "since_date":
            period = f"les emails reçus depuis le {self.since_date:%d/%m/%Y}"
        else:
            period = "TOUS les emails de la boîte, sans limite de date (la première synchronisation peut être longue)"
        reading = "uniquement les emails NON LUS" if self.unread_only else "lus ou non lus"
        extras = []
        if self.ignore_automatic:
            extras.append("emails automatiques ignorés")
        if self.ignored_senders:
            extras.append(f"{len(self.ignored_senders)} expéditeur(s)/domaine(s) ignoré(s)")
        if self.folder:
            extras.append(f"dossier « {self.folder} » seulement")
        tail = f" ({', '.join(extras)})" if extras else ""
        return f"Récupère {period} — {reading}{tail}."


class ProfileInfo(BaseModel):
    name: str
    label: str
    description: str
    config: SyncConfig


PROFILES: dict[str, ProfileInfo] = {
    "prudent": ProfileInfo(
        name="prudent",
        label="Prudent (recommandé)",
        description="Reprend les 30 derniers jours puis suit les nouveaux emails ; ignore les emails automatiques.",
        config=SyncConfig(mode="last_days", days=30),
    ),
    "new_only": ProfileInfo(
        name="new_only",
        label="Nouveaux seulement",
        description="N'importe que les emails reçus à partir de maintenant ; l'existant est laissé de côté.",
        config=SyncConfig(mode="new_only"),
    ),
    "everything": ProfileInfo(
        name="everything",
        label="Tout importer",
        description="Lit tout l'historique de la boîte, sans filtrer les emails automatiques.",
        config=SyncConfig(mode="all", ignore_automatic=False, max_attachment_mb=50),
    ),
}


class GmailStatus(BaseModel):
    mode: Literal["fake", "real"]
    connected: bool
    provider: Literal["gmail_oauth", "imap", "fake"] | None = None
    account_email: str | None = None
    watching: bool
    poll_minutes: float
    last_sync_at: datetime | None = None
    total_cvs: int = 0
    sync_config: SyncConfig | None = None
    needs_setup: bool = False  # vrai tant que le recruteur n'a pas validé son choix de reprise (écran de démarrage)
    ignored_count: int = 0  # nombre d'emails dans la liste « Ignorés »


class RejectedFile(BaseModel):
    filename: str
    reason: str


class ImportResult(BaseModel):
    imported: list[CVMetadata] = Field(default_factory=list)
    duplicates_skipped: int = 0
    rejected: list[RejectedFile] = Field(default_factory=list)


class IgnoredItem(BaseModel):
    """Une pièce jointe écartée par les règles de l'utilisateur (jamais en silence)."""

    id: int
    filename: str
    sender_name: str
    sender_email: str
    subject: str
    received_at: datetime
    rule: Literal["automatic", "sender", "extension", "size"]
    reason: str  # phrase lisible : pourquoi c'est ignoré


class RecoverResult(BaseModel):
    imported: CVMetadata | None = None
    detail: str


class PreviewItem(BaseModel):
    sender_name: str
    sender_email: str
    subject: str
    received_at: datetime
    filename: str
    outcome: Literal["to_import", "already_imported", "ignored"]
    reason: str = ""


class PreviewResult(BaseModel):
    """Aperçu AVANT import : rien n'est téléchargé ni enregistré."""

    description: str  # la règle évaluée, en français
    since: datetime | None = None
    emails_with_cv: int = 0
    to_import: int = 0
    already_imported: int = 0
    ignored: int = 0
    ignored_by_rule: dict[str, int] = Field(default_factory=dict)
    truncated: bool = False  # il y a plus d'emails que la limite d'aperçu
    samples: list[PreviewItem] = Field(default_factory=list)
