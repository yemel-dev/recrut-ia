"""Profils de poste : création, consultation, modification, suppression, statut.

Seuls les postes au statut « actif » serviront au classement des candidatures.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from ..database.repositories import PosteRepository
from .erreurs import ErreurValidation, Introuvable
from .validation import liste, texte

STATUTS = ("brouillon", "actif", "cloture")
NIVEAUX_FORMATION = ("BTS", "Licence", "Master", "Doctorat")
TYPES_CONTRAT = ("CDI", "CDD", "stage", "mission", "freelance")
TELETRAVAIL = ("sur_site", "hybride", "complet")

EXPERIENCE_MAX = 50
CHAMPS_TEXTE = {
    "intitule": 255,
    "description": 20000,
    "reference_interne": 100,
    "departement": 255,
    "lieu": 255,
    "duree": 100,
    "remuneration": 255,
    "processus_selection": 5000,
}
CHAMPS_LISTE = ("competences_requises", "competences_comportementales", "langues", "documents_demandes")
TAILLE_MAX_LISTE = 50
TAILLE_MAX_ELEMENT = 100
POIDS = ("poids_competences", "poids_experience", "poids_formation", "poids_adequation")
POIDS_DEFAUT = {"poids_competences": 40, "poids_experience": 25, "poids_formation": 20, "poids_adequation": 15}


class PostesService:
    def __init__(self, repo: PosteRepository) -> None:
        self.repo = repo
        # Services prévenus quand un poste change (les candidatures sont alors renotées).
        self.a_la_modification: list[Callable[[], None]] = []

    def _prevenir(self) -> None:
        for abonne in self.a_la_modification:
            abonne()

    def lister(self, statut: str | None = None) -> list[dict[str, Any]]:
        if statut is not None and statut not in STATUTS:
            raise ErreurValidation({"statut": "Statut inconnu."})
        return self.repo.list(statut)

    def consulter(self, poste_id: int) -> dict[str, Any]:
        poste = self.repo.get(poste_id)
        if poste is None:
            raise Introuvable("Ce poste n'existe pas ou a été supprimé.")
        return poste

    def creer(self, donnees: dict[str, Any]) -> dict[str, Any]:
        poste = self.repo.create(**self._valider(donnees))
        self._prevenir()
        return poste

    def modifier(self, poste_id: int, donnees: dict[str, Any]) -> dict[str, Any]:
        actuel = self.consulter(poste_id)
        poste = self.repo.update(poste_id, **self._valider(donnees, actuel))
        self._prevenir()
        return poste

    def changer_statut(self, poste_id: int, statut: str) -> dict[str, Any]:
        if statut not in STATUTS:
            raise ErreurValidation({"statut": "Statut inconnu."})
        self.consulter(poste_id)
        poste = self.repo.update(poste_id, statut=statut)
        self._prevenir()
        return poste

    def supprimer(self, poste_id: int) -> None:
        if not self.repo.delete(poste_id):
            raise Introuvable("Ce poste n'existe pas ou a été supprimé.")
        self._prevenir()

    def compter_par_statut(self) -> dict[str, int]:
        comptes = self.repo.count_by_statut()
        resultat = {statut: comptes.get(statut, 0) for statut in STATUTS}
        resultat["total"] = sum(resultat.values())
        return resultat

    # --- Validation -----------------------------------------------------------------

    def _valider(self, donnees: dict[str, Any], actuel: dict[str, Any] | None = None) -> dict[str, Any]:
        erreurs: dict[str, str] = {}
        v: dict[str, Any] = {champ: texte(donnees.get(champ)) for champ in CHAMPS_TEXTE}
        for champ in CHAMPS_LISTE:
            v[champ] = liste(donnees.get(champ))

        # Obligatoires
        if not v["intitule"]:
            erreurs["intitule"] = "L'intitulé du poste est obligatoire."
        if not v["description"]:
            erreurs["description"] = "La description et les missions sont obligatoires."
        if not v["competences_requises"]:
            erreurs["competences_requises"] = "Indiquez au moins une compétence requise."

        experience = donnees.get("experience_min_annees")
        if experience is None or experience == "":
            erreurs["experience_min_annees"] = "L'expérience minimale est obligatoire (0 si débutant accepté)."
        elif isinstance(experience, bool) or not isinstance(experience, int) or not 0 <= experience <= EXPERIENCE_MAX:
            erreurs["experience_min_annees"] = f"Indiquez un nombre entier d'années entre 0 et {EXPERIENCE_MAX}."
        v["experience_min_annees"] = experience

        v["niveau_formation"] = donnees.get("niveau_formation")
        if v["niveau_formation"] not in NIVEAUX_FORMATION:
            erreurs["niveau_formation"] = "Choisissez un niveau de formation : " + ", ".join(NIVEAUX_FORMATION) + "."

        # Facultatifs à valeurs fixes
        v["type_contrat"] = donnees.get("type_contrat") or None
        if v["type_contrat"] is not None and v["type_contrat"] not in TYPES_CONTRAT:
            erreurs["type_contrat"] = "Type de contrat inconnu."
        v["teletravail"] = donnees.get("teletravail") or None
        if v["teletravail"] is not None and v["teletravail"] not in TELETRAVAIL:
            erreurs["teletravail"] = "Option de télétravail inconnue."
        v["statut"] = donnees.get("statut") or "brouillon"
        if v["statut"] not in STATUTS:
            erreurs["statut"] = "Statut inconnu."

        date_limite = donnees.get("date_limite")
        if isinstance(date_limite, str):
            try:
                date_limite = date.fromisoformat(date_limite) if date_limite else None
            except ValueError:
                erreurs["date_limite"] = "Date invalide."
                date_limite = None
        v["date_limite"] = date_limite

        # Longueurs
        for champ, maximum in CHAMPS_TEXTE.items():
            if v[champ] and len(v[champ]) > maximum and champ not in erreurs:
                erreurs[champ] = f"{maximum} caractères maximum."
        for champ in CHAMPS_LISTE:
            if len(v[champ]) > TAILLE_MAX_LISTE:
                erreurs[champ] = f"{TAILLE_MAX_LISTE} éléments maximum."
            elif any(len(e) > TAILLE_MAX_ELEMENT for e in v[champ]):
                erreurs[champ] = f"Chaque élément est limité à {TAILLE_MAX_ELEMENT} caractères."

        # Poids du score : entiers de 0 à 100, total 100. Absents : valeurs actuelles, sinon par défaut.
        for champ in POIDS:
            valeur = donnees.get(champ)
            if valeur is None:
                valeur = (actuel or {}).get(champ, POIDS_DEFAUT[champ])
            if isinstance(valeur, bool) or not isinstance(valeur, int) or not 0 <= valeur <= 100:
                erreurs[champ] = "Indiquez un nombre entier entre 0 et 100."
            v[champ] = valeur
        if not any(c in erreurs for c in POIDS) and sum(v[c] for c in POIDS) != 100:
            erreurs["poids"] = f"La somme des poids doit faire 100 (actuellement {sum(v[c] for c in POIDS)})."

        if erreurs:
            raise ErreurValidation(erreurs)
        return v
