"""Import manuel de CV (bouton « Importer des CV » du frontend, ou dossier en ligne de commande).

Même registre et même dossier de stockage que les CV venus des emails : un CV
importé à la main puis reçu par email plus tard sera reconnu comme doublon.
Accepte des fichiers PDF / DOCX, et des archives ZIP qui en contiennent.
"""
from __future__ import annotations

import hashlib
import io
import logging
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

from .client import SUPPORTED_EXTENSIONS
from .ledger import Ledger
from .parsing import safe_filename
from .schemas import CVMetadata, ImportResult, RejectedFile

log = logging.getLogger("injara.gmail")

MAX_FILE_BYTES = 20 * 1024 * 1024  # un CV
MAX_ZIP_BYTES = 200 * 1024 * 1024  # une archive
MAX_ZIP_ENTRIES = 1000
MAX_ZIP_UNCOMPRESSED = 500 * 1024 * 1024  # protection contre les « bombes » zip


def looks_valid(extension: str, data: bytes) -> bool:
    """Vérifie que le contenu correspond à l'extension (un .pdf doit commencer par %PDF)."""
    if not data:
        return False
    if extension == ".pdf":
        return data.startswith(b"%PDF")
    if extension == ".docx":
        return data.startswith(b"PK")  # un .docx est une archive zip
    return False


def _expand(filename: str, data: bytes, rejected: list[RejectedFile]) -> Iterator[tuple[str, bytes]]:
    if Path(filename).suffix.lower() != ".zip":
        yield filename, data
        return
    if len(data) > MAX_ZIP_BYTES:
        rejected.append(RejectedFile(filename=filename, reason="archive trop volumineuse (max 200 Mo)"))
        return
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        rejected.append(RejectedFile(filename=filename, reason="archive ZIP invalide"))
        return
    entries = [i for i in archive.infolist() if not i.is_dir() and "__MACOSX" not in i.filename]
    if len(entries) > MAX_ZIP_ENTRIES or sum(i.file_size for i in entries) > MAX_ZIP_UNCOMPRESSED:
        rejected.append(RejectedFile(filename=filename, reason="archive trop volumineuse ou trop de fichiers"))
        return
    for info in entries:
        name = Path(info.filename).name
        if Path(name).suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue  # on ignore silencieusement les fichiers qui ne sont pas des CV (Thumbs.db...)
        try:
            yield name, archive.read(info)
        except Exception:
            rejected.append(RejectedFile(filename=name, reason="fichier illisible dans l'archive"))


def import_cv_files(ledger: Ledger, cv_dir: Path, files: Iterable[tuple[str, bytes]]) -> ImportResult:
    result = ImportResult()
    cv_dir = Path(cv_dir)
    for original_name, original_data in files:
        for name, data in _expand(original_name, original_data, result.rejected):
            extension = Path(name).suffix.lower()
            if extension not in SUPPORTED_EXTENSIONS:
                result.rejected.append(RejectedFile(filename=name, reason="format non pris en charge (PDF ou DOCX uniquement)"))
                continue
            if len(data) > MAX_FILE_BYTES:
                result.rejected.append(RejectedFile(filename=name, reason="fichier trop volumineux (max 20 Mo)"))
                continue
            if not looks_valid(extension, data):
                result.rejected.append(RejectedFile(filename=name, reason="fichier invalide ou corrompu"))
                continue
            digest = hashlib.sha256(data).hexdigest()
            if ledger.sha_exists(digest):
                result.duplicates_skipped += 1
                continue
            now = datetime.now(timezone.utc)
            cv_dir.mkdir(parents=True, exist_ok=True)
            target = cv_dir / f"{now:%Y%m%d}_upload_{digest[:8]}_{safe_filename(name)}"
            tmp = target.with_suffix(target.suffix + ".part")
            tmp.write_bytes(data)
            tmp.replace(target)  # écriture atomique
            cv = CVMetadata(
                message_id=f"upload-{digest[:16]}",
                attachment_id="0",
                filename=Path(name).name,
                saved_path=str(target),
                sender_name="",
                sender_email="",
                subject="Import manuel",
                received_at=now,
                size_bytes=len(data),
                sha256=digest,
                downloaded_at=now,
                source="upload",
            )
            if ledger.add_cv(cv):
                result.imported.append(cv)
            else:
                target.unlink(missing_ok=True)
                result.duplicates_skipped += 1
    return result
