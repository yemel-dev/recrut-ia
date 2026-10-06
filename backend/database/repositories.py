"""Accès aux données. Les services ne manipulent que des dictionnaires, jamais des sessions SQLAlchemy."""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from .db import Database
from .models import Compte, Entreprise, Parametre, Poste


def _as_dict(row: Any) -> dict[str, Any]:
    return {column.key: getattr(row, column.key) for column in row.__table__.columns}


class CompteRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def get(self) -> dict[str, Any] | None:
        with self.db.session() as s:
            compte = s.scalars(select(Compte).limit(1)).first()
            return _as_dict(compte) if compte else None

    def exists(self) -> bool:
        with self.db.session() as s:
            return s.scalar(select(func.count()).select_from(Compte)) > 0

    def create(self, **fields: Any) -> dict[str, Any]:
        with self.db.session() as s:
            compte = Compte(**fields)
            s.add(compte)
            s.flush()
            return _as_dict(compte)

    def update(self, **fields: Any) -> dict[str, Any]:
        with self.db.session() as s:
            compte = s.scalars(select(Compte).limit(1)).one()
            for key, value in fields.items():
                setattr(compte, key, value)
            s.flush()
            return _as_dict(compte)


class EntrepriseRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def get(self) -> dict[str, Any] | None:
        with self.db.session() as s:
            entreprise = s.scalars(select(Entreprise).limit(1)).first()
            return _as_dict(entreprise) if entreprise else None

    def save(self, **fields: Any) -> dict[str, Any]:
        with self.db.session() as s:
            entreprise = s.scalars(select(Entreprise).limit(1)).first()
            if entreprise is None:
                entreprise = Entreprise()
                s.add(entreprise)
            for key, value in fields.items():
                setattr(entreprise, key, value)
            s.flush()
            return _as_dict(entreprise)


class PosteRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def list(self, statut: str | None = None) -> list[dict[str, Any]]:
        query = select(Poste).order_by(Poste.modifie_le.desc(), Poste.id.desc())
        if statut:
            query = query.where(Poste.statut == statut)
        with self.db.session() as s:
            return [_as_dict(p) for p in s.scalars(query)]

    def get(self, poste_id: int) -> dict[str, Any] | None:
        with self.db.session() as s:
            poste = s.get(Poste, poste_id)
            return _as_dict(poste) if poste else None

    def create(self, **fields: Any) -> dict[str, Any]:
        with self.db.session() as s:
            poste = Poste(**fields)
            s.add(poste)
            s.flush()
            return _as_dict(poste)

    def update(self, poste_id: int, **fields: Any) -> dict[str, Any] | None:
        with self.db.session() as s:
            poste = s.get(Poste, poste_id)
            if poste is None:
                return None
            for key, value in fields.items():
                setattr(poste, key, value)
            s.flush()
            return _as_dict(poste)

    def delete(self, poste_id: int) -> bool:
        with self.db.session() as s:
            poste = s.get(Poste, poste_id)
            if poste is None:
                return False
            s.delete(poste)
            return True

    def count_by_statut(self) -> dict[str, int]:
        with self.db.session() as s:
            rows = s.execute(select(Poste.statut, func.count()).group_by(Poste.statut))
            return {statut: total for statut, total in rows}


class ParametreRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def get(self, cle: str) -> str | None:
        with self.db.session() as s:
            parametre = s.get(Parametre, cle)
            return parametre.valeur if parametre else None

    def set(self, cle: str, valeur: str) -> None:
        with self.db.session() as s:
            parametre = s.get(Parametre, cle)
            if parametre is None:
                s.add(Parametre(cle=cle, valeur=valeur))
            else:
                parametre.valeur = valeur
