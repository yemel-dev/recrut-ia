"""Chiffrement des CV au repos, avec la clé de données de la session (AES-256-GCM).

- Un CV reçu par l'agent mail est écrit en clair par celui-ci (`<chemin>`). Le traitement le chiffre aussitôt dans
  `<chemin>.injara` puis efface le clair : la base garde le chemin d'origine, le fichier chiffré est à côté.
- Le texte extrait du CV (et des lettres) est chiffré en base, préfixé par `PREFIXE_TEXTE`.
- Un chiffré se présente ainsi : nonce (12 octets) || texte chiffré + étiquette d'authentification.
- Les fichiers et textes en clair d'avant le chiffrement restent lisibles ; ils sont chiffrés au passage suivant.
"""
from __future__ import annotations

import base64
import os
import secrets
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

EXTENSION = ".injara"
PREFIXE_TEXTE = "injara:v1:"
TAILLE_NONCE = 12
_AAD_FICHIER = b"injara:cv:v1"
_AAD_TEXTE = b"injara:texte:v1"
_AAD_MORCEAU = b"injara:enregistrement:v1"


class Indechiffrable(Exception):
    """Le contenu ne se déchiffre pas avec cette clé (fichier altéré ou d'un autre compte)."""


def _chiffrer(donnees: bytes, cle: bytes, aad: bytes) -> bytes:
    nonce = secrets.token_bytes(TAILLE_NONCE)
    return nonce + AESGCM(cle).encrypt(nonce, donnees, aad)


def _dechiffrer(chiffre: bytes, cle: bytes, aad: bytes) -> bytes:
    try:
        return AESGCM(cle).decrypt(chiffre[:TAILLE_NONCE], chiffre[TAILLE_NONCE:], aad)
    except (InvalidTag, ValueError) as exc:
        raise Indechiffrable("Contenu chiffré illisible avec cette clé.") from exc


# --- Fichiers ---------------------------------------------------------------------------------------------


def chemin_chiffre(chemin: str | Path) -> Path:
    return Path(f"{chemin}{EXTENSION}")


def chiffrer_fichier(chemin: str | Path, cle: bytes) -> bool:
    """Chiffre `chemin` dans `chemin.injara` puis efface le clair. Renvoie False s'il n'y avait rien à faire."""
    source = Path(chemin)
    if not source.is_file():
        return False
    cible = chemin_chiffre(source)
    temporaire = cible.with_name(cible.name + ".tmp")
    with open(temporaire, "wb") as f:
        f.write(_chiffrer(source.read_bytes(), cle, _AAD_FICHIER))
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporaire, cible)  # le chiffré complet existe avant que le clair disparaisse
    source.unlink()
    return True


def lire_fichier(chemin: str | Path, cle: bytes) -> bytes:
    """Contenu en clair du CV, qu'il soit déjà chiffré ou pas encore. Lève FileNotFoundError ou Indechiffrable."""
    cible = chemin_chiffre(chemin)
    if cible.is_file():
        return _dechiffrer(cible.read_bytes(), cle, _AAD_FICHIER)
    return Path(chemin).read_bytes()


# --- Enregistrements (écrits au fil de l'eau, jamais en clair sur le disque) ----------------------------------------


def ajouter_morceau(chemin: str | Path, donnees: bytes, cle: bytes) -> None:
    """Ajoute un morceau chiffré à la fin du fichier : longueur (4 octets) || nonce || chiffré."""
    chiffre = _chiffrer(donnees, cle, _AAD_MORCEAU)
    with open(chemin, "ab") as f:
        f.write(len(chiffre).to_bytes(4, "big") + chiffre)
        f.flush()
        os.fsync(f.fileno())


def lire_morceaux(chemin: str | Path, cle: bytes):
    """Morceaux en clair, dans l'ordre. Lève Indechiffrable si le fichier est altéré ou tronqué au milieu d'un morceau."""
    with open(chemin, "rb") as f:
        while entete := f.read(4):
            taille = int.from_bytes(entete, "big")
            chiffre = f.read(taille)
            if len(entete) < 4 or len(chiffre) < taille:
                raise Indechiffrable("Enregistrement incomplet.")
            yield _dechiffrer(chiffre, cle, _AAD_MORCEAU)


# --- Textes en base ---------------------------------------------------------------------------------------


def chiffrer_texte(texte: str | None, cle: bytes) -> str | None:
    if texte is None or texte.startswith(PREFIXE_TEXTE):
        return texte
    return PREFIXE_TEXTE + base64.b64encode(_chiffrer(texte.encode("utf-8"), cle, _AAD_TEXTE)).decode("ascii")


def dechiffrer_texte(valeur: str | None, cle: bytes) -> str | None:
    if valeur is None or not valeur.startswith(PREFIXE_TEXTE):
        return valeur  # texte enregistré avant le chiffrement
    return _dechiffrer(base64.b64decode(valeur[len(PREFIXE_TEXTE) :]), cle, _AAD_TEXTE).decode("utf-8")


def est_chiffre(valeur: str | None) -> bool:
    return valeur is None or valeur.startswith(PREFIXE_TEXTE)
