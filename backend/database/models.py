"""Modèles SQLAlchemy du socle INJARA.

Une installation = une entreprise = un compte. Les tables liées aux candidatures (candidats, analyses,
entretiens) seront ajoutées avec leurs modules.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, Integer, LargeBinary, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _now() -> datetime:
    return datetime.now(timezone.utc)


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
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    modifie_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


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
    modifie_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


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

    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    modifie_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
