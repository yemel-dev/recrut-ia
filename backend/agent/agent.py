"""Agent IA Gmail : surveille la boîte mail, télécharge les CV, évite les doublons.

Aucune dépendance à l'interface graphique. Le frontend (Electron) ou la CLI
pilotent l'agent ; l'agent publie des événements que n'importe qui peut lire.
"""
from __future__ import annotations

import hashlib
import logging
import threading
from collections import deque
from datetime import datetime, time as dtime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from .accounts import AccountStore, ImapConfig, default_secret_store
from .client import SUPPORTED_EXTENSIONS, FakeMailClient, GmailApiClient, MailClient, RawAttachment, RawMessage
from .errors import GmailAuthRequired, GmailModuleError, ImapAuthError, NotConnectedError
from .imap_client import ImapMailClient
from .importer import import_cv_files, looks_valid
from .ledger import Ledger
from .parsing import parse_sender, safe_filename
from .schemas import (
    PROFILES,
    AgentEvent,
    CVMetadata,
    GmailStatus,
    ImportResult,
    PreviewItem,
    PreviewResult,
    RecoverResult,
    SkippedAttachment,
    SyncConfig,
    SyncResult,
)
from .settings import GmailSettings, default_sync_config, load_settings

log = logging.getLogger("injara.gmail")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class GmailAgent:
    def __init__(
        self,
        *,
        ledger: Ledger,
        cv_dir: Path,
        mode: str = "real",
        client: MailClient | None = None,
        client_factory: Callable[[bool], MailClient] | None = None,
        disconnect_fn: Callable[[], None] | None = None,
        account_store: AccountStore | None = None,
        poll_minutes: float = 5.0,
        lookback_days: int = 30,
        max_results: int = 500,
        sync_config: SyncConfig | None = None,
    ) -> None:
        self.ledger = ledger
        self.cv_dir = Path(cv_dir)
        self.mode = mode
        self.poll_minutes = poll_minutes
        self.lookback_days = lookback_days
        self.max_results = max_results
        self.sync_config = sync_config or SyncConfig(days=lookback_days)
        stored = ledger.get_state("sync_config")  # la configuration choisie dans l'application l'emporte sur le .env
        if stored:
            try:
                self.sync_config = SyncConfig.model_validate_json(stored)
            except ValueError:
                log.warning("Configuration enregistrée illisible : valeurs par défaut utilisées.")
        self._client = client
        self._client_factory = client_factory
        self._disconnect_fn = disconnect_fn
        self.account_store = account_store
        self.provider: str | None = "fake" if mode == "fake" else None
        self.account_email: str | None = None
        self._sync_lock = threading.Lock()
        self._stop = threading.Event()
        self._stop.set()
        self._thread: threading.Thread | None = None
        self._events: deque[AgentEvent] = deque(maxlen=200)
        self._event_counter = 0
        self._event_lock = threading.Lock()
        self._listeners: list[Callable[[AgentEvent], None]] = []

    # ------------------------------------------------------------------ état
    @property
    def client(self) -> MailClient | None:
        return self._client

    @property
    def connected(self) -> bool:
        return self._client is not None

    @property
    def watching(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._stop.is_set()

    def status(self) -> GmailStatus:
        last = self.ledger.get_state(self._cursor_key)
        return GmailStatus(
            mode=self.mode,  # type: ignore[arg-type]
            connected=self.connected,
            provider=self.provider if self.connected else None,  # type: ignore[arg-type]
            account_email=self.account_email if self.connected else None,
            watching=self.watching,
            poll_minutes=self.poll_minutes,
            last_sync_at=datetime.fromisoformat(last) if last else None,
            sync_config=self.sync_config,
            needs_setup=self.connected and not self.ledger.get_state(self._setup_key),
            ignored_count=self.ledger.count_ignored(),
            total_cvs=self.ledger.count_cvs(),
        )

    # ------------------------------------------------------------ événements
    def subscribe(self, listener: Callable[[AgentEvent], None]) -> None:
        """Permet à l'application principale d'être notifiée ('X nouveaux CV récupérés')."""
        self._listeners.append(listener)

    def _emit(self, type_: str, message: str, data: dict[str, Any] | None = None) -> AgentEvent:
        with self._event_lock:
            self._event_counter += 1
            event = AgentEvent(id=self._event_counter, type=type_, at=_now(), message=message, data=data or {})  # type: ignore[arg-type]
            self._events.append(event)
        for listener in list(self._listeners):
            try:
                listener(event)
            except Exception:
                log.exception("Un abonné aux événements a échoué")
        return event

    def events_since(self, after_id: int = 0) -> list[AgentEvent]:
        with self._event_lock:
            return [e for e in self._events if e.id > after_id]

    # ------------------------------------------------------------ connexion
    @property
    def _cursor_key(self) -> str:
        """Chaque compte a son propre curseur : changer de boîte ne fait rien rater."""
        return f"last_sync_at:{self.provider or 'none'}:{self.account_email or ''}"

    def _attach(self, client: MailClient, provider: str, email: str) -> None:
        if self.watching:
            self.stop_watching()
        self._client = client
        self.provider = provider
        self.account_email = email or None
        if hasattr(client, "skip_filter"):
            client.skip_filter = self.ledger.has_message  # type: ignore[attr-defined]

    def try_restore(self) -> bool:
        """Au démarrage : reprend le compte déjà lié, sans ouvrir le navigateur ni redemander quoi que ce soit."""
        if self._client is not None:
            return True
        saved = self.account_store.load() if self.account_store else None
        try:
            if saved and saved.get("provider") == "imap":
                restored = self.account_store.load_imap()
                if restored:
                    cfg, password = restored
                    self._attach(ImapMailClient(cfg.host, cfg.email, password, cfg.port, cfg.folder), "imap", cfg.email)
                    self._emit("connected", f"Boîte {cfg.email} reconnectée (IMAP)")
            elif self._client_factory is not None:
                client = self._client_factory(False)
                self._attach(client, "gmail_oauth", getattr(client, "account_email", lambda: "")())
                self._emit("connected", "Session Gmail restaurée")
        except GmailAuthRequired:
            pass
        except Exception:
            log.exception("Restauration du compte impossible")
        return self.connected

    def connect(self) -> None:
        """Gmail / Google Workspace : autorisation OAuth2 (ouvre le navigateur la première fois)."""
        if self._client is not None and self.provider != "imap":
            return
        if self._client_factory is None:
            raise GmailAuthRequired("Aucune méthode de connexion configurée")
        client = self._client_factory(True)
        email = getattr(client, "account_email", lambda: "")()
        self._attach(client, "gmail_oauth", email)
        if self.account_store:
            self.account_store.save_oauth(email)
        self._emit("connected", "Gmail connecté")

    def connect_imap(self, cfg: ImapConfig, password: str) -> None:
        """Autres hébergeurs et adresses simples : IMAP + mot de passe d'application."""
        if self.mode == "fake":  # simulation pour développer le formulaire du frontend
            if password == "mauvais":
                raise ImapAuthError("Identifiants refusés (simulation : mot de passe « mauvais »).")
            self.provider, self.account_email = "imap", cfg.email
            self._emit("connected", f"Boîte {cfg.email} connectée (simulation IMAP)")
            return
        client = ImapMailClient(cfg.host, cfg.email, password, cfg.port, cfg.folder)
        client.test_connection()  # lève ImapAuthError / ImapConnectionError si échec
        self._attach(client, "imap", cfg.email)
        if self.account_store:
            self.account_store.save_imap(cfg, password)
        self._emit("connected", f"Boîte {cfg.email} connectée (IMAP)")

    def disconnect(self) -> None:
        self.stop_watching()
        if self._disconnect_fn:
            self._disconnect_fn()
        if self.account_store:
            self.account_store.clear()
        if self.mode == "real":
            self._client = None
            self.provider = self.account_email = None
        self._emit("disconnected", "Compte déconnecté")

    # --------------------------------------------------------- synchronisation
    # ------------------------------------------------- règle de récupération
    @property
    def _baseline_key(self) -> str:
        return f"baseline:{self.provider or 'none'}:{self.account_email or ''}"

    @property
    def _setup_key(self) -> str:
        return f"setup_done:{self.provider or 'none'}:{self.account_email or ''}"

    def _base_start(self, cfg: SyncConfig, now: datetime, create_baseline: bool = False) -> datetime | None:
        """Début de période demandé par la configuration, sans tenir compte de la dernière synchro."""
        if cfg.mode == "all":
            return None
        if cfg.mode == "since_date":
            return datetime.combine(cfg.since_date, dtime.min, tzinfo=timezone.utc)  # type: ignore[arg-type]
        if cfg.mode == "new_only":
            stored = self.ledger.get_state(self._baseline_key)
            if stored:
                return datetime.fromisoformat(stored)
            if create_baseline:  # point de départ : « à partir de maintenant »
                self.ledger.set_state(self._baseline_key, now.isoformat())
            return now
        return now - timedelta(days=cfg.days)  # last_days

    def window_start(self, now: datetime | None = None, create_baseline: bool = False) -> datetime | None:
        """Date à partir de laquelle on regarde les emails (None = tout l'historique)."""
        now = now or _now()
        base = self._base_start(self.sync_config, now, create_baseline)
        last = self.ledger.get_state(self._cursor_key)
        if last:  # reprise après la dernière synchro, avec un jour de marge (les doublons sont écartés)
            resume = datetime.fromisoformat(last) - timedelta(days=1)
            base = resume if base is None else max(base, resume)
        return base

    def update_config(self, config: SyncConfig) -> SyncConfig:
        """Change les réglages (période, règles d'exclusion...) et les mémorise.

        Appeler cette méthode valide aussi l'écran de démarrage : le choix de reprise est considéré comme fait.
        """
        old = self.sync_config
        self.sync_config = config
        self.ledger.set_state("sync_config", config.model_dump_json(exclude={"profile", "description", "warnings"}))
        self.ledger.set_state(self._setup_key, "1")
        if old._editable() != config._editable():
            # Nouveaux réglages : on rescanne toute la période pour que les emails déjà ignorés soient réévalués
            # (les doublons sont de toute façon écartés par le registre).
            self.ledger.delete_state(self._cursor_key)
        if config.mode == "new_only" and old.mode != "new_only":
            self.ledger.set_state(self._baseline_key, _now().isoformat())  # « nouveaux » = à partir de maintenant
        return config

    def apply_profile(self, name: str) -> SyncConfig:
        """Applique un profil prédéfini : prudent, new_only ou everything."""
        if name not in PROFILES:
            raise KeyError(name)
        return self.update_config(PROFILES[name].config.model_copy(deep=True))

    def sync_once(self) -> SyncResult:
        """Interroge la boîte mail une fois et télécharge les nouveaux CV."""
        if self._client is None:
            raise NotConnectedError("Gmail n'est pas connecté")
        with self._sync_lock:  # jamais deux synchronisations en même temps
            started = _now()
            result = SyncResult(started_at=started)
            since = self.window_start(started, create_baseline=True)
            result.since = since
            try:
                messages = self._client.list_cv_messages(
                    since, self.max_results, unread_only=self.sync_config.unread_only, folder=self.sync_config.folder
                )
            except Exception as exc:
                log.exception("Lecture de la boîte mail impossible")
                result.errors.append(f"Lecture de la boîte mail : {exc}")
                messages = []
            result.scanned_messages = len(messages)
            result.truncated = bool(getattr(self._client, "truncated", False))
            for message in messages:
                for attachment in message.attachments:
                    try:
                        self._process_attachment(message, attachment, result)
                    except Exception as exc:
                        log.exception("Échec du traitement de %s", attachment.filename)
                        result.errors.append(f"{attachment.filename} : {exc}")
            if not result.errors and not result.truncated:  # le curseur n'avance que si tout est traité sans erreur
                self.ledger.set_state(self._cursor_key, started.isoformat())
            result.finished_at = _now()
        if result.new_cvs:
            self._emit(
                "new_cvs",
                f"{len(result.new_cvs)} nouveau(x) CV récupéré(s)",
                {"count": len(result.new_cvs), "filenames": [c.filename for c in result.new_cvs], "ignored": result.ignored_count},
            )
        if result.errors:
            self._emit("sync_error", f"{len(result.errors)} erreur(s) pendant la synchronisation", {"errors": result.errors})
        return result

    def _exclusion(self, message: RawMessage, attachment: RawAttachment, extension: str, cfg: SyncConfig) -> tuple[str, str] | None:
        """Les règles de l'utilisateur écartent-elles cette pièce jointe ? Retourne (règle, raison) ou None."""
        if extension.lstrip(".") not in cfg.allowed_extensions:
            return "extension", f"type de fichier désactivé dans les réglages ({extension.lstrip('.').upper()})"
        _, address = parse_sender(message.sender)
        rule = cfg.sender_ignored(address)
        if rule:
            return "sender", f"expéditeur ou domaine ignoré dans les réglages ({rule})"
        if cfg.ignore_automatic and message.automatic_reason:
            return "automatic", message.automatic_reason
        limit = cfg.max_attachment_mb * 1024 * 1024
        if attachment.size and attachment.size > limit:
            return "size", f"fichier trop volumineux ({attachment.size / 1048576:.1f} Mo, maximum {cfg.max_attachment_mb} Mo)"
        return None

    def _record_ignored(self, message: RawMessage, attachment: RawAttachment, rule: str, reason: str) -> None:
        name, address = parse_sender(message.sender)
        self.ledger.upsert_ignored(
            {
                "message_id": message.id,
                "filename": attachment.filename,
                "sender_name": name,
                "sender_email": address,
                "subject": message.subject,
                "received_at": message.received_at.isoformat(),
                "rule": rule,
                "reason": reason,
            }
        )

    def _process_attachment(
        self, message: RawMessage, attachment: RawAttachment, result: SyncResult, force: bool = False
    ) -> None:
        extension = Path(attachment.filename).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            return  # pas un CV (image de signature, etc.)
        name, address = parse_sender(message.sender)

        def skip(reason: str) -> None:
            result.skipped.append(
                SkippedAttachment(filename=attachment.filename, sender_email=address, subject=message.subject, reason=reason)
            )

        if not force:
            verdict = self._exclusion(message, attachment, extension, self.sync_config)
            if verdict:  # écarté par les règles : jamais en silence, il apparaît dans la liste « Ignorés »
                self._record_ignored(message, attachment, *verdict)
                result.ignored_count += 1
                return
        if self.ledger.is_seen(message.id, attachment.attachment_id):
            result.duplicates_skipped += 1  # déjà traité lors d'une synchro précédente : silencieux
            return
        data = self._client.download_attachment(message.id, attachment.attachment_id)  # type: ignore[union-attr]
        if not force and len(data) > self.sync_config.max_attachment_mb * 1024 * 1024:
            self._record_ignored(message, attachment, "size", f"fichier trop volumineux ({len(data) / 1048576:.1f} Mo, maximum {self.sync_config.max_attachment_mb} Mo)")
            result.ignored_count += 1
            return
        if not looks_valid(extension, data):
            self.ledger.mark_seen(message.id, attachment.attachment_id, "invalid")
            result.invalid_skipped += 1
            skip("fichier invalide (vide, corrompu ou renommé : le contenu ne correspond pas à l'extension)")
            return
        digest = hashlib.sha256(data).hexdigest()
        known = self.ledger.cv_by_sha(digest)
        if known is not None:  # même fichier déjà reçu (même contenu octet pour octet)
            self.ledger.mark_seen(message.id, attachment.attachment_id, "duplicate")
            result.duplicates_skipped += 1
            skip(f"même contenu que « {known.filename} » déjà enregistré le {known.received_at:%d/%m/%Y %H:%M} : un CV renvoyé tel quel n'est pas recompté")
            return

        self.cv_dir.mkdir(parents=True, exist_ok=True)
        target = self.cv_dir / f"{message.received_at:%Y%m%d}_{message.id[:8]}_{safe_filename(attachment.filename)}"
        tmp = target.with_suffix(target.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(target)  # écriture atomique : jamais de fichier à moitié écrit

        cv = CVMetadata(
            message_id=message.id,
            attachment_id=attachment.attachment_id,
            filename=attachment.filename,
            saved_path=str(target),
            sender_name=name,
            sender_email=address,
            subject=message.subject,
            body_excerpt=message.body_excerpt,
            received_at=message.received_at,
            size_bytes=len(data),
            sha256=digest,
            downloaded_at=_now(),
        )
        if self.ledger.add_cv(cv):
            result.new_cvs.append(cv)
            self.ledger.delete_ignored(message.id, attachment.filename)  # n'est plus ignoré (règle assouplie ou récupéré)
        else:
            target.unlink(missing_ok=True)
            result.duplicates_skipped += 1
            skip("fichier identique déjà enregistré")

    # ------------------------------------------------------------- aperçu
    def preview(self, config: SyncConfig | None = None, sample_size: int = 20) -> PreviewResult:
        """Aperçu AVANT import : combien d'emails avec CV, combien seraient importés ou ignorés.

        Ne télécharge aucun CV, n'écrit rien. `config` permet d'évaluer des réglages qu'on n'a pas encore enregistrés.
        """
        if self._client is None:
            raise NotConnectedError("Gmail n'est pas connecté")
        cfg = config or self.sync_config
        now = _now()
        since = self._base_start(cfg, now)  # un aperçu ignore le curseur : « que se passerait-il avec ces réglages ? »
        result = PreviewResult(description=cfg.describe(), since=since)
        with self._sync_lock:
            had_filter = hasattr(self._client, "skip_filter")
            saved_filter = getattr(self._client, "skip_filter", None)
            if had_filter:
                self._client.skip_filter = None  # type: ignore[attr-defined]  # on veut TOUT voir, y compris l'existant
            try:
                messages = self._client.list_cv_messages(since, self.max_results, unread_only=cfg.unread_only, folder=cfg.folder)
                result.truncated = bool(getattr(self._client, "truncated", False))
            finally:
                if had_filter:
                    self._client.skip_filter = saved_filter  # type: ignore[attr-defined]
        items: list[PreviewItem] = []
        for message in messages:
            sender_name, address = parse_sender(message.sender)
            counted = False
            for attachment in message.attachments:
                extension = Path(attachment.filename).suffix.lower()
                if extension not in SUPPORTED_EXTENSIONS:
                    continue
                counted = True
                reason = ""
                if self.ledger.has_message(message.id):
                    outcome = "already_imported"
                    result.already_imported += 1
                else:
                    verdict = self._exclusion(message, attachment, extension, cfg)
                    if verdict:
                        outcome, reason = "ignored", verdict[1]
                        result.ignored += 1
                        result.ignored_by_rule[verdict[0]] = result.ignored_by_rule.get(verdict[0], 0) + 1
                    else:
                        outcome = "to_import"
                        result.to_import += 1
                items.append(
                    PreviewItem(
                        sender_name=sender_name, sender_email=address, subject=message.subject,
                        received_at=message.received_at, filename=attachment.filename, outcome=outcome, reason=reason,  # type: ignore[arg-type]
                    )
                )
            result.emails_with_cv += 1 if counted else 0
        items.sort(key=lambda i: i.received_at, reverse=True)
        result.samples = items[:sample_size]
        return result

    # --------------------------------------------------- liste « Ignorés »
    def recover_ignored(self, ignored_id: int) -> RecoverResult:
        """Bouton « Récupérer quand même » : importe une pièce jointe écartée par les règles."""
        found = self.ledger.get_ignored(ignored_id)
        if found is None:
            raise KeyError(ignored_id)
        item, message_id = found
        if self._client is None:
            raise NotConnectedError("Gmail n'est pas connecté")
        getter = getattr(self._client, "get_message", None)
        message = getter(message_id) if getter else None
        attachment = next((a for a in (message.attachments if message else []) if a.filename == item.filename), None)
        if message is None or attachment is None:
            raise GmailModuleError("Email introuvable dans la boîte (supprimé ou déplacé ?)")
        result = SyncResult(started_at=_now())
        with self._sync_lock:
            self._process_attachment(message, attachment, result, force=True)
        if result.new_cvs:
            self._emit("new_cvs", "1 CV récupéré depuis la liste des ignorés", {"count": 1, "filenames": [item.filename], "source": "recovered"})
            return RecoverResult(imported=result.new_cvs[0], detail="CV récupéré.")
        reason = result.skipped[0].reason if result.skipped else "déjà traité"
        if result.duplicates_skipped:  # on l'avait déjà : plus rien à « récupérer »
            self.ledger.delete_ignored(message_id, item.filename)
        return RecoverResult(imported=None, detail=f"Non importé : {reason}")

    # ---------------------------------------------------------- import manuel
    def import_files(self, files: list[tuple[str, bytes]]) -> ImportResult:
        """Importe des CV déposés à la main (PDF, DOCX ou ZIP). Ne nécessite aucune connexion mail."""
        with self._sync_lock:
            result = import_cv_files(self.ledger, self.cv_dir, files)
        if result.imported:
            self._emit(
                "new_cvs",
                f"{len(result.imported)} CV importé(s)",
                {"count": len(result.imported), "filenames": [c.filename for c in result.imported], "source": "upload"},
            )
        return result

    # ----------------------------------------------------------- surveillance
    def start_watching(self, poll_minutes: float | None = None) -> None:
        if self._client is None:
            raise NotConnectedError("Gmail n'est pas connecté")
        if self.watching:
            return
        if poll_minutes:
            self.poll_minutes = poll_minutes
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="gmail-watcher", daemon=True)
        self._thread.start()
        self._emit("watch_started", f"Surveillance démarrée (toutes les {self.poll_minutes:g} min)")

    def stop_watching(self) -> None:
        if not self.watching:
            return
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._emit("watch_stopped", "Surveillance arrêtée")

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.sync_once()
            except Exception:
                log.exception("Cycle de surveillance en échec")
            if self._stop.wait(self.poll_minutes * 60):
                break


# --------------------------------------------------------------------------- #
# Fabrique : point d'entrée unique pour l'API, la CLI et l'app principale
# --------------------------------------------------------------------------- #
def create_agent(settings: GmailSettings | None = None, mode: str | None = None) -> GmailAgent:
    s = settings or load_settings()
    mode = (mode or s.mode).lower()
    if mode == "fake":
        # Données de démo séparées des vrais CV et du vrai registre
        agent = GmailAgent(
            ledger=Ledger(s.ledger_path.with_name("gmail_ledger_demo.db")),
            cv_dir=s.cv_dir / "_demo",
            mode="fake",
            client=FakeMailClient.with_demo_data(5),
            poll_minutes=s.poll_minutes,
            lookback_days=s.lookback_days,
            max_results=s.max_results,
            sync_config=default_sync_config(s),
        )
        return agent

    from .auth import connect_gmail, forget_token

    agent = GmailAgent(
        ledger=Ledger(s.ledger_path),
        cv_dir=s.cv_dir,
        mode="real",
        client_factory=lambda interactive: GmailApiClient(connect_gmail(s.credentials_path, s.token_path, interactive)),
        disconnect_fn=lambda: forget_token(s.token_path),
        account_store=AccountStore(s.account_path, default_secret_store()),
        poll_minutes=s.poll_minutes,
        lookback_days=s.lookback_days,
        max_results=s.max_results,
        sync_config=default_sync_config(s),
    )
    agent.try_restore()
    return agent
