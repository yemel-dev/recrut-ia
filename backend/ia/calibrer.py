"""Outil de développement : similarités brutes Sentence-BERT entre les CV fictifs et quelques postes.

    python -m backend.ia.calibrer

Sert à caler SIMILARITE_PLANCHER (≈ similarité d'un CV sans rapport) et SIMILARITE_PLAFOND (≈ CV très proche)
dans ia/scoring.py. Nécessite le modèle (python -m backend.ia.telecharger_modele).
"""
from __future__ import annotations

import time

from .scoring import SIMILARITE_PLAFOND, SIMILARITE_PLANCHER
from .semantique import ModeleSemantique, similarite

POSTES = {
    "Développeur Python": "Développeur Python\nDéveloppement d'API web en Python (Django REST Framework) pour nos clients "
    "bancaires, bases PostgreSQL, conteneurs Docker.\nPython, Django REST Framework, PostgreSQL, Docker, JavaScript",
    "Comptable principal": "Comptable principal\nTenue de la comptabilité générale selon le SYSCOHADA, déclarations "
    "fiscales, états financiers et paie.\nComptabilité générale, SYSCOHADA, Sage 100, Excel, Fiscalité",
    "Chef de projet IT": "Chef de projet informatique\nPilotage de projets de transformation numérique en méthode agile, "
    "coordination des équipes, reporting à la direction.\nGestion de projet, Scrum, Jira, MS Project",
    "Infirmier": "Infirmier diplômé d'État\nSoins aux patients hospitalisés, administration des traitements, suivi des "
    "dossiers médicaux.\nSoins infirmiers, Pharmacologie, Hygiène hospitalière",
}


def main() -> int:
    from ..tests.fixtures import fabrique

    modele = ModeleSemantique()
    debut = time.monotonic()
    if not modele.disponible:
        print(f"Modèle indisponible : {modele.motif_indisponible}")
        return 1
    print(f"Modèle chargé en {time.monotonic() - debut:.1f} s ; bornes actuelles : plancher {SIMILARITE_PLANCHER}, plafond {SIMILARITE_PLAFOND}")
    postes = {nom: modele.encoder(texte) for nom, texte in POSTES.items()}
    for cv in ["dev_python", "comptable", "scrum_master", "jeune_diplome"]:
        vecteur = modele.encoder(fabrique.texte_cv(cv))
        print(f"{cv:>14} | " + "  ".join(f"{nom[:12]:>12}: {similarite(vecteur, v):.3f}" for nom, v in postes.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
