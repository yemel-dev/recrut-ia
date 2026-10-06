"""Tests du Module 1 — aucun accès réseau, aucun compte Google nécessaire."""
import time
from email.header import Header

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.agent import GmailAgent, NotConnectedError
from backend.agent.api import router, set_agent
from backend.agent.client import FakeMailClient, fake_cv_bytes
from backend.agent.ledger import Ledger
from backend.agent.parsing import parse_sender, safe_filename


@pytest.fixture
def fake():
    return FakeMailClient()


@pytest.fixture
def agent(tmp_path, fake):
    return GmailAgent(ledger=Ledger(tmp_path / "ledger.db"), cv_dir=tmp_path / "cvs", mode="fake", client=fake)


def test_only_pdf_and_docx_are_downloaded(agent, fake):
    fake.add_message(
        "Jean Dupont <jean@x.cm>",
        "Candidature",
        [("cv.pdf", fake_cv_bytes("a")), ("cv.docx", fake_cv_bytes("b", "docx")), ("logo.png", b"\x89PNG")],
    )
    result = agent.sync_once()
    assert len(result.new_cvs) == 2
    assert all(__import__("pathlib").Path(cv.saved_path).exists() for cv in result.new_cvs)


def test_second_sync_finds_nothing_new(agent, fake):
    fake.add_random_message()
    assert len(agent.sync_once().new_cvs) == 1
    again = agent.sync_once()
    assert again.new_cvs == []
    assert again.duplicates_skipped == 1


def test_same_file_in_two_emails_is_a_duplicate(agent, fake):
    content = fake_cv_bytes("meme-cv")
    fake.add_message("A <a@x.cm>", "1", [("cv.pdf", content)])
    fake.add_message("B <b@x.cm>", "2", [("cv.pdf", content)])
    result = agent.sync_once()
    assert len(result.new_cvs) == 1
    assert result.duplicates_skipped == 1


def test_fake_pdf_is_rejected(agent, fake):
    fake.add_message("A <a@x.cm>", "1", [("cv.pdf", b"ceci n'est pas un pdf")])
    result = agent.sync_once()
    assert result.new_cvs == [] and result.invalid_skipped == 1


def test_metadata_is_extracted(agent, fake):
    fake.add_message("Aïcha Mballa <Aicha@Gmail.com>", "Candidature — Data Analyst", [("cv.pdf", fake_cv_bytes("x"))])
    cv = agent.sync_once().new_cvs[0]
    assert cv.sender_name == "Aïcha Mballa"
    assert cv.sender_email == "aicha@gmail.com"
    assert cv.subject == "Candidature — Data Analyst"
    assert agent.ledger.count_cvs() == 1


def test_parse_sender_variants():
    assert parse_sender("jean.dupont@gmail.com") == ("Jean Dupont", "jean.dupont@gmail.com")
    encoded = Header("Aïcha Mballa", "utf-8").encode() + " <aicha@gmail.com>"
    assert parse_sender(encoded) == ("Aïcha Mballa", "aicha@gmail.com")


def test_safe_filename_blocks_path_traversal():
    assert safe_filename("../../etc/passwd.pdf") == "passwd.pdf"
    assert safe_filename("C:\\Users\\x\\CV Final!!.PDF") == "CV Final.pdf"


def test_not_connected_raises(tmp_path):
    agent = GmailAgent(ledger=Ledger(tmp_path / "l.db"), cv_dir=tmp_path / "cvs", mode="real")
    with pytest.raises(NotConnectedError):
        agent.sync_once()


def test_events_are_published(agent, fake):
    fake.add_random_message()
    agent.sync_once()
    events = agent.events_since(0)
    assert [e.type for e in events] == ["new_cvs"]
    assert agent.events_since(events[-1].id) == []


def test_watcher_picks_up_new_emails(agent, fake):
    agent.start_watching(poll_minutes=0.005)  # ~0,3 s
    try:
        assert agent.watching
        fake.add_random_message()
        deadline = time.time() + 5
        while agent.ledger.count_cvs() == 0 and time.time() < deadline:
            time.sleep(0.1)
        assert agent.ledger.count_cvs() == 1
    finally:
        agent.stop_watching()
    assert not agent.watching


# ---- API : ce que le frontend utilisera ----
@pytest.fixture
def client(agent):
    set_agent(agent)
    app = FastAPI()
    app.include_router(router)
    yield TestClient(app)
    set_agent(None)


def test_api_full_flow(client, fake):
    assert client.get("/gmail/status").json()["connected"] is True
    client.post("/gmail/dev/simulate-email", json={"sender_name": "Brice Kamga"})
    sync = client.post("/gmail/sync").json()
    assert len(sync["new_cvs"]) == 1
    cvs = client.get("/gmail/cvs").json()
    assert cvs[0]["sender_name"] == "Brice Kamga"
    events = client.get("/gmail/events").json()
    assert events[0]["type"] == "new_cvs"
    assert client.get(f"/gmail/events?after_id={events[-1]['id']}").json() == []


def test_api_returns_409_when_not_connected(tmp_path):
    set_agent(GmailAgent(ledger=Ledger(tmp_path / "l.db"), cv_dir=tmp_path / "cvs", mode="real"))
    app = FastAPI()
    app.include_router(router)
    assert TestClient(app).post("/gmail/sync").status_code == 409
    set_agent(None)


# --- Extrait du corps du mail (ajout INJARA) ---------------------------------------------


def test_extrait_du_corps_texte_et_html():
    from backend.agent.parsing import BODY_EXCERPT_MAX, body_excerpt

    assert body_excerpt("Bonjour,\n\n  je postule   au poste DEV-12.") == "Bonjour, je postule au poste DEV-12."
    assert body_excerpt("", "<p>Poste&nbsp;<b>Comptable</b></p><style>p{}</style>") == "Poste Comptable"
    assert len(body_excerpt("x " * 5000)) == BODY_EXCERPT_MAX


def test_extrait_du_corps_gmail():
    import base64

    from backend.agent.client import GmailApiClient

    corps = base64.urlsafe_b64encode("Je postule au poste de comptable.".encode()).decode().rstrip("=")
    message = {
        "id": "m1", "internalDate": "1700000000000", "labelIds": [],
        "payload": {"headers": [{"name": "From", "value": "A <a@b.cm>"}, {"name": "Subject", "value": "CV"}], "parts": [
            {"mimeType": "text/plain", "body": {"data": corps}},
            {"filename": "cv.pdf", "mimeType": "application/pdf", "body": {"attachmentId": "x", "size": 10}},
        ]},
    }
    assert GmailApiClient._to_raw(message).body_excerpt == "Je postule au poste de comptable."


def test_extrait_du_corps_conserve_dans_le_registre(tmp_path):
    client = FakeMailClient()
    client.add_message("Awa <awa@x.cm>", "Candidature", [("cv.pdf", fake_cv_bytes("Awa"))], body="Poste visé : DEV-12")
    agent = GmailAgent(ledger=Ledger(tmp_path / "l.db"), cv_dir=tmp_path / "cvs", mode="fake", client=client)
    agent.sync_once()
    assert agent.ledger.list_cvs()[0].body_excerpt == "Poste visé : DEV-12"
