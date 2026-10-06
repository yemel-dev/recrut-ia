"""Client IMAP : pour tout hébergeur mail (OVH, o2switch, serveur pro, Yahoo, Gmail perso...).

Même interface que GmailApiClient : l'agent n'y voit aucune différence.
Lecture seule : la boîte est ouverte en `readonly`, aucun email n'est marqué « lu »
ni modifié.
"""
from __future__ import annotations

import email
import imaplib
import logging
import re
from datetime import datetime, timezone
from email import policy
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Callable

from .client import SUPPORTED_EXTENSIONS, RawAttachment, RawMessage
from .parsing import detect_automatic, parse_sender
from .errors import ImapAuthError, ImapConnectionError

log = logging.getLogger("injara.gmail")

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_CANDIDATE = re.compile(r"\.(pdf|docx)\b")


def _quote_folder(name: str) -> str:
    """Met entre guillemets un nom de dossier qui contient des espaces (ex. « Mes candidatures »)."""
    if " " in name and not name.startswith('"'):
        return f'"{name}"'
    return name


def _imap_date(moment: datetime) -> str:
    """Date au format IMAP (ex. 04-Oct-2026), sans dépendre de la langue du système."""
    return f"{moment.day:02d}-{_MONTHS[moment.month - 1]}-{moment.year}"


class ImapMailClient:
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 993,
        folder: str = "INBOX",
        use_ssl: bool = True,
        timeout: float = 30,
    ) -> None:
        self.host, self.port, self.username = host, port, username
        self._password = password
        self.folder, self.use_ssl, self.timeout = folder, use_ssl, timeout
        # Rempli par l'agent : permet de ne pas re-télécharger les emails déjà traités.
        self.skip_filter: Callable[[str], bool] | None = None
        self._cache: dict[tuple[str, str], bytes] = {}
        self._no_cv: set[str] = set()
        self.truncated = False  # vrai si la limite par synchro a été atteinte
        self._current_folder = folder

    # ------------------------------------------------------------ connexion
    def _open(self):
        try:
            factory = imaplib.IMAP4_SSL if self.use_ssl else imaplib.IMAP4
            conn = factory(self.host, self.port, timeout=self.timeout)
        except (OSError, imaplib.IMAP4.error) as exc:
            raise ImapConnectionError(f"Serveur IMAP injoignable ({self.host}:{self.port}) : {exc}") from exc
        try:
            conn.login(self.username, self._password)
        except imaplib.IMAP4.error as exc:
            raise ImapAuthError(
                "Identifiants refusés. Vérifiez l'adresse complète et le mot de passe. "
                "Gmail et Yahoo exigent un mot de passe d'application ; OVH utilise le mot de passe de la boîte mail."
            ) from exc
        return conn

    def test_connection(self) -> None:
        """Vérifie serveur + identifiants + dossier. Lève ImapAuthError / ImapConnectionError."""
        conn = self._open()
        try:
            typ, _ = conn.select(self.folder, readonly=True)
            if typ != "OK":
                raise ImapConnectionError(f"Dossier introuvable : {self.folder}")
        finally:
            self._logout(conn)

    @staticmethod
    def _logout(conn) -> None:
        try:
            conn.logout()
        except Exception:
            pass

    # ------------------------------------------------------------- lecture
    def list_cv_messages(
        self, since: datetime | None, max_results: int = 200, unread_only: bool = False, folder: str | None = None
    ) -> list[RawMessage]:
        folder = folder or self.folder
        self._current_folder = folder
        conn = self._open()
        try:
            typ, _ = conn.select(_quote_folder(folder), readonly=True)
            if typ != "OK":
                raise ImapConnectionError(f"Dossier introuvable : {folder}")
            validity = self._uidvalidity(conn)
            criteria: list[str] = []
            if unread_only:
                criteria.append("UNSEEN")  # emails non lus
            if since is not None:
                criteria += ["SINCE", _imap_date(since)]
            criteria = criteria or ["ALL"]
            self.truncated = False
            fetched = 0
            typ, data = conn.uid("SEARCH", None, *criteria)
            uids = data[0].split() if typ == "OK" and data and data[0] else []
            self._cache.clear()
            messages: list[RawMessage] = []
            for uid in reversed(uids):  # du plus récent au plus ancien
                uid_s = uid.decode()
                message_id = f"imap-{validity}-{uid_s}"
                if message_id in self._no_cv or (self.skip_filter and self.skip_filter(message_id)):
                    continue
                if not self._maybe_has_cv(conn, uid_s):
                    self._no_cv.add(message_id)
                    continue
                if fetched >= max_results:
                    self.truncated = True
                    break
                fetched += 1
                parsed = self._parse(message_id, self._fetch_raw(conn, uid_s))
                if parsed is None:
                    self._no_cv.add(message_id)
                elif since is None or parsed.received_at >= since:
                    messages.append(parsed)
            return messages
        finally:
            self._logout(conn)

    def download_attachment(self, message_id: str, attachment_id: str) -> bytes:
        key = (message_id, attachment_id)
        if key not in self._cache:  # cas rare : le cache a été vidé, on re-télécharge l'email
            uid = message_id.rsplit("-", 1)[1]
            conn = self._open()
            try:
                conn.select(_quote_folder(self._current_folder), readonly=True)
                self._parse(message_id, self._fetch_raw(conn, uid))
            finally:
                self._logout(conn)
        return self._cache.pop(key)

    def get_message(self, message_id: str) -> RawMessage | None:
        """Relit un email par son identifiant (utilisé pour « Récupérer quand même »)."""
        try:
            uid = message_id.rsplit("-", 1)[1]
            conn = self._open()
            try:
                conn.select(_quote_folder(self._current_folder), readonly=True)
                return self._parse(message_id, self._fetch_raw(conn, uid))
            finally:
                self._logout(conn)
        except Exception:
            return None

    # ------------------------------------------------------------- internes
    @staticmethod
    def _uidvalidity(conn) -> str:
        try:
            _, data = conn.response("UIDVALIDITY")
            return data[0].decode() if data and data[0] else "0"
        except Exception:
            return "0"

    @staticmethod
    def _maybe_has_cv(conn, uid: str) -> bool:
        """Test rapide et léger (structure MIME seulement) avant de télécharger l'email entier."""
        typ, data = conn.uid("FETCH", uid, "(BODYSTRUCTURE)")
        if typ != "OK":
            return False
        chunks = []
        for item in data or []:
            if isinstance(item, tuple):
                chunks.extend(x for x in item if isinstance(x, bytes))
            elif isinstance(item, bytes):
                chunks.append(item)
        text = b" ".join(chunks).decode("utf-8", "ignore").lower()
        # Heuristique volontairement large : un nom de fichier encodé (=?utf-8?...), un type
        # « octet-stream » ou une pièce jointe sans extension visible ne doivent pas être manqués.
        return bool(
            _CANDIDATE.search(text)
            or "wordprocessingml" in text
            or '"application"' in text
            or '"attachment"' in text
            or "=?" in text
        )

    @staticmethod
    def _fetch_raw(conn, uid: str) -> bytes:
        typ, data = conn.uid("FETCH", uid, "(BODY.PEEK[])")  # PEEK : ne marque pas l'email comme lu
        if typ == "OK":
            for item in data or []:
                if isinstance(item, tuple):
                    return item[1]
        raise ImapConnectionError(f"Impossible de lire l'email UID {uid}")

    def _parse(self, message_id: str, raw: bytes) -> RawMessage | None:
        msg = email.message_from_bytes(raw, policy=policy.default)
        attachments: list[RawAttachment] = []
        for part in msg.walk():
            filename = part.get_filename()
            if not filename or Path(filename).suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            attachment_id = str(len(attachments))
            self._cache[(message_id, attachment_id)] = payload
            attachments.append(RawAttachment(attachment_id, filename, part.get_content_type(), len(payload)))
        if not attachments:
            return None
        try:
            received = parsedate_to_datetime(str(msg["Date"]))
            if received.tzinfo is None:
                received = received.replace(tzinfo=timezone.utc)
            received = received.astimezone(timezone.utc)
        except Exception:
            received = datetime.now(timezone.utc)
        sender = str(msg["From"] or "")
        automatic = detect_automatic({k: str(v) for k, v in msg.items()}, parse_sender(sender)[1])
        return RawMessage(message_id, sender, str(msg["Subject"] or ""), received, attachments, automatic_reason=automatic, folder=self._current_folder)

    # ---------------------------------------------------------------- audit
    def audit_recent(self, since: datetime, limit: int = 30) -> dict:
        """Photo de la boîte telle que l'agent la voit : dossiers, derniers emails, TOUTES les pièces jointes."""
        conn = self._open()
        try:
            folders = []
            try:
                typ, data = conn.list()
                for line in data or []:
                    text = line.decode("utf-8", "ignore") if isinstance(line, bytes) else str(line)
                    match = re.search(r'"([^"]*)"\s*$', text) or re.search(r"(\S+)\s*$", text)
                    if match:
                        folders.append(match.group(1))
            except Exception:
                pass
            typ, sel = conn.select(self.folder, readonly=True)
            if typ != "OK":
                raise ImapConnectionError(f"Dossier introuvable : {self.folder}")
            total = int(sel[0]) if sel and sel[0] else 0
            validity = self._uidvalidity(conn)
            typ, data = conn.uid("SEARCH", None, "SINCE", _imap_date(since))
            uids = data[0].split() if typ == "OK" and data and data[0] else []
            messages = []
            for uid in uids[-limit:]:
                uid_s = uid.decode()
                msg = email.message_from_bytes(self._fetch_raw(conn, uid_s), policy=policy.default)
                names = [p.get_filename() for p in msg.walk() if p.get_filename()]
                try:
                    received = parsedate_to_datetime(str(msg["Date"]))
                    received = received if received.tzinfo else received.replace(tzinfo=timezone.utc)
                    received = received.astimezone(timezone.utc)
                except Exception:
                    received = None
                messages.append(
                    {
                        "id": f"imap-{validity}-{uid_s}",
                        "received_at": received,
                        "sender": str(msg["From"] or ""),
                        "subject": str(msg["Subject"] or ""),
                        "attachments": names,
                    }
                )
            return {"folder": self.folder, "folders": folders, "total_in_folder": total, "messages": messages}
        finally:
            self._logout(conn)
