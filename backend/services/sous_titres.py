"""Sous-titres de l'entretien, en différé : reçoit des extraits de son (quelques secondes), les transcrit avec Whisper.

Le son vient de l'interface du recruteur, une piste par personne (le micro du recruteur, la voix du candidat), ce qui
donne qui parle sans analyse de voix. Les sous-titres arrivent avec un retard (la durée de l'extrait plus le temps de calcul).
Comme l'analyse du regard : seulement pendant l'entretien et avec le consentement du candidat. Le son n'est pas conservé ;
seul le texte l'est, chiffré dans la transcription de l'entretien, ligne après ligne : « [mm:ss] Candidat : texte ».
"""
from __future__ import annotations

import threading
from typing import Any, Callable

from ..database.repositories import EntretienRepository
from ..ia.transcription import FREQUENCE, Transcripteur
from . import coffre
from .erreurs import Conflit, ErreurValidation, Introuvable, SessionRequise

LOCUTEURS = {"recruteur": "Recruteur", "candidat": "Candidat"}
DUREE_MAX_EXTRAIT = 30  # secondes
TAILLE_MAX_EXTRAIT = DUREE_MAX_EXTRAIT * FREQUENCE * 4  # flottants 32 bits
TAILLE_MIN_EXTRAIT = FREQUENCE * 4 // 2  # une demi-seconde


class SousTitresService:
    def __init__(self, entretiens: EntretienRepository, transcripteur: Transcripteur, cle: Callable[[], bytes | None]) -> None:
        self.entretiens = entretiens
        self.transcripteur = transcripteur
        self._cle = cle
        self._lock = threading.Lock()  # la transcription de l'entretien se complète ligne après ligne

    def disponible(self) -> bool:
        return self.transcripteur.disponible()

    def transcrire(self, entretien_id: int, locuteur: str, debut: float, audio: bytes) -> list[dict[str, Any]]:
        import numpy as np

        entretien = self.entretiens.get(entretien_id)
        if entretien is None:
            raise Introuvable("Entretien introuvable.")
        if entretien["statut"] != "en_cours":
            raise Conflit("Les sous-titres ne sont produits que pendant l'entretien.")
        if not entretien["consentement_enregistrement"]:
            raise Conflit("Le candidat n'a pas consenti à la transcription de son entretien.")
        if locuteur not in LOCUTEURS:
            raise ErreurValidation({"locuteur": "Locuteur inconnu."})
        if debut < 0:
            raise ErreurValidation({"debut": "Début invalide."})
        if len(audio) % 4 or not TAILLE_MIN_EXTRAIT <= len(audio) <= TAILLE_MAX_EXTRAIT:
            raise ErreurValidation({"audio": f"Extrait invalide : entre 0,5 et {DUREE_MAX_EXTRAIT} secondes de son (flottants 32 bits)."})
        pcm = np.frombuffer(audio, dtype="<f4")
        if not np.isfinite(pcm).all():
            raise ErreurValidation({"audio": "Son invalide."})

        segments = [
            {"locuteur": locuteur, "debut": round(debut + s.debut, 1), "fin": round(debut + s.fin, 1), "texte": s.texte}
            for s in self.transcripteur.transcrire(pcm)
        ]
        if segments:
            self._ajouter(entretien_id, segments)
        return segments

    def _ajouter(self, entretien_id: int, segments: list[dict[str, Any]]) -> None:
        cle = self._cle()
        if cle is None:
            raise SessionRequise("Vous devez être connecté.")
        lignes = "\n".join(f"[{_horodatage(s['debut'])}] {LOCUTEURS[s['locuteur']]} : {s['texte']}" for s in segments)
        with self._lock:
            courant = coffre.dechiffrer_texte(self.entretiens.get(entretien_id)["transcription"], cle) or ""
            self.entretiens.maj(entretien_id, transcription=coffre.chiffrer_texte(f"{courant}\n{lignes}" if courant else lignes, cle))


def _horodatage(secondes: float) -> str:
    minutes, reste = divmod(int(secondes), 60)
    return f"{minutes:02d}:{reste:02d}"
