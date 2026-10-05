"""Comptes mail : détection du serveur IMAP et stockage sécurisé des identifiants.

Le mot de passe (d'application) n'est JAMAIS écrit dans un fichier du projet :
il va dans le coffre du système (Windows Credential Manager, macOS Keychain...)
via la bibliothèque `keyring`. Sans coffre disponible, il reste en mémoire
pour la session (le recruteur le ressaisit au prochain lancement).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

log = logging.getLogger("injara.gmail")


@dataclass
class ImapConfig:
    email: str
    host: str
    port: int = 993
    folder: str = "INBOX"


@dataclass(frozen=True)
class ImapPreset:
    host: str
    port: int
    help: str


_GOOGLE_HELP = (
    "Activez la validation en 2 étapes sur le compte Google, puis créez un « mot de passe d'application » "
    "dans les paramètres de sécurité du compte. Utilisez ce mot de passe à la place du mot de passe habituel."
)
_YAHOO_HELP = "Générez un mot de passe d'application dans les paramètres de sécurité du compte Yahoo."

# Hébergeurs grand public dont le serveur IMAP est connu d'avance.
PRESETS: dict[str, ImapPreset] = {
    "gmail.com": ImapPreset("imap.gmail.com", 993, _GOOGLE_HELP),
    "googlemail.com": ImapPreset("imap.gmail.com", 993, _GOOGLE_HELP),
    "yahoo.com": ImapPreset("imap.mail.yahoo.com", 993, _YAHOO_HELP),
    "yahoo.fr": ImapPreset("imap.mail.yahoo.com", 993, _YAHOO_HELP),
    "ymail.com": ImapPreset("imap.mail.yahoo.com", 993, _YAHOO_HELP),
}
# NB : Outlook/Hotmail volontairement absents. À ma connaissance Microsoft n'accepte plus
# les mots de passe d'application en IMAP pour ces comptes (OAuth exigé) : à vérifier avant d'ajouter.


def detect_imap(email: str) -> ImapPreset | None:
    """Devine le serveur IMAP d'après le domaine. None = l'utilisateur doit le saisir."""
    domain = email.rsplit("@", 1)[-1].strip().lower() if "@" in email else ""
    return PRESETS.get(domain)


# --------------------------------------------------------------------------- #
class SecretStore(Protocol):
    persistent: bool

    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str) -> None: ...
    def delete(self, key: str) -> None: ...


class MemorySecretStore:
    """Coffre en mémoire (session uniquement). Sert aussi aux tests."""

    persistent = False

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value

    def delete(self, key: str) -> None:
        self._data.pop(key, None)


class KeyringSecretStore:
    persistent = True
    SERVICE = "injara-ats"

    def __init__(self) -> None:
        import keyring

        self._kr = keyring

    def get(self, key: str) -> str | None:
        return self._kr.get_password(self.SERVICE, key)

    def set(self, key: str, value: str) -> None:
        self._kr.set_password(self.SERVICE, key, value)

    def delete(self, key: str) -> None:
        try:
            self._kr.delete_password(self.SERVICE, key)
        except Exception:
            pass


def default_secret_store() -> SecretStore:
    try:
        import keyring
        from keyring.backends.fail import Keyring as FailKeyring

        if isinstance(keyring.get_keyring(), FailKeyring):
            raise RuntimeError("aucun coffre disponible")
        return KeyringSecretStore()
    except Exception:
        log.warning("Pas de coffre de mots de passe système : le mot de passe IMAP ne sera pas conservé.")
        return MemorySecretStore()


# --------------------------------------------------------------------------- #
class AccountStore:
    """Mémorise quel compte est lié (type, adresse, serveur) pour se reconnecter au démarrage."""

    def __init__(self, path: Path, secrets: SecretStore | None = None) -> None:
        self.path = Path(path)
        self.secrets = secrets or default_secret_store()

    def save_oauth(self, email: str = "") -> None:
        self._write({"provider": "gmail_oauth", "email": email})

    def save_imap(self, cfg: ImapConfig, password: str) -> None:
        self._write({"provider": "imap", "email": cfg.email, "host": cfg.host, "port": cfg.port, "folder": cfg.folder})
        self.secrets.set(f"imap:{cfg.email}", password)

    def load(self) -> dict | None:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def load_imap(self) -> tuple[ImapConfig, str] | None:
        data = self.load()
        if not data or data.get("provider") != "imap":
            return None
        password = self.secrets.get(f"imap:{data['email']}")
        if not password:
            return None
        return ImapConfig(data["email"], data["host"], data.get("port", 993), data.get("folder", "INBOX")), password

    def clear(self) -> None:
        data = self.load()
        if data and data.get("provider") == "imap":
            self.secrets.delete(f"imap:{data['email']}")
        self.path.unlink(missing_ok=True)

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
