"""Gestion des clés de chiffrement des données locales.

- La clé de données (32 octets aléatoires) chiffrera plus tard les fichiers CV. Elle n'est jamais écrite en clair.
- Elle est stockée deux fois, chiffrée (AES-256-GCM) :
  * par une clé dérivée du mot de passe (argon2id, lent, car un mot de passe a peu d'entropie) ;
  * par une clé dérivée de la clé de récupération (HKDF-SHA256, suffisant car elle contient 160 bits aléatoires).
- Un chiffré se présente ainsi : nonce (12 octets) || texte chiffré + étiquette d'authentification.
"""
from __future__ import annotations

import base64
import secrets

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from ..config import KdfParams

TAILLE_CLE = 32
TAILLE_SEL = 16
TAILLE_NONCE = 12
_AAD = b"injara:cle-de-donnees:v1"


class CleInvalide(Exception):
    """Le secret fourni ne permet pas de déchiffrer la clé de données."""


def nouvelle_cle_de_donnees() -> bytes:
    return secrets.token_bytes(TAILLE_CLE)


def nouveau_sel() -> bytes:
    return secrets.token_bytes(TAILLE_SEL)


def nouvelle_cle_de_recuperation() -> str:
    """160 bits aléatoires en base32, par groupes de 4 : « ABCD-EFGH-… » (8 groupes)."""
    brut = base64.b32encode(secrets.token_bytes(20)).decode("ascii")
    return "-".join(brut[i : i + 4] for i in range(0, len(brut), 4))


def normaliser_cle_de_recuperation(saisie: str) -> str:
    """Tolère minuscules, espaces et tirets oubliés. Base32 n'utilise ni 0, ni 1, ni 8 : on les lit O, I et B."""
    brut = "".join(c for c in saisie.upper() if c.isalnum())
    brut = brut.replace("0", "O").replace("1", "I").replace("8", "B")
    return "-".join(brut[i : i + 4] for i in range(0, len(brut), 4))


def cle_depuis_mot_de_passe(mot_de_passe: str, sel: bytes, kdf: KdfParams) -> bytes:
    return hash_secret_raw(
        secret=mot_de_passe.encode("utf-8"),
        salt=sel,
        time_cost=kdf.time_cost,
        memory_cost=kdf.memory_cost_kib,
        parallelism=kdf.parallelism,
        hash_len=TAILLE_CLE,
        type=Type.ID,
    )


def cle_depuis_recuperation(cle_de_recuperation: str, sel: bytes) -> bytes:
    brut = normaliser_cle_de_recuperation(cle_de_recuperation).encode("ascii")
    return HKDF(algorithm=hashes.SHA256(), length=TAILLE_CLE, salt=sel, info=b"injara:recuperation:v1").derive(brut)


def envelopper(cle_de_donnees: bytes, cle_de_protection: bytes) -> bytes:
    nonce = secrets.token_bytes(TAILLE_NONCE)
    return nonce + AESGCM(cle_de_protection).encrypt(nonce, cle_de_donnees, _AAD)


def desenvelopper(chiffre: bytes, cle_de_protection: bytes) -> bytes:
    try:
        return AESGCM(cle_de_protection).decrypt(chiffre[:TAILLE_NONCE], chiffre[TAILLE_NONCE:], _AAD)
    except (InvalidTag, ValueError) as exc:
        raise CleInvalide() from exc
