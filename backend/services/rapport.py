"""Rapport par candidat (module 7) : toutes les données du rapport PDF, en une seule réponse.

Le PDF lui-même est produit par Electron (gabarit HTML et webContents.printToPDF) : ce service ne fait que rassembler
les données déjà calculées (extraction, score, potentiel, décision). Rien n'est recalculé et le CV n'est pas relu.

Le rapport porte sur le poste assigné à la candidature ; sans poste assigné, sur le poste où elle obtient le meilleur
score, et le rapport le précise. Ce qui n'a pas été calculé (adéquation, potentiel, score) est indiqué explicitement.
La section « entretien » vaut None tant qu'il n'y a pas d'entretien : le gabarit ne l'affiche pas.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..database.repositories import CandidatureRepository, EntrepriseRepository, PosteRepository, ScoreRepository
from . import coffre
from .erreurs import Introuvable, SessionRequise

MENTION = "Les scores et indicateurs sont des aides à la décision. La décision appartient au recruteur."
NOMS_CRITERES = {
    "competences": "Compétences",
    "experience": "Expérience",
    "formation": "Formation",
    "adequation": "Adéquation globale",
}
NOMS_DECISIONS = {"a_examiner": "À examiner", "retenu": "Retenu", "en_attente": "En attente", "ecarte": "Écarté"}
MODES = {"reference": "Poste cité dans le mail", "automatique": "Classement automatique", "manuel": "Choix du recruteur"}
STATUTS = {"a_traiter": "En cours de traitement", "classe": "Classée", "a_verifier": "À vérifier", "non_classe": "Non classée"}


class RapportService:
    def __init__(
        self,
        candidatures: CandidatureRepository,
        scores: ScoreRepository,
        postes: PosteRepository,
        entreprise: EntrepriseRepository,
        cle,
    ) -> None:
        self.candidatures = candidatures
        self.scores = scores
        self.postes = postes
        self.entreprise = entreprise
        self.cle = cle  # clé de données de la session (note du recruteur chiffrée)

    def donnees(self, candidature_id: int) -> dict[str, Any]:
        candidature = self.candidatures.get(candidature_id)
        if candidature is None:
            raise Introuvable("Cette candidature n'existe pas.")
        scores = self.scores.pour_candidature(candidature_id)
        score, mention_poste = self._score_du_rapport(candidature, scores)
        poste = self.postes.get(score["poste_id"]) if score else self.postes.get(candidature["poste_id"]) if candidature["poste_id"] else None
        extraction = candidature["extraction"] or {}
        entreprise = self.entreprise.get() or {}
        return {
            "genere_le": datetime.now(timezone.utc).isoformat(),
            "entreprise": {"nom": entreprise.get("nom") or None, "ville": entreprise.get("ville")},
            "poste": _poste(poste, mention_poste),
            "candidat": {
                "nom": candidature["nom"] or candidature["expediteur_nom"],
                "email": candidature["email"] or candidature["expediteur_email"],
                "telephone": candidature["telephone"],
                "recue_le": candidature["recue_le"].isoformat() if candidature["recue_le"] else None,
                "fichier_cv": candidature["nom_fichier_cv"],
            },
            "lecture": {
                "statut": candidature["statut_lecture"],
                "motif": candidature["motif_lecture"],
            },
            "assignation": {
                "statut": candidature["statut_classement"],
                "statut_libelle": STATUTS.get(candidature["statut_classement"], candidature["statut_classement"]),
                "mode": candidature["mode_assignation"],
                "mode_libelle": MODES.get(candidature["mode_assignation"]),
                "motif": candidature["motif_classement"],
            },
            "score": _score(score),
            "competences": _competences(score),
            "experience": {
                "total_mois": candidature["experience_mois"],
                "stages_mois": candidature["stages_mois"],
                "periodes": [
                    {k: p.get(k) for k in ("debut", "fin", "en_cours", "mois", "stage")}
                    for p in extraction.get("periodes", [])
                ],
                "estimation": not extraction.get("section_experience_trouvee", True),
            },
            "diplome": {
                "niveau": candidature["diplome_niveau"],
                "ligne": (extraction.get("diplome") or {}).get("ligne"),
            },
            "potentiel": _potentiel(score),
            "decision": {
                "etat": candidature["decision"],
                "libelle": NOMS_DECISIONS.get(candidature["decision"], candidature["decision"]),
                "note": coffre.dechiffrer_texte(candidature["decision_note"], self._cle()),
                "le": candidature["decision_le"].isoformat() if candidature["decision_le"] else None,
            },
            "entretien": None,  # module entretien à venir : section masquée tant qu'elle est vide
            "mention": MENTION,
        }

    def _score_du_rapport(self, candidature: dict, scores: list[dict]) -> tuple[dict | None, str | None]:
        if candidature["poste_id"] is not None:
            assigne = next((s for s in scores if s["poste_id"] == candidature["poste_id"]), None)
            return assigne, None
        if not scores:
            return None, "Aucun poste assigné et aucun score calculé."
        meilleur = max(scores, key=lambda s: s["score"])
        return meilleur, "Aucun poste assigné : rapport établi pour le poste où la candidature obtient le meilleur score."

    def _cle(self) -> bytes:
        cle = self.cle()
        if cle is None:
            raise SessionRequise("Session expirée. Veuillez vous reconnecter.")
        return cle


def _poste(poste: dict | None, mention: str | None) -> dict[str, Any] | None:
    if poste is None:
        return {"intitule": None, "mention": mention} if mention else None
    return {
        "id": poste["id"],
        "intitule": poste["intitule"],
        "reference": poste["reference_interne"],
        "niveau_formation": poste["niveau_formation"],
        "experience_min_annees": poste["experience_min_annees"],
        "mention": mention,
    }


def _score(score: dict | None) -> dict[str, Any] | None:
    if score is None:
        return None
    criteres = (score["detail"] or {}).get("criteres", {})
    return {
        "valeur": score["score"],
        "adequation_calculee": not score["adequation_ignoree"],
        "mention_adequation": (
            "Adéquation globale non calculée (moteur d'analyse indisponible) : le score repose sur les trois autres "
            "critères, poids recalculés."
            if score["adequation_ignoree"] else None
        ),
        "criteres": [
            {
                "cle": cle,
                "nom": nom,
                "score": criteres.get(cle, {}).get("score"),
                "poids": criteres.get(cle, {}).get("poids"),
                "poids_demande": criteres.get(cle, {}).get("poids_demande"),
                "message": (criteres.get(cle, {}).get("detail") or {}).get("message"),
            }
            for cle, nom in NOMS_CRITERES.items()
        ],
    }


def _competences(score: dict | None) -> dict[str, list[str]] | None:
    if score is None:
        return None
    detail = ((score["detail"] or {}).get("criteres", {}).get("competences") or {}).get("detail") or {}
    trouvees = [t["competence"] if isinstance(t, dict) else t for t in detail.get("trouvees", [])]  # {competence, trouvee_sous}
    return {"trouvees": trouvees, "manquantes": list(detail.get("manquantes", []))}


def _potentiel(score: dict | None) -> dict[str, Any]:
    if score is None or not score.get("potentiel"):
        return {"calcule": False, "niveau": None, "justification": [], "recommandation": None}
    potentiel = score["potentiel"]
    return {
        "calcule": True,
        "niveau": potentiel["niveau"],
        "justification": potentiel["justification"],
        "signaux": [{k: s[k] for k in ("nom", "note", "evaluable", "phrase")} for s in potentiel["signaux"]],
        "recommandation": potentiel.get("recommandation"),
        "mention": "Indicateur fondé sur des règles, à apprécier par le recruteur.",
    }
