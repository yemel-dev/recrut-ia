"""Petites fonctions utilitaires de parsing (expéditeur, noms de fichiers)."""
from __future__ import annotations

import re
from email.header import decode_header, make_header
from email.utils import parseaddr
from pathlib import PurePosixPath


def decode_header_value(raw: str) -> str:
    """Décode un en-tête MIME (ex. '=?UTF-8?B?...?=') en texte lisible."""
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw)))
    except Exception:
        return raw


def parse_sender(raw: str) -> tuple[str, str]:
    """Retourne (nom, email) à partir d'un en-tête From.

    Si le nom est absent, on le déduit de l'adresse : jean.dupont@x.cm -> 'Jean Dupont'.
    """
    name, address = parseaddr(raw or "")
    name = decode_header_value(name).strip().strip('"')
    address = address.strip().lower()
    if not name and address:
        local = address.split("@")[0]
        name = re.sub(r"[._\-+]+", " ", local).strip().title()
    return name, address


def safe_filename(filename: str, max_len: int = 80) -> str:
    """Nettoie un nom de fichier venant d'un email (anti path-traversal inclus)."""
    base = filename.replace("\\", "/").split("/")[-1].strip()
    path = PurePosixPath(base)
    stem = re.sub(r"[^\w\- ()]+", "_", path.stem).strip(" ._") or "cv"
    return f"{stem[:max_len]}{path.suffix.lower()}"


_AUTO_LOCALPART = re.compile(r"(no[-_.]?reply|do[-_.]?not[-_.]?reply|mailer-daemon|postmaster)")


def detect_automatic(headers: dict[str, str], sender_email: str = "") -> str | None:
    """Repère un email automatique (newsletter, notification, réponse automatique).

    Retourne la raison (en français) ou None. Ne regarde que des en-têtes standards.
    """
    h = {k.lower(): str(v) for k, v in headers.items()}
    auto = h.get("auto-submitted", "").strip().lower()
    if auto and auto != "no":
        return f"réponse ou notification automatique (en-tête Auto-Submitted : {auto})"
    precedence = h.get("precedence", "").strip().lower()
    if precedence in {"bulk", "list", "junk", "auto_reply"}:
        return f"envoi en masse (en-tête Precedence : {precedence})"
    if "list-unsubscribe" in h or "list-id" in h:
        return "newsletter ou liste de diffusion (lien de désabonnement présent)"
    if "x-autoreply" in h or "x-autorespond" in h:
        return "réponse automatique"
    local = sender_email.split("@")[0].lower() if sender_email else ""
    if local and _AUTO_LOCALPART.fullmatch(local):
        return f"expéditeur automatique ({local}@…)"
    return None


def normalize_sender_rule(entry: str) -> str:
    """'  <NoReply@X.com> ' -> 'noreply@x.com' ; '@linkedin.com' -> 'linkedin.com'."""
    value = entry.strip().strip("<>").strip().lower()
    return value[1:] if value.startswith("@") else value


def sender_matches(rule: str, address: str) -> bool:
    """rule = adresse exacte (a@x.com) ou domaine (x.com, couvre aussi mail.x.com)."""
    address = address.strip().lower()
    if "@" in rule:
        return address == rule
    domain = address.rsplit("@", 1)[-1]
    return domain == rule or domain.endswith("." + rule)
