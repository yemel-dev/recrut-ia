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
from typing import Any, Callable

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
        self._chargement: threading.Thread | None = None

    @property
    def nom(self) -> str:
        return NOM_MODELE

    @property
    def disponible(self) -> bool:
        """Charge le modèle si besoin (jusqu'à deux minutes) : à éviter là où l'on ne doit pas attendre."""
        self._charger()
        return self._modele is not None

    @property
    def pret(self) -> bool:
        """Sans attendre : vrai seulement si le modèle est déjà chargé."""
        return self._modele is not None

    def precharger(self, quand_fini: Callable[[], None] | None = None) -> None:
        """Lance le chargement dans un fil à part ; `quand_fini` est appelé ensuite, même en cas d'échec."""
        with self._lock:
            if self._essaye or self._chargement is not None:
                return

            def charger() -> None:
                self._charger()
                if quand_fini is not None:
                    quand_fini()

            self._chargement = threading.Thread(target=charger, name="chargement-modele", daemon=True)
            self._chargement.start()

    def statut(self) -> dict[str, Any]:
        """État pour l'interface, sans attendre la fin d'un chargement en cours."""
        termine = self._essaye and not self._lock.locked()
        return {
            "disponible": self._modele is not None,
            "en_chargement": not termine,
            "modele": self.nom,
            "motif": self.motif_indisponible if termine else None,
        }

    def _charger(self) -> None:
        with self._lock:
            if self._essaye:
                return
            self._essaye = True
            poids = ("model.safetensors", "pytorch_model.bin")
            if not (self.chemin / "config.json").exists() or not any((self.chemin / p).exists() for p in poids):
                self.motif_indisponible = f"Modèle d'adéquation absent ({self.chemin})."
                log.warning("Adéquation désactivée : %s", self.motif_indisponible)
                return
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            # torch charge des DLL natives : si elles manquent, l'import peut figer tout le processus (constaté sous
            # Windows sans runtime Visual C++). On l'essaie donc d'abord dans un processus séparé, avec un délai.
            motif = sonder_import()
            if motif:
                self.motif_indisponible = motif
                log.warning("Adéquation désactivée : %s", motif)
                return
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                self.motif_indisponible = "Bibliothèque sentence-transformers absente (voir requirements-ia.txt)."
                log.warning("Adéquation désactivée : %s", self.motif_indisponible)
                return
            except OSError as exc:  # sous Windows : DLL de torch introuvable (runtime Visual C++ absent)
                self.motif_indisponible = (
                    "Moteur d'analyse impossible à charger (sous Windows, installez le runtime Microsoft Visual C++ "
                    f"2015-2022 x64) : {exc}"
                )
                log.warning("Adéquation désactivée : %s", self.motif_indisponible)
                return
            except Exception as exc:  # toute autre panne d'import : l'adéquation est ignorée, le reste fonctionne
                self.motif_indisponible = f"Moteur d'analyse impossible à charger : {exc}"
                log.exception("Import de sentence-transformers impossible")
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


DELAI_SONDE_S = 120
ARGUMENT_SONDE = "--sonde-moteur-analyse"


def sonder_import() -> str | None:
    """Essaie `import sentence_transformers` dans un processus séparé. Renvoie un motif d'échec, ou None si l'import marche."""
    import subprocess
    import sys

    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
    # Application installée (PyInstaller) : pas d'interpréteur, l'exécutable du backend fait lui-même l'essai.
    commande = [sys.executable, ARGUMENT_SONDE] if getattr(sys, "frozen", False) else [sys.executable, "-c", "import sentence_transformers"]
    try:
        resultat = subprocess.run(
            commande,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=DELAI_SONDE_S,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            **options,
        )
    except subprocess.TimeoutExpired:
        return f"Le moteur d'analyse ne se charge pas (délai de {DELAI_SONDE_S} s dépassé)."
    except OSError as exc:
        return f"Le moteur d'analyse ne peut pas être testé : {exc}"
    if resultat.returncode == 0:
        return None
    erreur = (resultat.stderr or "").strip().splitlines()
    derniere = erreur[-1] if erreur else f"code {resultat.returncode}"
    if "No module named" in derniere:
        return "Bibliothèque sentence-transformers absente (voir requirements-ia.txt)."
    if sys.platform == "win32" and ("DLL" in derniere or "WinError" in derniere):
        return f"Moteur d'analyse impossible à charger (installez le runtime Microsoft Visual C++ 2015-2022 x64) : {derniere}"
    return f"Moteur d'analyse impossible à charger : {derniere}"


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
