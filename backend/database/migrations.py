"""Mise à niveau des bases existantes.

`create_all` crée les tables manquantes mais n'ajoute pas de colonne à une table existante. Ce module ajoute
les colonnes déclarées dans les modèles qui manquent dans la base (ex. : poids du score dans `postes`).
Une colonne ajoutée doit être facultative ou avoir une valeur par défaut côté base (`server_default`).
"""
from __future__ import annotations

import logging

from sqlalchemy import Engine, inspect, text

from .models import Base

log = logging.getLogger("injara.database")


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
