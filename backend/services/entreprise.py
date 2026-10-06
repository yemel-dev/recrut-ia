"""Profil de l'entreprise (une seule par installation)."""
from __future__ import annotations

from typing import Any

from ..database.repositories import EntrepriseRepository
from .erreurs import ErreurValidation
from .validation import email_valide, telephone_valide, texte

CHAMPS = ("nom", "secteur", "ville", "email_pro", "telephone", "description")
_LONGUEURS = {"nom": 255, "secteur": 255, "ville": 255, "email_pro": 254, "telephone": 25, "description": 5000}


class EntrepriseService:
    def __init__(self, repo: EntrepriseRepository) -> None:
        self.repo = repo

    def consulter(self) -> dict[str, Any]:
        entreprise = self.repo.get() or {}
        return {champ: entreprise.get(champ) or ("" if champ == "nom" else None) for champ in CHAMPS}

    def enregistrer(self, donnees: dict[str, Any]) -> dict[str, Any]:
        valeurs = {champ: texte(donnees.get(champ)) for champ in CHAMPS}
        erreurs: dict[str, str] = {}
        if not valeurs["nom"]:
            erreurs["nom"] = "Le nom de l'entreprise est obligatoire."
        if valeurs["email_pro"]:
            valeurs["email_pro"] = valeurs["email_pro"].lower()
            if not email_valide(valeurs["email_pro"]):
                erreurs["email_pro"] = "Adresse email invalide."
        if valeurs["telephone"] and not telephone_valide(valeurs["telephone"]):
            erreurs["telephone"] = "Numéro de téléphone invalide (chiffres, espaces, +, -, points et parenthèses)."
        for champ, maximum in _LONGUEURS.items():
            if valeurs[champ] and len(valeurs[champ]) > maximum and champ not in erreurs:
                erreurs[champ] = f"{maximum} caractères maximum."
        if erreurs:
            raise ErreurValidation(erreurs)
        self.repo.save(**valeurs)
        return self.consulter()
