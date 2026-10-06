"""Petites règles de validation partagées par les services."""
from __future__ import annotations

import re

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TELEPHONE = re.compile(r"^\+?[0-9 ().-]{6,25}$")


def texte(valeur: str | None) -> str | None:
    """Supprime les espaces superflus ; une chaîne vide devient None."""
    if valeur is None:
        return None
    valeur = valeur.strip()
    return valeur or None


def liste(valeurs: list[str] | None) -> list[str]:
    """Nettoie une liste saisie : espaces retirés, entrées vides et doublons (sans tenir compte de la casse) supprimés."""
    resultat: list[str] = []
    vus: set[str] = set()
    for v in valeurs or []:
        v = v.strip()
        if v and v.lower() not in vus:
            vus.add(v.lower())
            resultat.append(v)
    return resultat


def email_valide(valeur: str) -> bool:
    return len(valeur) <= 254 and bool(_EMAIL.match(valeur))


def telephone_valide(valeur: str) -> bool:
    return bool(_TELEPHONE.match(valeur))
