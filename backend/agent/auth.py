"""Authentification OAuth2 Gmail (lecture seule).

Le mot de passe du recruteur n'est jamais vu ni stocké : seul un jeton OAuth2
(token.json, ignoré par git) est conservé localement.
"""
from __future__ import annotations

import logging
from pathlib import Path

from .errors import GmailAuthRequired

log = logging.getLogger("injara.gmail")

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _save_token(creds, token_path: Path) -> None:
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    try:
        token_path.chmod(0o600)
    except OSError:  # pas supporté sous Windows : sans importance
        pass


def connect_gmail(credentials_path: Path, token_path: Path, interactive: bool = True):
    """Retourne un service Gmail authentifié.

    interactive=False : n'ouvre jamais le navigateur (utilisé au démarrage pour
    restaurer une session existante). Lève GmailAuthRequired si une connexion
    manuelle est nécessaire.
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise GmailAuthRequired(
            "Bibliothèques Google manquantes : pip install google-auth-oauthlib google-api-python-client"
        ) from exc

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and not creds.valid and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds, token_path)
        except Exception as exc:  # jeton révoqué ou expiré
            log.warning("Rafraîchissement du jeton Gmail impossible : %s", exc)
            creds = None

    if not creds or not creds.valid:
        if not interactive:
            raise GmailAuthRequired("Connexion Gmail requise.")
        if not credentials_path.exists():
            raise GmailAuthRequired(f"Fichier credentials.json introuvable : {credentials_path}")
        flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
        creds = flow.run_local_server(port=0)  # ouvre le navigateur du recruteur
        _save_token(creds, token_path)

    return build("gmail", "v1", credentials=creds, cache_discovery=False)


# Nom prévu dans la répartition des tâches
connecter_gmail = connect_gmail


def forget_token(token_path: Path) -> None:
    """Déconnexion : supprime le jeton local."""
    token_path.unlink(missing_ok=True)
