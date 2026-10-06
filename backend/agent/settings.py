"""Configuration du Module 1, lue depuis les variables d'environnement (.env).

On ne touche pas à app/config.py (partagé avec l'équipe) : le module reste autonome.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]  # racine du dépôt


@dataclass(frozen=True)
class GmailSettings:
    mode: str  # "fake" (développement sans Gmail) ou "real"
    credentials_path: Path
    token_path: Path
    account_path: Path
    cv_dir: Path
    ledger_path: Path
    poll_minutes: float
    lookback_days: int
    max_results: int
    env_file: Path | None = None  # chemin du .env s'il existe
    sync_mode: str = "last_days"
    since_date: str | None = None
    unread_only: bool = False


def _path(env_name: str, default: str) -> Path:
    value = os.getenv(env_name) or default
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


def load_settings() -> GmailSettings:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT_DIR / ".env")
    except ImportError:  # python-dotenv est optionnel
        pass
    return GmailSettings(
        mode=os.getenv("GMAIL_MODE", "fake").lower(),
        credentials_path=_path("GMAIL_CREDENTIALS_PATH", "data/secrets/credentials.json"),
        token_path=_path("GMAIL_TOKEN_PATH", "data/secrets/token.json"),
        account_path=_path("MAIL_ACCOUNT_PATH", "data/secrets/account.json"),
        cv_dir=_path("CV_DIR", "data/cvs"),
        ledger_path=_path("GMAIL_LEDGER_PATH", "data/gmail_ledger.db"),
        poll_minutes=float(os.getenv("GMAIL_POLL_MINUTES", "5")),
        lookback_days=int(os.getenv("GMAIL_LOOKBACK_DAYS", "30")),
        max_results=int(os.getenv("GMAIL_MAX_RESULTS", "500")),
        env_file=(ROOT_DIR / ".env") if (ROOT_DIR / ".env").exists() else None,
        sync_mode=os.getenv("GMAIL_SYNC_MODE", "last_days").lower(),
        since_date=os.getenv("GMAIL_SINCE_DATE") or None,
        unread_only=os.getenv("GMAIL_UNREAD_ONLY", "false").lower() in ("1", "true", "yes", "oui"),
    )


def default_sync_config(settings: GmailSettings):
    """Règle de récupération par défaut, issue du .env (modifiable ensuite depuis l'application)."""
    import logging

    from .schemas import SyncConfig

    try:
        return SyncConfig(
            mode=settings.sync_mode,  # type: ignore[arg-type]
            days=settings.lookback_days,
            since_date=settings.since_date,  # type: ignore[arg-type]
            unread_only=settings.unread_only,
        )
    except ValueError as exc:
        logging.getLogger("injara.gmail").warning("Configuration .env invalide (%s) : valeurs par défaut utilisées.", exc)
        return SyncConfig()
