"""Tests de l'import manuel de CV (upload de fichiers et d'archives ZIP)."""
import io
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.agent import GmailAgent
from backend.agent import importer
from backend.agent.api import router, set_agent
from backend.agent.client import FakeMailClient, fake_cv_bytes
from backend.agent.ledger import Ledger


@pytest.fixture
def agent(tmp_path):
    return GmailAgent(ledger=Ledger(tmp_path / "l.db"), cv_dir=tmp_path / "cvs", mode="real")  # aucune boîte connectée


def make_zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return buf.getvalue()


def test_import_works_without_any_mail_connection(agent):
    result = agent.import_files([("cv1.pdf", fake_cv_bytes("a")), ("cv2.docx", fake_cv_bytes("b", "docx"))])
    assert len(result.imported) == 2 and not agent.connected
    assert all(cv.source == "upload" for cv in result.imported)
    assert agent.ledger.count_cvs() == 2


def test_duplicates_invalid_and_wrong_formats(agent):
    same = fake_cv_bytes("a")
    result = agent.import_files(
        [("a.pdf", same), ("a_copie.pdf", same), ("faux.pdf", b"pas un pdf"), ("photo.png", b"\x89PNG"), ("vide.pdf", b"")]
    )
    assert len(result.imported) == 1 and result.duplicates_skipped == 1
    reasons = {r.filename: r.reason for r in result.rejected}
    assert set(reasons) == {"faux.pdf", "photo.png", "vide.pdf"}
    assert "non pris en charge" in reasons["photo.png"]


def test_zip_archive_is_expanded(agent):
    archive = make_zip(
        {
            "candidats/jean.pdf": fake_cv_bytes("jean"),
            "candidats/marie.docx": fake_cv_bytes("marie", "docx"),
            "candidats/Thumbs.db": b"x",
            "__MACOSX/._jean.pdf": b"x",
        }
    )
    result = agent.import_files([("lot.zip", archive)])
    assert sorted(cv.filename for cv in result.imported) == ["jean.pdf", "marie.docx"]


def test_bad_or_oversized_zip_is_rejected(agent, monkeypatch):
    assert agent.import_files([("casse.zip", b"PK pas une archive")]).rejected[0].reason == "archive ZIP invalide"
    monkeypatch.setattr(importer, "MAX_ZIP_ENTRIES", 2)
    archive = make_zip({f"{i}.pdf": fake_cv_bytes(str(i)) for i in range(3)})
    result = agent.import_files([("trop.zip", archive)])
    assert result.imported == [] and "trop" in result.rejected[0].reason


def test_oversized_file_is_rejected(agent, monkeypatch):
    monkeypatch.setattr(importer, "MAX_FILE_BYTES", 10)
    result = agent.import_files([("gros.pdf", fake_cv_bytes("a"))])
    assert result.imported == [] and "volumineux" in result.rejected[0].reason


def test_uploaded_cv_received_later_by_email_is_a_duplicate(tmp_path):
    fake = FakeMailClient()
    agent = GmailAgent(ledger=Ledger(tmp_path / "l.db"), cv_dir=tmp_path / "cvs", mode="fake", client=fake)
    content = fake_cv_bytes("meme")
    agent.import_files([("cv.pdf", content)])
    fake.add_message("A <a@x.cm>", "Candidature", [("cv.pdf", content)])
    result = agent.sync_once()
    assert result.new_cvs == [] and result.duplicates_skipped == 1


def test_import_publishes_an_event(agent):
    agent.import_files([("cv.pdf", fake_cv_bytes("a"))])
    event = agent.events_since(0)[0]
    assert event.type == "new_cvs" and event.data["source"] == "upload"


def test_api_upload_multiple_files_and_zip(agent):
    set_agent(agent)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    files = [
        ("files", ("cv1.pdf", fake_cv_bytes("a"), "application/pdf")),
        ("files", ("lot.zip", make_zip({"b.pdf": fake_cv_bytes("b")}), "application/zip")),
        ("files", ("note.txt", b"bonjour", "text/plain")),
    ]
    response = client.post("/gmail/cvs/upload", files=files)
    assert response.status_code == 200
    body = response.json()
    assert len(body["imported"]) == 2 and body["rejected"][0]["filename"] == "note.txt"
    cvs = client.get("/gmail/cvs").json()
    assert len(cvs) == 2 and {c["source"] for c in cvs} == {"upload"}
    set_agent(None)
