"""Modèles SQLAlchemy du socle INJARA.

Une installation = une entreprise = un compte. Les tables des entretiens seront ajoutées avec leur module.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, TypeDecorator, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DateHeureUTC(TypeDecorator):
    """SQLite ne conserve pas le fuseau horaire : on stocke en UTC et on le rétablit à la lecture."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=timezone.utc) if value is not None else None


class Base(DeclarativeBase):
    pass


class Compte(Base):
    """Le compte unique du recruteur, avec la clé de données protégée deux fois."""

    __tablename__ = "compte"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    mot_de_passe_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Clé de données chiffrée par une clé dérivée du mot de passe (argon2id + AES-GCM)
    sel_mot_de_passe: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    cle_par_mot_de_passe: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    # Même clé de données, chiffrée par une clé dérivée de la clé de récupération (HKDF + AES-GCM)
    sel_recuperation: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    cle_par_recuperation: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    cree_le: Mapped[datetime] = mapped_column(DateHeureUTC, default=_now)
    modifie_le: Mapped[datetime] = mapped_column(DateHeureUTC, default=_now, onupdate=_now)


class Entreprise(Base):
    """Profil de l'entreprise (une seule ligne)."""

    __tablename__ = "entreprise"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nom: Mapped[str] = mapped_column(String(255), default="")
    secteur: Mapped[str | None] = mapped_column(String(255))
    ville: Mapped[str | None] = mapped_column(String(255))
    email_pro: Mapped[str | None] = mapped_column(String(255))
    telephone: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)
    modifie_le: Mapped[datetime] = mapped_column(DateHeureUTC, default=_now, onupdate=_now)


class Parametre(Base):
    """Préférences de l'application (clé / valeur), par exemple la surveillance automatique de la boîte mail."""

    __tablename__ = "parametres"

    cle: Mapped[str] = mapped_column(String(100), primary_key=True)
    valeur: Mapped[str] = mapped_column(Text, nullable=False)


class Poste(Base):
    """Profil de poste créé par l'entreprise. Seuls les postes « actif » serviront au classement."""

    __tablename__ = "postes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    statut: Mapped[str] = mapped_column(String(20), default="brouillon", index=True)

    # Obligatoires
    intitule: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    competences_requises: Mapped[list[str]] = mapped_column(JSON, default=list)
    experience_min_annees: Mapped[int] = mapped_column(Integer, default=0)
    niveau_formation: Mapped[str] = mapped_column(String(20), nullable=False)

    # Facultatifs
    reference_interne: Mapped[str | None] = mapped_column(String(100))
    departement: Mapped[str | None] = mapped_column(String(255))
    lieu: Mapped[str | None] = mapped_column(String(255))
    teletravail: Mapped[str | None] = mapped_column(String(20))
    type_contrat: Mapped[str | None] = mapped_column(String(20))
    duree: Mapped[str | None] = mapped_column(String(100))
    date_limite: Mapped[date | None] = mapped_column(Date)
    competences_comportementales: Mapped[list[str]] = mapped_column(JSON, default=list)
    langues: Mapped[list[str]] = mapped_column(JSON, default=list)
    remuneration: Mapped[str | None] = mapped_column(String(255))
    processus_selection: Mapped[str | None] = mapped_column(Text)
    documents_demandes: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Poids du score (sur 100), modifiables par poste
    poids_competences: Mapped[int] = mapped_column(Integer, default=40, server_default="40")
    poids_experience: Mapped[int] = mapped_column(Integer, default=25, server_default="25")
    poids_formation: Mapped[int] = mapped_column(Integer, default=20, server_default="20")
    poids_adequation: Mapped[int] = mapped_column(Integer, default=15, server_default="15")

    cree_le: Mapped[datetime] = mapped_column(DateHeureUTC, default=_now)
    modifie_le: Mapped[datetime] = mapped_column(DateHeureUTC, default=_now, onupdate=_now)


class Candidature(Base):
    """Une candidature = un mail reçu (ou un fichier importé à la main), avec son CV principal."""

    __tablename__ = "candidatures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cle: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)  # identifiant du mail dans l'agent
    source: Mapped[str] = mapped_column(String(20), default="email")
    expediteur_nom: Mapped[str | None] = mapped_column(String(255))
    expediteur_email: Mapped[str | None] = mapped_column(String(255))
    objet: Mapped[str | None] = mapped_column(Text)
    corps: Mapped[str | None] = mapped_column(Text)
    recue_le: Mapped[datetime | None] = mapped_column(DateHeureUTC)

    # Fichiers : le CV principal et les autres pièces jointes [{nom, chemin, sha256}]
    fichier_cv: Mapped[str] = mapped_column(Text, nullable=False)
    nom_fichier_cv: Mapped[str] = mapped_column(String(255), nullable=False)
    sha256_cv: Mapped[str] = mapped_column(String(64), nullable=False)
    pieces_jointes: Mapped[list[dict]] = mapped_column(JSON, default=list)

    # Étape 1 : lecture
    statut_lecture: Mapped[str] = mapped_column(String(20), default="en_attente", index=True)  # en_attente | lue | illisible
    motif_lecture: Mapped[str | None] = mapped_column(Text)

    # Étape 2 : extraction (indépendante des postes)
    texte: Mapped[str | None] = mapped_column(Text)
    texte_lettre: Mapped[str | None] = mapped_column(Text)
    extraction: Mapped[dict | None] = mapped_column(JSON)
    nom: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    telephone: Mapped[str | None] = mapped_column(String(50))
    experience_mois: Mapped[int | None] = mapped_column(Integer)
    stages_mois: Mapped[int | None] = mapped_column(Integer)
    diplome_niveau: Mapped[str | None] = mapped_column(String(20))
    version_extraction: Mapped[int | None] = mapped_column(Integer)
    vecteur: Mapped[bytes | None] = mapped_column(LargeBinary)  # Sentence-BERT, pour renoter sans relire le CV
    modele_vecteur: Mapped[str | None] = mapped_column(String(100))
    extraite_le: Mapped[datetime | None] = mapped_column(DateHeureUTC)

    # Étape 3 : classement
    poste_id: Mapped[int | None] = mapped_column(ForeignKey("postes.id", ondelete="SET NULL"), index=True)
    statut_classement: Mapped[str] = mapped_column(String(20), default="a_traiter", index=True)  # a_traiter | classe | a_verifier | non_classe
    mode_assignation: Mapped[str | None] = mapped_column(String(20))  # reference | automatique | manuel
    motif_classement: Mapped[str | None] = mapped_column(Text)
    classee_le: Mapped[datetime | None] = mapped_column(DateHeureUTC)

    # Décision du recruteur : n'influence ni le score ni le classement
    decision: Mapped[str] = mapped_column(String(20), default="a_examiner", server_default=text("'a_examiner'"))  # a_examiner | retenu | en_attente | ecarte
    decision_note: Mapped[str | None] = mapped_column(Text)  # chiffrée avec la clé de données (services/coffre.py)
    decision_le: Mapped[datetime | None] = mapped_column(DateHeureUTC)

    cree_le: Mapped[datetime] = mapped_column(DateHeureUTC, default=_now)
    modifie_le: Mapped[datetime] = mapped_column(DateHeureUTC, default=_now, onupdate=_now)


class Score(Base):
    """Étape 4 : score d'une candidature pour un poste, avec le détail de chaque critère."""

    __tablename__ = "scores"
    __table_args__ = (UniqueConstraint("candidature_id", "poste_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidature_id: Mapped[int] = mapped_column(ForeignKey("candidatures.id", ondelete="CASCADE"), nullable=False, index=True)
    poste_id: Mapped[int] = mapped_column(ForeignKey("postes.id", ondelete="CASCADE"), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    pertinence: Mapped[float] = mapped_column(Float, nullable=False)
    adequation_ignoree: Mapped[bool] = mapped_column(Boolean, default=False)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    # Indicateur de potentiel (ia/potentiel.py) : affiché à côté du score, sans jamais le modifier
    potentiel_niveau: Mapped[str | None] = mapped_column(String(20))
    potentiel: Mapped[dict | None] = mapped_column(JSON)
    calcule_le: Mapped[datetime] = mapped_column(DateHeureUTC, default=_now, onupdate=_now)
