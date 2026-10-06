"""Données de synthèse du tableau de bord."""
from __future__ import annotations

from typing import Any

from .entreprise import EntrepriseService
from .postes import PostesService


class TableauDeBordService:
    def __init__(self, entreprise: EntrepriseService, postes: PostesService) -> None:
        self.entreprise = entreprise
        self.postes = postes

    def synthese(self) -> dict[str, Any]:
        nom = self.entreprise.consulter()["nom"]
        return {
            "entreprise_nom": nom,
            "profil_renseigne": bool(nom),
            "postes": self.postes.compter_par_statut(),
        }
