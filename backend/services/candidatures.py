"""Candidatures côté recruteur : liste, fiche, choix manuel du poste, top par poste.

Le score est un indicateur : aucune candidature n'est rejetée ni masquée automatiquement.
"""
from __future__ import annotations

from typing import Any

from ..database.repositories import CandidatureRepository, PosteRepository, ScoreRepository
from . import coffre
from .erreurs import ErreurService, ErreurValidation, Introuvable, SessionRequise
from .traitement import TraitementService

TAILLE_TOP = 10
STATUTS_CLASSEMENT = ("a_traiter", "classe", "a_verifier", "non_classe")
STATUTS_LECTURE = ("en_attente", "lue", "illisible")
TAILLE_PAGE_MAX = 200


class CandidaturesService:
    def __init__(
        self,
        candidatures: CandidatureRepository,
        scores: ScoreRepository,
        postes: PosteRepository,
        traitement: TraitementService,
    ) -> None:
        self.candidatures = candidatures
        self.scores = scores
        self.postes = postes
        self.traitement = traitement

    def lister(
        self,
        statut: str | None = None,
        lecture: str | None = None,
        poste_id: int | None = None,
        limite: int = 50,
        decalage: int = 0,
    ) -> dict[str, Any]:
        if statut is not None and statut not in STATUTS_CLASSEMENT:
            raise ErreurValidation({"statut": "Statut inconnu."})
        if lecture is not None and lecture not in STATUTS_LECTURE:
            raise ErreurValidation({"lecture": "Statut de lecture inconnu."})
        limite = max(1, min(limite, TAILLE_PAGE_MAX))
        elements, total = self.candidatures.lister(statut, lecture, poste_id, limite, max(0, decalage))
        return {"elements": [_resume(e) for e in elements], "total": total, "compteurs": self.candidatures.compter()}

    def consulter(self, candidature_id: int) -> dict[str, Any]:
        candidature = self._get(candidature_id)
        extraction = candidature["extraction"] or {}
        scores = self.scores.pour_candidature(candidature_id)
        assigne = next((s for s in scores if s["poste_id"] == candidature["poste_id"]), None)
        poste = self.postes.get(candidature["poste_id"]) if candidature["poste_id"] else None
        return {
            **_resume({**candidature, "poste_intitule": poste["intitule"] if poste else None, "score": assigne["score"] if assigne else None}),
            "corps": candidature["corps"],
            "pieces_jointes": [{"nom": p["nom"], "chemin": p["chemin"]} for p in candidature["pieces_jointes"] or []],
            "fichier_cv": candidature["fichier_cv"],
            "extraction": {
                "periodes": extraction.get("periodes", []),
                "diplome": extraction.get("diplome"),
                "section_experience_trouvee": extraction.get("section_experience_trouvee"),
                "sections": sorted((extraction.get("sections") or {}).keys()),
            },
            "scores": [
                {
                    "poste_id": s["poste_id"],
                    "poste_intitule": s["poste_intitule"],
                    "poste_statut": s["poste_statut"],
                    "score": s["score"],
                    "pertinence": s["pertinence"],
                    "adequation_ignoree": s["adequation_ignoree"],
                    "detail": s["detail"],
                }
                for s in scores
            ],
        }

    def assigner(self, candidature_id: int, poste_id: int | None) -> dict[str, Any]:
        """Choix du recruteur : il n'est jamais écrasé par un nouveau calcul. poste_id=None : « aucun poste »."""
        self._get(candidature_id)
        if poste_id is not None and self.postes.get(poste_id) is None:
            raise ErreurValidation({"poste_id": "Ce poste n'existe pas."})
        self.candidatures.maj(
            candidature_id,
            poste_id=poste_id,
            mode_assignation="manuel",
            statut_classement="classe" if poste_id is not None else "non_classe",
            motif_classement="Choisi par le recruteur." if poste_id is not None else "Aucun poste, selon le recruteur.",
        )
        self.traitement.noter_une(candidature_id)  # score pour ce poste, même s'il n'est pas actif
        return self.consulter(candidature_id)

    def rendre_automatique(self, candidature_id: int) -> dict[str, Any]:
        """Annule le choix manuel : INJARA reclasse la candidature."""
        self._get(candidature_id)
        self.candidatures.maj(candidature_id, mode_assignation=None, statut_classement="a_traiter", motif_classement=None)
        self.traitement.noter_une(candidature_id)
        return self.consulter(candidature_id)

    def relancer_lecture(self, candidature_id: int) -> dict[str, Any]:
        """Après avoir remplacé un fichier illisible, par exemple."""
        self._get(candidature_id)
        self.candidatures.maj(candidature_id, statut_lecture="en_attente")
        self.traitement.demander(f"relecture de la candidature {candidature_id}")
        return self.consulter(candidature_id)

    def top(self, poste_id: int) -> dict[str, Any]:
        poste = self.postes.get(poste_id)
        if poste is None:
            raise Introuvable("Ce poste n'existe pas ou a été supprimé.")
        lignes = self.scores.top(poste_id, TAILLE_TOP)
        return {
            "poste_id": poste_id,
            "taille": TAILLE_TOP,
            "total_rattachees": self.candidatures.compter_par_poste().get(poste_id, 0),
            "elements": [
                {**_resume(l["candidature"]), "score": l["score"], "pertinence": l["pertinence"], "detail": l["detail"], "adequation_ignoree": l["adequation_ignoree"]}
                for l in lignes
            ],
        }

    def etat(self) -> dict[str, Any]:
        return {**self.traitement.etat(), "compteurs": self.candidatures.compter()}

    def contenu_cv(self, candidature_id: int) -> tuple[str, bytes]:
        """Nom et contenu en clair du CV, déchiffré en mémoire pour être ouvert par le recruteur."""
        candidature = self._get(candidature_id)
        cle = self.traitement.cle()
        if cle is None:
            raise SessionRequise("Session expirée. Veuillez vous reconnecter.")
        try:
            return candidature["nom_fichier_cv"], coffre.lire_fichier(candidature["fichier_cv"], cle)
        except FileNotFoundError as exc:
            raise Introuvable("Fichier introuvable : il a peut-être été déplacé ou supprimé.") from exc
        except coffre.Indechiffrable as exc:
            raise ErreurService("Le fichier chiffré est endommagé : il ne peut pas être ouvert.") from exc

    def _get(self, candidature_id: int) -> dict[str, Any]:
        candidature = self.candidatures.get(candidature_id)
        if candidature is None:
            raise Introuvable("Cette candidature n'existe pas.")
        return candidature


def _resume(c: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": c["id"],
        "nom": c.get("nom") or c.get("expediteur_nom"),
        "email": c.get("email") or c.get("expediteur_email"),
        "telephone": c.get("telephone"),
        "source": c["source"],
        "objet": c.get("objet"),
        "recue_le": c["recue_le"],
        "nom_fichier_cv": c["nom_fichier_cv"],
        "statut_lecture": c["statut_lecture"],
        "motif_lecture": c.get("motif_lecture"),
        "experience_mois": c.get("experience_mois"),
        "stages_mois": c.get("stages_mois"),
        "diplome_niveau": c.get("diplome_niveau"),
        "poste_id": c.get("poste_id"),
        "poste_intitule": c.get("poste_intitule"),
        "statut_classement": c["statut_classement"],
        "mode_assignation": c.get("mode_assignation"),
        "motif_classement": c.get("motif_classement"),
        "score": c.get("score"),
    }
