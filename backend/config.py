"""Configuration du backend INJARA, lue depuis l'environnement.

Electron fournit INJARA_TOKEN (jeton de lancement) et INJARA_DATA_DIR (dossier des données de l'utilisateur).
En développement sans Electron, les données vont dans ./data à la racine du dépôt.

GMAIL_MODE (variable d'environnement ou fichier .env à la racine) choisit le mode de l'agent mail :
« real » par défaut (vraie boîte mail), « fake » pour une boîte de démonstration.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class KdfParams:
    """Coût argon2id pour dériver une clé depuis le mot de passe (valeurs OWASP par défaut)."""

    time_cost: int = 3
    memory_cost_kib: int = 64 * 1024
    parallelism: int = 4


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    token: str
    kdf: KdfParams = KdfParams()
    mode_agent: str = "real"
    dossier_modeles: Path | None = None  # None : INJARA_MODELES_DIR, sinon ./modeles

    @property
    def database_url(self) -> str:
        return f"sqlite:///{(self.data_dir / 'injara.db').as_posix()}"


MIN_TOKEN_LENGTH = 32


def load_settings() -> Settings:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT_DIR / ".env")  # n'écrase pas les variables déjà définies
    except ImportError:
        pass
    data_dir = Path(os.getenv("INJARA_DATA_DIR") or ROOT_DIR / "data")
    mode_agent = os.getenv("GMAIL_MODE", "real").strip().lower()
    return Settings(data_dir=data_dir, token=os.getenv("INJARA_TOKEN", ""), mode_agent=mode_agent)
