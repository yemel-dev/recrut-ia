"""Normalisation de texte partagée par l'analyse des CV."""
from __future__ import annotations

import re
import unicodedata

_TIRETS = re.compile(r"[‐‑‒–—―−]")
_APOSTROPHES = re.compile(r"[’‘`´]")
_ESPACES = re.compile(r"[ \t   ]+")


def sans_accents(texte: str) -> str:
    decompose = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c))


def normaliser(texte: str) -> str:
    """Minuscules, sans accents, tirets et apostrophes unifiés, espaces simples (les sauts de ligne sont gardés)."""
    texte = sans_accents(texte or "").lower()
    texte = _TIRETS.sub("-", texte)
    texte = _APOSTROPHES.sub("'", texte)
    return "\n".join(_ESPACES.sub(" ", ligne).strip() for ligne in texte.splitlines())


def lignes(texte: str) -> list[str]:
    """Lignes non vides, sans espaces superflus."""
    return [l.strip() for l in (texte or "").splitlines() if l.strip()]
