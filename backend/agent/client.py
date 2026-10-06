"""Clients de messagerie : le vrai (API Gmail) et le faux (développement sans Gmail).

L'agent ne parle qu'à l'interface `MailClient` : il ignore s'il est branché sur
Gmail ou sur la version simulée. C'est ce qui permet de développer et tester
sans connexion, sans frontend, sans compte Google.
"""
from __future__ import annotations

import base64
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Protocol

from .parsing import detect_automatic, parse_sender

SUPPORTED_EXTENSIONS = {".pdf", ".docx"}
GMAIL_QUERY = "has:attachment (filename:pdf OR filename:docx) -in:trash"


@dataclass
class RawAttachment:
    attachment_id: str
    filename: str
    mime_type: str = ""
    size: int = 0


@dataclass
class RawMessage:
    id: str
    sender: str  # en-tête From brut
    subject: str
    received_at: datetime  # toujours en UTC
    attachments: list[RawAttachment] = field(default_factory=list)
    unread: bool = True
    automatic_reason: str | None = None  # rempli si l'email est automatique (newsletter, notification...)
    folder: str = "INBOX"


class MailClient(Protocol):
    def list_cv_messages(
        self, since: datetime | None, max_results: int, unread_only: bool = False, folder: str | None = None
    ) -> list[RawMessage]: ...

    def get_message(self, message_id: str) -> RawMessage | None: ...

    def download_attachment(self, message_id: str, attachment_id: str) -> bytes: ...


# --------------------------------------------------------------------------- #
# Vrai client Gmail
# --------------------------------------------------------------------------- #
class GmailApiClient:
    """Adaptateur autour du `service` retourné par connect_gmail()."""

    def __init__(self, service):
        self._svc = service
        # Rempli par l'agent : évite de re-télécharger les emails déjà traités.
        self.skip_filter: Callable[[str], bool] | None = None
        self.truncated = False  # vrai si la limite par synchro a été atteinte

    def account_email(self) -> str:
        try:
            return self._svc.users().getProfile(userId="me").execute().get("emailAddress", "")
        except Exception:
            return ""

    def audit_recent(self, since: datetime, limit: int = 30) -> dict:
        """Photo de la boîte telle que l'agent la voit : derniers emails (sans filtre) et TOUTES leurs pièces jointes."""
        resp = (
            self._svc.users().messages()
            .list(userId="me", q=f"after:{int(since.timestamp())} -in:trash", maxResults=limit)
            .execute()
        )
        messages = []
        for item in resp.get("messages", []):
            full = self._svc.users().messages().get(userId="me", id=item["id"], format="full").execute()
            payload = full.get("payload", {})
            headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
            names = [p["filename"] for p in self._walk(payload) if p.get("filename")]
            messages.append(
                {
                    "id": full["id"],
                    "received_at": datetime.fromtimestamp(int(full["internalDate"]) / 1000, tz=timezone.utc),
                    "sender": headers.get("from", ""),
                    "subject": headers.get("subject", ""),
                    "attachments": names,
                    "labels": full.get("labelIds", []),
                }
            )
        return {"folder": "Gmail (toute la boîte)", "folders": [], "total_in_folder": None, "messages": messages}

    def list_cv_messages(
        self, since: datetime | None, max_results: int = 200, unread_only: bool = False, folder: str | None = None
    ) -> list[RawMessage]:
        query = GMAIL_QUERY
        if folder:
            query += " in:inbox" if folder.upper() == "INBOX" else f" label:{folder.strip().replace(' ', '-')}"
        if unread_only:
            query += " is:unread"
        if since is not None:
            query += f" after:{int(since.timestamp())}"
        ids: list[str] = []
        page_token = None
        self.truncated = False
        while True:
            resp = (
                self._svc.users()
                .messages()
                .list(userId="me", q=query, maxResults=100, pageToken=page_token)
                .execute()
            )
            for item in resp.get("messages", []):
                if self.skip_filter and self.skip_filter(item["id"]):
                    continue  # déjà traité : on ne le re-télécharge pas
                if len(ids) >= max_results:
                    self.truncated = True
                    break
                ids.append(item["id"])
            page_token = resp.get("nextPageToken")
            if self.truncated or not page_token:
                break
        messages = []
        for message_id in ids:
            full = self._svc.users().messages().get(userId="me", id=message_id, format="full").execute()
            raw = self._to_raw(full)
            if raw.attachments:
                messages.append(raw)
        return messages

    def get_message(self, message_id: str) -> RawMessage | None:
        """Relit un email (les identifiants de pièces jointes Gmail peuvent changer d'un appel à l'autre)."""
        try:
            return self._to_raw(self._svc.users().messages().get(userId="me", id=message_id, format="full").execute())
        except Exception:
            return None

    def download_attachment(self, message_id: str, attachment_id: str) -> bytes:
        data = (
            self._svc.users()
            .messages()
            .attachments()
            .get(userId="me", messageId=message_id, id=attachment_id)
            .execute()["data"]
        )
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))

    @staticmethod
    def _walk(part: dict):
        yield part
        for sub in part.get("parts") or []:
            yield from GmailApiClient._walk(sub)

    @classmethod
    def _to_raw(cls, message: dict) -> RawMessage:
        payload = message.get("payload", {})
        headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
        attachments = []
        for part in cls._walk(payload):
            filename = part.get("filename") or ""
            body = part.get("body", {})
            if filename and body.get("attachmentId") and Path(filename).suffix.lower() in SUPPORTED_EXTENSIONS:
                attachments.append(
                    RawAttachment(body["attachmentId"], filename, part.get("mimeType", ""), body.get("size", 0))
                )
        received = datetime.fromtimestamp(int(message["internalDate"]) / 1000, tz=timezone.utc)
        return RawMessage(
            id=message["id"],
            sender=headers.get("from", ""),
            subject=headers.get("subject", ""),
            received_at=received,
            attachments=attachments,
            unread="UNREAD" in message.get("labelIds", []),
            automatic_reason=detect_automatic(headers, parse_sender(headers.get("from", ""))[1]),
        )


# --------------------------------------------------------------------------- #
# Faux client (mode démo / développement / tests)
# --------------------------------------------------------------------------- #
_DEMO_NAMES = [
    ("Aïcha Mballa", "aicha.mballa@gmail.com"),
    ("Jean-Paul Fotso", "jp.fotso@yahoo.fr"),
    ("Nadège Tchinda", "nadege.tchinda@gmail.com"),
    ("Brice Kamga", "brice.kamga@outlook.com"),
    ("Sandrine Ngo Bayiha", "sandrine.ngo@gmail.com"),
    ("Hervé Nkoulou", "herve.nkoulou@gmail.com"),
]
_DEMO_SUBJECTS = [
    "Candidature — Développeur Python",
    "Candidature spontanée — Comptable",
    "CV — Assistante de direction",
    "Postulation : Chargé de communication",
    "Candidature — Data Analyst",
]


def fake_cv_bytes(name: str, kind: str = "pdf", unique: bool = True) -> bytes:
    """Fabrique un faux CV (en-tête valide, contenu bidon). unique=False : contenu stable."""
    tag = f"{name}-{uuid.uuid4().hex}".encode() if unique else name.encode()
    if kind == "docx":
        return b"PK\x03\x04" + b"Injara demo CV " + tag
    return b"%PDF-1.4\n% Injara demo CV " + tag + b"\n%%EOF\n"


class FakeMailClient:
    """Boîte mail en mémoire. Parfaite pour développer sans Gmail ni frontend."""

    def __init__(self) -> None:
        self._messages: dict[str, RawMessage] = {}
        self._blobs: dict[tuple[str, str], bytes] = {}
        self.skip_filter: Callable[[str], bool] | None = None
        self.truncated = False

    def add_message(
        self,
        sender: str,
        subject: str,
        attachments: list[tuple[str, bytes]],
        received_at: datetime | None = None,
        message_id: str | None = None,
        unread: bool = True,
        automatic_reason: str | None = None,
        folder: str = "INBOX",
    ) -> RawMessage:
        message_id = message_id or uuid.uuid4().hex[:16]
        raws = []
        for index, (filename, content) in enumerate(attachments):
            attachment_id = f"att{index}-{message_id}"
            self._blobs[(message_id, attachment_id)] = content
            raws.append(RawAttachment(attachment_id, filename, "", len(content)))
        message = RawMessage(message_id, sender, subject, received_at or datetime.now(timezone.utc), raws, unread, automatic_reason, folder)
        self._messages[message_id] = message
        return message

    def add_random_message(self, sender_name: str | None = None, subject: str | None = None) -> RawMessage:
        name, address = random.choice(_DEMO_NAMES)
        if sender_name:
            name, address = sender_name, f"{sender_name.lower().replace(' ', '.')}@example.com"
        filename = f"CV_{name.replace(' ', '_')}.pdf"
        return self.add_message(
            f"{name} <{address}>",
            subject or random.choice(_DEMO_SUBJECTS),
            [(filename, fake_cv_bytes(name))],
        )

    @classmethod
    def with_demo_data(cls, count: int = 5) -> "FakeMailClient":
        client = cls()
        now = datetime.now(timezone.utc)
        for i in range(count):
            name, address = _DEMO_NAMES[i % len(_DEMO_NAMES)]
            kind = "docx" if i % 3 == 2 else "pdf"
            client.add_message(
                f"{name} <{address}>",
                _DEMO_SUBJECTS[i % len(_DEMO_SUBJECTS)],
                [(f"CV_{name.replace(' ', '_')}.{kind}", fake_cv_bytes(name, kind, unique=False))],
                received_at=now - timedelta(hours=i + 1),
                message_id=f"demo{i:04d}",  # identifiants stables : 2e lancement = 0 nouveau CV
            )
        return client

    def audit_recent(self, since: datetime, limit: int = 30) -> dict:
        recent = [m for m in self._messages.values() if m.received_at >= since][-limit:]
        return {
            "folder": "Boîte simulée",
            "folders": [],
            "total_in_folder": len(self._messages),
            "messages": [
                {"id": m.id, "received_at": m.received_at, "sender": m.sender, "subject": m.subject,
                 "attachments": [a.filename for a in m.attachments]}
                for m in recent
            ],
        }

    def mark_read(self, message_id: str) -> None:
        self._messages[message_id].unread = False

    # --- interface MailClient ---
    def get_message(self, message_id: str) -> RawMessage | None:
        return self._messages.get(message_id)

    def list_cv_messages(
        self, since: datetime | None, max_results: int = 200, unread_only: bool = False, folder: str | None = None
    ) -> list[RawMessage]:
        self.truncated = False
        found: list[RawMessage] = []
        for message in sorted(self._messages.values(), key=lambda m: m.received_at, reverse=True):
            if since is not None and message.received_at < since:
                continue
            if unread_only and not message.unread:
                continue
            if folder and message.folder.lower() != folder.lower():
                continue
            if self.skip_filter and self.skip_filter(message.id):
                continue
            if len(found) >= max_results:
                self.truncated = True
                break
            found.append(message)
        return found

    def download_attachment(self, message_id: str, attachment_id: str) -> bytes:
        return self._blobs[(message_id, attachment_id)]
