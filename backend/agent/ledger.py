"""Registre local (SQLite) des pièces jointes déjà traitées.

Sert à la gestion des doublons et à lister les CV récupérés. Fichier SQLite
propre au module : on ne touche pas à la base commune (database/models.py) tant
que le contrat avec le Team Lead n'est pas validé. Quand ce sera fait, il suffira
de remplacer cette classe par une qui écrit dans database/crud.py (mêmes méthodes).
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from .schemas import CVMetadata, IgnoredItem

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attachments_seen (
    message_id    TEXT NOT NULL,
    attachment_id TEXT NOT NULL,
    status        TEXT NOT NULL,          -- saved | duplicate | invalid
    PRIMARY KEY (message_id, attachment_id)
);
CREATE TABLE IF NOT EXISTS cvs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id    TEXT NOT NULL,
    attachment_id TEXT NOT NULL,
    sha256        TEXT NOT NULL UNIQUE,
    payload       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ignored (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id    TEXT NOT NULL,
    filename      TEXT NOT NULL,
    sender_name   TEXT NOT NULL,
    sender_email  TEXT NOT NULL,
    subject       TEXT NOT NULL,
    received_at   TEXT NOT NULL,
    rule          TEXT NOT NULL,
    reason        TEXT NOT NULL,
    UNIQUE (message_id, filename)
);
"""


class Ledger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._conn()) as conn:
            conn.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def is_seen(self, message_id: str, attachment_id: str) -> bool:
        with closing(self._conn()) as conn:
            row = conn.execute(
                "SELECT 1 FROM attachments_seen WHERE message_id=? AND attachment_id=?",
                (message_id, attachment_id),
            ).fetchone()
        return row is not None

    def has_message(self, message_id: str) -> bool:
        """Vrai si au moins une pièce jointe de cet email a déjà été traitée."""
        with closing(self._conn()) as conn:
            row = conn.execute("SELECT 1 FROM attachments_seen WHERE message_id=? LIMIT 1", (message_id,)).fetchone()
        return row is not None

    def seen_status(self, message_id: str, attachment_id: str) -> str | None:
        with closing(self._conn()) as conn:
            row = conn.execute(
                "SELECT status FROM attachments_seen WHERE message_id=? AND attachment_id=?", (message_id, attachment_id)
            ).fetchone()
        return row[0] if row else None

    def cv_by_sha(self, sha256: str) -> CVMetadata | None:
        with closing(self._conn()) as conn:
            row = conn.execute("SELECT payload FROM cvs WHERE sha256=?", (sha256,)).fetchone()
        return CVMetadata.model_validate_json(row[0]) if row else None

    def delete_state(self, key: str) -> None:
        with closing(self._conn()) as conn, conn:
            conn.execute("DELETE FROM state WHERE key=?", (key,))

    def sha_exists(self, sha256: str) -> bool:
        with closing(self._conn()) as conn:
            return conn.execute("SELECT 1 FROM cvs WHERE sha256=?", (sha256,)).fetchone() is not None

    def mark_seen(self, message_id: str, attachment_id: str, status: str) -> None:
        with closing(self._conn()) as conn, conn:
            conn.execute(
                "INSERT OR REPLACE INTO attachments_seen VALUES (?,?,?)",
                (message_id, attachment_id, status),
            )

    def add_cv(self, cv: CVMetadata) -> bool:
        """Enregistre un CV. Retourne False si le même fichier existe déjà."""
        try:
            with closing(self._conn()) as conn, conn:
                conn.execute(
                    "INSERT INTO cvs (message_id, attachment_id, sha256, payload) VALUES (?,?,?,?)",
                    (cv.message_id, cv.attachment_id, cv.sha256, cv.model_dump_json()),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO attachments_seen VALUES (?,?, 'saved')",
                    (cv.message_id, cv.attachment_id),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def list_cvs(self, limit: int = 50, offset: int = 0) -> list[CVMetadata]:
        with closing(self._conn()) as conn:
            rows = conn.execute(
                "SELECT payload FROM cvs ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
        return [CVMetadata.model_validate_json(r[0]) for r in rows]

    def count_cvs(self) -> int:
        with closing(self._conn()) as conn:
            return conn.execute("SELECT COUNT(*) FROM cvs").fetchone()[0]

    def get_state(self, key: str) -> str | None:
        with closing(self._conn()) as conn:
            row = conn.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def set_state(self, key: str, value: str) -> None:
        with closing(self._conn()) as conn, conn:
            conn.execute("INSERT OR REPLACE INTO state VALUES (?,?)", (key, value))

    # ------------------------------------------------------- emails ignorés
    def upsert_ignored(self, item: dict) -> None:
        with closing(self._conn()) as conn, conn:
            conn.execute(
                """INSERT INTO ignored (message_id, filename, sender_name, sender_email, subject, received_at, rule, reason)
                   VALUES (:message_id, :filename, :sender_name, :sender_email, :subject, :received_at, :rule, :reason)
                   ON CONFLICT(message_id, filename) DO UPDATE SET
                     sender_name=excluded.sender_name, sender_email=excluded.sender_email, subject=excluded.subject,
                     rule=excluded.rule, reason=excluded.reason""",
                item,
            )

    @staticmethod
    def _ignored_from_row(row) -> IgnoredItem:
        return IgnoredItem(
            id=row[0], filename=row[2], sender_name=row[3], sender_email=row[4], subject=row[5],
            received_at=row[6], rule=row[7], reason=row[8],
        )

    def list_ignored(self, limit: int = 50, offset: int = 0) -> list[IgnoredItem]:
        with closing(self._conn()) as conn:
            rows = conn.execute("SELECT * FROM ignored ORDER BY received_at DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        return [self._ignored_from_row(r) for r in rows]

    def count_ignored(self) -> int:
        with closing(self._conn()) as conn:
            return conn.execute("SELECT COUNT(*) FROM ignored").fetchone()[0]

    def get_ignored(self, ignored_id: int) -> tuple[IgnoredItem, str] | None:
        """Retourne (élément, message_id) ou None."""
        with closing(self._conn()) as conn:
            row = conn.execute("SELECT * FROM ignored WHERE id=?", (ignored_id,)).fetchone()
        return (self._ignored_from_row(row), row[1]) if row else None

    def delete_ignored(self, message_id: str, filename: str) -> None:
        with closing(self._conn()) as conn, conn:
            conn.execute("DELETE FROM ignored WHERE message_id=? AND filename=?", (message_id, filename))
