"""Transcription de la parole avec Whisper, hors ligne : sous-titres de l'entretien (module 3).

Le son arrive déjà décodé (mono, 16 kHz, flottants entre -1 et 1) : ni ffmpeg ni fichier intermédiaire. Le modèle est
chargé à la demande depuis le dossier des modèles (`modeles/whisper`). Whisper « invente » volontiers du texte sur
du silence ou du bruit : les passages silencieux ne sont pas transcrits et les formules typiques de ces
hallucinations sont écartées.

Variables d'environnement : INJARA_WHISPER_MODELE (défaut « small » ; « base » ou « tiny » si l'ordinateur est lent,
« medium » pour plus de précision), INJARA_WHISPER_LANGUE (défaut « fr » ; vide pour laisser Whisper la détecter).
"""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path

from ..services.erreurs import Indisponible

FREQUENCE = 16000
SEUIL_SILENCE = 0.005  # niveau efficace en dessous duquel on ne transcrit pas
NOM_MODELE_DEFAUT = "small"
PHRASES_PARASITES = (
    "sous-titres réalisés par", "sous-titrage st", "sous-titres par la communauté", "merci d'avoir regardé",
    "merci d'avoir regardé cette vidéo", "abonnez-vous", "amara.org", "thanks for watching",
)


@dataclass(frozen=True)
class Segment:
    debut: float  # secondes depuis le début de l'extrait
    fin: float
    texte: str


def nom_modele() -> str:
    return (os.getenv("INJARA_WHISPER_MODELE") or NOM_MODELE_DEFAUT).strip()


def langue() -> str | None:
    return (os.getenv("INJARA_WHISPER_LANGUE", "fr") or "").strip() or None


def dossier_whisper(dossier_modeles: Path) -> Path:
    return dossier_modeles / "whisper"


def niveau(pcm) -> float:
    import numpy as np

    return float(np.sqrt(np.mean(np.square(pcm)))) if len(pcm) else 0.0


class Transcripteur:
    def __init__(self, dossier: Path, nom: str | None = None) -> None:
        self.dossier = dossier
        self.nom = nom or nom_modele()
        self._modele = None
        self._lock = threading.Lock()

    def disponible(self) -> bool:
        return (self.dossier / f"{self.nom}.pt").is_file()

    def _charger(self):
        if self._modele is not None:
            return self._modele
        if not self.disponible():
            raise Indisponible(f"Le modèle de transcription « {self.nom} » est absent. Lancez : python -m backend.ia.telecharger_modele")
        try:
            import whisper
        except ImportError:
            raise Indisponible("Whisper n'est pas installé : pip install -r requirements-ia.txt") from None
        self._modele = whisper.load_model(self.nom, device="cpu", download_root=str(self.dossier))
        return self._modele

    def transcrire(self, pcm) -> list[Segment]:
        """Les phrases de l'extrait. `pcm` : tableau numpy float32, mono, 16 kHz."""
        if niveau(pcm) < SEUIL_SILENCE:
            return []
        with self._lock:  # un seul calcul à la fois : le modèle est lourd
            resultat = self._charger().transcribe(
                pcm, language=langue(), fp16=False, temperature=0.0, condition_on_previous_text=False,
                no_speech_threshold=0.6, verbose=None,
            )
        segments = []
        for s in resultat["segments"]:
            texte = s["text"].strip()
            if not texte or s["no_speech_prob"] > 0.6 or _parasite(texte):
                continue
            segments.append(Segment(float(s["start"]), float(s["end"]), texte))
        return segments


def _parasite(texte: str) -> bool:
    bas = texte.lower()
    return any(p in bas for p in PHRASES_PARASITES)


def telecharger_modele_whisper(dossier_modeles: Path) -> Path:
    """Télécharge le modèle Whisper choisi dans le dossier des modèles (de 75 Mo pour « tiny » à 1,5 Go pour « medium »)."""
    import whisper

    dossier = dossier_whisper(dossier_modeles)
    dossier.mkdir(parents=True, exist_ok=True)
    whisper.load_model(nom_modele(), device="cpu", download_root=str(dossier))
    return dossier / f"{nom_modele()}.pt"
