"""Mise à niveau des bases existantes.

`create_all` crée les tables manquantes mais n'ajoute pas de colonne à une table existante. Ce module ajoute
les colonnes déclarées dans les modèles qui manquent dans la base (ex. : poids du score dans `postes`).
Une colonne ajoutée doit être facultative ou avoir une valeur par défaut côté base (`server_default`).
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta

from sqlalchemy import Engine, MetaData, inspect, text

from .models import Base

log = logging.getLogger("injara.database")

VALIDITE_LIEN = timedelta(days=7)  # comme services/entretiens.py


def convertir_anciens_entretiens(engine: Engine) -> int:
    """Ancienne table `entretiens` (branche des mails, avant le module vidéo : colonne `debut`, pas de code
    d'invitation) : reconstruite au format actuel en gardant chaque entretien. Renvoie le nombre de lignes reprises."""
    inspecteur = inspect(engine)
    if not inspecteur.has_table("entretiens"):
        return 0
    colonnes = {c["name"] for c in inspecteur.get_columns("entretiens")}
    if "debut" not in colonnes or "code_invitation" in colonnes:
        return 0
    table = Base.metadata.tables["entretiens"]
    meta = MetaData()
    for nom in ("candidatures", "postes"):  # cibles des clés étrangères, pour générer le CREATE TABLE
        Base.metadata.tables[nom].to_metadata(meta)
    provisoire = table.to_metadata(meta, name="entretiens_nouveau")
    provisoire.indexes.clear()
    with engine.begin() as connexion:
        anciens = connexion.exec_driver_sql(
            "SELECT e.id, e.candidature_id, p.id AS poste_id, e.debut, e.duree_minutes, e.mode, e.adresse, e.message,"
            " e.statut, e.cree_le, e.modifie_le FROM entretiens e JOIN candidatures c ON c.id = e.candidature_id"
            " LEFT JOIN postes p ON p.id = e.poste_id"  # lignes orphelines écartées : elles bloqueraient le démarrage
        ).mappings().all()
        provisoire.create(connexion)
        for e in anciens:
            debut = _date(e["debut"])
            connexion.execute(provisoire.insert().values(
                id=e["id"], candidature_id=e["candidature_id"], poste_id=e["poste_id"],
                code_invitation=secrets.token_urlsafe(12), date_entretien=debut,
                expire_le=debut + VALIDITE_LIEN if debut else None, statut="planifie",
                duree_minutes=e["duree_minutes"] or 60, mode=e["mode"] or "en_ligne",
                adresse=e["adresse"], message=e["message"],
                confirme_le=_date(e["modifie_le"]) if e["statut"] == "confirme" else None,
                cree_le=_date(e["cree_le"]), modifie_le=_date(e["modifie_le"]),
            ))
        connexion.exec_driver_sql("DROP TABLE entretiens")
        connexion.exec_driver_sql("ALTER TABLE entretiens_nouveau RENAME TO entretiens")
        for index in table.indexes:
            index.create(connexion)
    log.info("Entretiens convertis au format du module vidéo : %d", len(anciens))
    return len(anciens)


def _date(valeur) -> datetime | None:
    if valeur is None or isinstance(valeur, datetime):
        return valeur
    return datetime.fromisoformat(str(valeur))


def ajouter_colonnes_manquantes(engine: Engine) -> list[str]:
    inspecteur = inspect(engine)
    ajoutees = []
    with engine.begin() as connexion:
        for table in Base.metadata.sorted_tables:
            if not inspecteur.has_table(table.name):
                continue
            existantes = {c["name"] for c in inspecteur.get_columns(table.name)}
            for colonne in table.columns:
                if colonne.name in existantes:
                    continue
                if not colonne.nullable and colonne.server_default is None:
                    raise RuntimeError(f"Colonne {table.name}.{colonne.name} : valeur par défaut requise pour la migration.")
                definition = f'"{colonne.name}" {colonne.type.compile(engine.dialect)}'
                if colonne.server_default is not None:
                    definition += f" DEFAULT {colonne.server_default.arg}"
                connexion.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN {definition}'))
                ajoutees.append(f"{table.name}.{colonne.name}")
    if ajoutees:
        log.info("Base mise à niveau : %s", ", ".join(ajoutees))
    return ajoutees
