"""Connexion SQLite. Seul le paquet database/ ouvre des sessions SQLAlchemy."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .migrations import ajouter_colonnes_manquantes
from .models import Base


class Database:
    def __init__(self, url: str) -> None:
        self.engine = create_engine(url, connect_args={"check_same_thread": False})
        event.listen(self.engine, "connect", _sqlite_pragmas)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)
        ajouter_colonnes_manquantes(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Transaction : validée en sortie normale, annulée en cas d'exception."""
        with self._sessions() as session, session.begin():
            yield session

    def close(self) -> None:
        self.engine.dispose()


def _sqlite_pragmas(dbapi_connection, _record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()
