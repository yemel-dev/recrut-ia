"""Accès aux données. Les services ne manipulent que des dictionnaires, jamais des sessions SQLAlchemy."""
from __future__ import annotations

from typing import Any

from sqlalchemy import and_, func, or_, select

from .db import Database
from .models import Candidature, Compte, Entreprise, Parametre, Poste, Score


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


# Colonnes lourdes exclues des listes (texte complet, vecteur, extraction détaillée)
_COLONNES_LEGERES = [
    c for c in Candidature.__table__.columns
    if c.key not in ("texte", "texte_lettre", "extraction", "vecteur", "corps", "decision_note")
]


class CandidatureRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def cles_connues(self) -> set[str]:
        with self.db.session() as s:
            return set(s.scalars(select(Candidature.cle)))

    def creer(self, **fields: Any) -> dict[str, Any]:
        with self.db.session() as s:
            candidature = Candidature(**fields)
            s.add(candidature)
            s.flush()
            return _as_dict(candidature)

    def get(self, candidature_id: int) -> dict[str, Any] | None:
        with self.db.session() as s:
            candidature = s.get(Candidature, candidature_id)
            return _as_dict(candidature) if candidature else None

    def get_par_cle(self, cle: str) -> dict[str, Any] | None:
        with self.db.session() as s:
            candidature = s.scalars(select(Candidature).where(Candidature.cle == cle)).first()
            return _as_dict(candidature) if candidature else None

    def maj(self, candidature_id: int, **fields: Any) -> dict[str, Any] | None:
        with self.db.session() as s:
            candidature = s.get(Candidature, candidature_id)
            if candidature is None:
                return None
            for key, value in fields.items():
                setattr(candidature, key, value)
            s.flush()
            return _as_dict(candidature)

    def ids_a_lire(self, version_extraction: int) -> list[int]:
        """En attente de lecture, ou lues avec une version d'extraction dépassée."""
        with self.db.session() as s:
            requete = select(Candidature.id).where(
                or_(
                    Candidature.statut_lecture == "en_attente",
                    and_(
                        Candidature.statut_lecture == "lue",
                        or_(Candidature.version_extraction.is_(None), Candidature.version_extraction < version_extraction),
                    ),
                )
            )
            return list(s.scalars(requete.order_by(Candidature.id)))

    def toutes(self) -> list[dict[str, Any]]:
        with self.db.session() as s:
            return [_as_dict(c) for c in s.scalars(select(Candidature).order_by(Candidature.id))]

    def lues(self) -> list[dict[str, Any]]:
        """Candidatures lisibles, avec ce qu'il faut pour les noter (sans relire les fichiers)."""
        with self.db.session() as s:
            requete = select(Candidature).where(Candidature.statut_lecture == "lue").order_by(Candidature.id)
            return [_as_dict(c) for c in s.scalars(requete)]

    def lister(
        self,
        statut_classement: str | None = None,
        statut_lecture: str | None = None,
        poste_id: int | None = None,
        limite: int = 50,
        decalage: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Liste légère, la plus récente d'abord, avec le score pour le poste assigné."""
        conditions = []
        if statut_classement:
            conditions.append(Candidature.statut_classement == statut_classement)
        if statut_lecture:
            conditions.append(Candidature.statut_lecture == statut_lecture)
        if poste_id is not None:
            conditions.append(Candidature.poste_id == poste_id)
        with self.db.session() as s:
            total = s.scalar(select(func.count()).select_from(Candidature).where(*conditions))
            requete = (
                select(*_COLONNES_LEGERES, Score.score, Poste.intitule)
                .outerjoin(Score, and_(Score.candidature_id == Candidature.id, Score.poste_id == Candidature.poste_id))
                .outerjoin(Poste, Poste.id == Candidature.poste_id)
                .where(*conditions)
                .order_by(Candidature.recue_le.desc(), Candidature.id.desc())
                .limit(limite)
                .offset(decalage)
            )
            lignes = []
            for rangee in s.execute(requete):
                donnees = dict(rangee._mapping)
                donnees["poste_intitule"] = donnees.pop("intitule")
                lignes.append(donnees)
            return lignes, total

    def compter(self) -> dict[str, int]:
        with self.db.session() as s:
            # Classement des seules candidatures lues (une illisible n'est pas « non classée » : elle est à ouvrir)
            par_classement = dict(
                s.execute(
                    select(Candidature.statut_classement, func.count())
                    .where(Candidature.statut_lecture == "lue")
                    .group_by(Candidature.statut_classement)
                ).all()
            )
            par_lecture = dict(s.execute(select(Candidature.statut_lecture, func.count()).group_by(Candidature.statut_lecture)).all())
            # Pas encore lues, ou lues mais pas encore classées
            en_attente = s.scalar(
                select(func.count()).select_from(Candidature).where(
                    or_(
                        Candidature.statut_lecture == "en_attente",
                        and_(Candidature.statut_lecture == "lue", Candidature.statut_classement == "a_traiter"),
                    )
                )
            )
        return {
            "total": sum(par_lecture.values()),
            "en_attente": en_attente,
            "illisibles": par_lecture.get("illisible", 0),
            "classees": par_classement.get("classe", 0),
            "a_verifier": par_classement.get("a_verifier", 0),
            "non_classees": par_classement.get("non_classe", 0),
        }

    def compter_par_poste(self) -> dict[int, int]:
        with self.db.session() as s:
            requete = select(Candidature.poste_id, func.count()).where(Candidature.poste_id.is_not(None)).group_by(Candidature.poste_id)
            return dict(s.execute(requete).all())

    def compter_decisions(self, poste_id: int) -> dict[str, int]:
        """Candidatures notées et rattachées au poste, par décision du recruteur."""
        with self.db.session() as s:
            requete = (
                select(Candidature.decision, func.count())
                .join(Score, and_(Score.candidature_id == Candidature.id, Score.poste_id == poste_id))
                .where(Candidature.poste_id == poste_id)
                .group_by(Candidature.decision)
            )
            return dict(s.execute(requete).all())


class ScoreRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def enregistrer(self, candidature_id: int, poste_id: int, **fields: Any) -> None:
        with self.db.session() as s:
            score = s.scalars(select(Score).where(Score.candidature_id == candidature_id, Score.poste_id == poste_id)).first()
            if score is None:
                s.add(Score(candidature_id=candidature_id, poste_id=poste_id, **fields))
            else:
                for key, value in fields.items():
                    setattr(score, key, value)

    def pour_candidature(self, candidature_id: int) -> list[dict[str, Any]]:
        with self.db.session() as s:
            requete = (
                select(Score, Poste.intitule, Poste.statut)
                .join(Poste, Poste.id == Score.poste_id)
                .where(Score.candidature_id == candidature_id)
                .order_by(Score.pertinence.desc())
            )
            return [{**_as_dict(score), "poste_intitule": intitule, "poste_statut": statut} for score, intitule, statut in s.execute(requete)]

    def get(self, candidature_id: int, poste_id: int) -> dict[str, Any] | None:
        with self.db.session() as s:
            score = s.scalars(select(Score).where(Score.candidature_id == candidature_id, Score.poste_id == poste_id)).first()
            return _as_dict(score) if score else None

    def top(self, poste_id: int, limite: int, decision: str | None = None) -> list[dict[str, Any]]:
        """Candidatures rattachées au poste, triées par score décroissant, avec leur rang.

        Avec `decision`, le rang reste celui du classement complet : le filtre masque des lignes sans rien réordonner.
        """
        with self.db.session() as s:
            requete = (
                select(Score, *_COLONNES_LEGERES)
                .join(Candidature, Candidature.id == Score.candidature_id)
                .where(Score.poste_id == poste_id, Candidature.poste_id == poste_id)
                .order_by(Score.score.desc(), Candidature.recue_le.desc(), Candidature.id)
            )
            if decision is None:
                requete = requete.limit(limite)
            resultat = []
            for rang, rangee in enumerate(s.execute(requete), start=1):
                donnees = dict(rangee._mapping)
                score = donnees.pop("Score")
                if decision is not None and donnees["decision"] != decision:
                    continue
                resultat.append({
                    "rang": rang,
                    "candidature": donnees,
                    "score": score.score,
                    "pertinence": score.pertinence,
                    "detail": score.detail,
                    "adequation_ignoree": score.adequation_ignoree,
                    "potentiel_niveau": score.potentiel_niveau,
                })
            return resultat
