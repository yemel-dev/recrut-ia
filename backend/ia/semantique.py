"""Similarité sémantique (Sentence-BERT), utilisée pour le critère « adéquation globale ».

- Le modèle est chargé une seule fois, depuis le disque, sans accès réseau.
- S'il est absent (ou si sentence-transformers n'est pas installé), `disponible` vaut False avec un motif :
  l'adéquation est alors ignorée et les autres poids sont recalculés (voir scoring.py).
- Les vecteurs sont des listes de flottants normalisées : la similarité est un simple produit scalaire,
  calculable sans dépendance (le scoring reste pur).
"""
from __future__ import annotations

import logging
import math
import os
import threading
from array import array
from pathlib import Path

from ..config import ROOT_DIR

log = logging.getLogger("injara.ia.semantique")

NOM_MODELE = "paraphrase-multilingual-MiniLM-L12-v2"
DEPOT_MODELE = f"sentence-transformers/{NOM_MODELE}"
MOTS_PAR_MORCEAU = 90  # le modèle tronque à 128 jetons : on découpe les longs textes
MORCEAUX_MAX = 24


def dossier_modeles() -> Path:
    return Path(os.getenv("INJARA_MODELES_DIR") or ROOT_DIR / "modeles")


class ModeleSemantique:
    def __init__(self, chemin: Path | None = None) -> None:
        self.chemin = chemin or dossier_modeles() / NOM_MODELE
        self._modele = None
        self._essaye = False
        self.motif_indisponible: str | None = None
        self._lock = threading.Lock()

    @property
    def nom(self) -> str:
        return NOM_MODELE

    @property
    def disponible(self) -> bool:
        self._charger()
        return self._modele is not None

    def _charger(self) -> None:
        with self._lock:
            if self._essaye:
                return
            self._essaye = True
            if not (self.chemin / "config.json").exists():
                self.motif_indisponible = f"Modèle d'adéquation absent ({self.chemin})."
                log.warning("Adéquation désactivée : %s", self.motif_indisponible)
                return
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                self.motif_indisponible = "Bibliothèque sentence-transformers absente (voir requirements-ia.txt)."
                log.warning("Adéquation désactivée : %s", self.motif_indisponible)
                return
            try:
                self._modele = SentenceTransformer(str(self.chemin), device="cpu")
                log.info("Modèle d'adéquation chargé : %s", self.chemin)
            except Exception as exc:  # fichiers incomplets, version incompatible…
                self.motif_indisponible = f"Modèle d'adéquation illisible : {exc}"
                log.exception("Chargement du modèle d'adéquation impossible")

    def encoder(self, texte: str) -> list[float] | None:
        """Vecteur normalisé du texte (moyenne des morceaux), ou None si le modèle est indisponible."""
        if not self.disponible or not (texte or "").strip():
            return None
        mots = texte.split()
        morceaux = [" ".join(mots[i : i + MOTS_PAR_MORCEAU]) for i in range(0, len(mots), MOTS_PAR_MORCEAU)][:MORCEAUX_MAX]
        vecteurs = self._modele.encode(morceaux, normalize_embeddings=True, show_progress_bar=False)
        moyenne = [sum(colonne) / len(vecteurs) for colonne in zip(*vecteurs)]
        return normaliser_vecteur(moyenne)


def normaliser_vecteur(vecteur: list[float]) -> list[float]:
    norme = math.sqrt(sum(x * x for x in vecteur)) or 1.0
    return [float(x) / norme for x in vecteur]


def similarite(a: list[float], b: list[float]) -> float:
    """Cosinus entre deux vecteurs normalisés."""
    return sum(x * y for x, y in zip(a, b))


def en_octets(vecteur: list[float] | None) -> bytes | None:
    return array("f", vecteur).tobytes() if vecteur is not None else None


def depuis_octets(donnees: bytes | None) -> list[float] | None:
    if not donnees:
        return None
    vecteur = array("f")
    vecteur.frombytes(donnees)
    return list(vecteur)
