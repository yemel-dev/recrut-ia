"""Analyse du regard pendant un entretien : reçoit des images du candidat, relève les événements, calcule le score.

Les images viennent de l'interface du recruteur (la vidéo reçue du candidat, quelques images par seconde, réduites).
L'analyse n'est faite que si le candidat a consenti, seulement pendant l'entretien, et rien n'est conservé : ni les
images ni les mesures image par image. Il ne reste que les événements (alertes) et le bilan, à la clôture.
Le suivi en cours est gardé en mémoire : si INJARA redémarre en pleine séance, il repart de zéro.
"""
from __future__ import annotations

import threading
import time
from typing import Any

from ..database.repositories import EntretienRepository
from ..ia.regard import AnalyseurVisage, SuiviRegard
from .entretiens import _score_entretien
from .erreurs import Conflit, ErreurValidation, Introuvable

TAILLE_MAX_IMAGE = 512 * 1024


class RegardService:
    def __init__(self, entretiens: EntretienRepository, analyseur: AnalyseurVisage) -> None:
        self.entretiens = entretiens
        self.analyseur = analyseur
        self._suivis: dict[int, SuiviRegard] = {}
        self._lock = threading.Lock()

    def disponible(self) -> bool:
        return self.analyseur.disponible()

    def analyser_image(self, entretien_id: int, jpeg: bytes) -> dict[str, Any]:
        entretien = self.entretiens.get(entretien_id)
        if entretien is None:
            raise Introuvable("Entretien introuvable.")
        if entretien["statut"] != "en_cours":
            raise Conflit("L'analyse du regard n'est possible que pendant l'entretien.")
        if not entretien["consentement_enregistrement"]:
            raise Conflit("Le candidat n'a pas consenti à l'analyse de son entretien.")
        if not jpeg or len(jpeg) > TAILLE_MAX_IMAGE:
            raise ErreurValidation({"image": "Image vide ou trop volumineuse."})
        try:
            mesure = self.analyseur.analyser(jpeg)
        except ValueError as e:
            raise ErreurValidation({"image": str(e)}) from None
        with self._lock:
            suivi = self._suivis.setdefault(entretien_id, SuiviRegard())
            evenements = suivi.ajouter(mesure, time.monotonic())
            etat = suivi.etat
        for ev in evenements:
            self.entretiens.ajouter_alerte(entretien_id, ev.type, ev.details)
        return {"etat": etat, "mesure": mesure.en_dict(), "evenements": [{"type": e.type, **e.details} for e in evenements]}

    def cloturer(self, entretien_id: int) -> dict[str, Any] | None:
        """À la fin de l'entretien : enregistre le bilan et le score de regard, et en déduit le score d'entretien."""
        with self._lock:
            suivi = self._suivis.pop(entretien_id, None)
        score = suivi.score() if suivi else None
        if suivi is None or score is None:
            return None
        entretien = self.entretiens.get(entretien_id)
        if entretien is None:
            return None
        bilan = suivi.bilan()
        self.entretiens.maj(
            entretien_id,
            score_regard=score,
            bilan_regard=bilan,
            score_entretien=_score_entretien(score, entretien["score_contenu"], entretien["score_confiance"]),
        )
        return bilan
