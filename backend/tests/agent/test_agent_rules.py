"""Règles d'exclusion, liste « Ignorés », aperçu, profils et écran de démarrage."""
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.agent import GmailAgent
from backend.agent.api import router, set_agent
from backend.agent.client import FakeMailClient, GmailApiClient, fake_cv_bytes
from backend.agent.imap_client import ImapMailClient, _quote_folder
from backend.agent.ledger import Ledger
from backend.agent.parsing import detect_automatic, sender_matches
from backend.agent.schemas import PROFILES, SyncConfig


@pytest.fixture
def fake():
    return FakeMailClient()


@pytest.fixture
def agent(tmp_path, fake):
    return GmailAgent(ledger=Ledger(tmp_path / "l.db"), cv_dir=tmp_path / "cvs", mode="fake", client=fake)


def add(fake, sender="Jean <jean@gmail.com>", subject="Candidature", content=None, filename="cv.pdf", **kw):
    return fake.add_message(sender, subject, [(filename, content or fake_cv_bytes(subject + sender))], **kw)


# ---------------------------------------------------------------- briques
def test_detect_automatic_headers_and_senders():
    assert "Auto-Submitted" in detect_automatic({"Auto-Submitted": "auto-replied"}, "a@x.com")
    assert detect_automatic({"Auto-Submitted": "no"}, "a@x.com") is None
    assert "Precedence" in detect_automatic({"Precedence": "bulk"}, "a@x.com")
    assert "désabonnement" in detect_automatic({"List-Unsubscribe": "<mailto:x>"}, "a@x.com")
    assert "automatique" in detect_automatic({}, "no-reply@linkedin.com")
    assert detect_automatic({"Subject": "Candidature"}, "jean.dupont@gmail.com") is None


def test_sender_rules_match_address_domain_and_subdomain():
    assert sender_matches("a@x.com", "A@X.com") and not sender_matches("a@x.com", "b@x.com")
    assert sender_matches("linkedin.com", "jobs@linkedin.com") and sender_matches("linkedin.com", "x@mail.linkedin.com")
    assert not sender_matches("linkedin.com", "x@notlinkedin.com")


def test_config_cleans_user_input():
    cfg = SyncConfig(ignored_senders=["  <NoReply@X.com> ", "@LinkedIn.com", "linkedin.com", ""], folder="  ")
    assert cfg.ignored_senders == ["noreply@x.com", "linkedin.com"] and cfg.folder is None
    with pytest.raises(ValueError):
        SyncConfig(allowed_extensions=[])


# ---------------------------------------------------------------- règles dans la synchro
def test_automatic_emails_are_ignored_and_listed(agent, fake):
    add(fake, subject="Newsletter", automatic_reason="newsletter ou liste de diffusion")
    add(fake, subject="Vraie candidature")
    result = agent.sync_once()
    assert [c.subject for c in result.new_cvs] == ["Vraie candidature"] and result.ignored_count == 1
    ignored = agent.ledger.list_ignored()
    assert len(ignored) == 1 and ignored[0].rule == "automatic" and "newsletter" in ignored[0].reason
    assert agent.status().ignored_count == 1


def test_automatic_filter_can_be_turned_off(agent, fake):
    add(fake, automatic_reason="newsletter")
    agent.update_config(SyncConfig(ignore_automatic=False))
    assert len(agent.sync_once().new_cvs) == 1


def test_ignored_senders_extensions_and_size(agent, fake):
    add(fake, sender="RH <rh@linkedin.com>", subject="Notif")
    add(fake, subject="Un docx", content=fake_cv_bytes("d", "docx"), filename="cv.docx")
    add(fake, subject="Trop gros", content=b"%PDF-1.4\n" + b"x" * 2_000_000, filename="gros.pdf")
    add(fake, subject="Normal")
    agent.update_config(SyncConfig(ignored_senders=["linkedin.com"], allowed_extensions=["pdf"], max_attachment_mb=1))
    result = agent.sync_once()
    assert [c.subject for c in result.new_cvs] == ["Normal"]
    assert {i.rule for i in agent.ledger.list_ignored()} == {"sender", "extension", "size"}


def test_folder_rule(agent, fake):
    add(fake, subject="Boite principale")
    add(fake, subject="Dans Candidatures", folder="Candidatures")
    agent.update_config(SyncConfig(folder="Candidatures"))
    assert [c.subject for c in agent.sync_once().new_cvs] == ["Dans Candidatures"]


# ---------------------------------------------------------------- liste « Ignorés »
def test_recover_ignored_imports_it_anyway(agent, fake):
    add(fake, subject="Auto mais utile", automatic_reason="newsletter")
    agent.sync_once()
    item = agent.ledger.list_ignored()[0]
    outcome = agent.recover_ignored(item.id)
    assert outcome.imported is not None and outcome.imported.subject == "Auto mais utile"
    assert agent.ledger.count_ignored() == 0 and agent.ledger.count_cvs() == 1


def test_recover_a_duplicate_clears_it_from_the_list(agent, fake):
    content = fake_cv_bytes("meme")
    add(fake, subject="Original", content=content)
    add(fake, subject="Copie auto", content=content, automatic_reason="newsletter")
    agent.sync_once()
    outcome = agent.recover_ignored(agent.ledger.list_ignored()[0].id)
    assert outcome.imported is None and "même contenu" in outcome.detail
    assert agent.ledger.count_ignored() == 0


def test_loosening_a_rule_imports_previously_ignored_emails(agent, fake):
    add(fake, sender="X <x@linkedin.com>", subject="Offre")
    agent.update_config(SyncConfig(ignored_senders=["linkedin.com"]))
    assert agent.sync_once().new_cvs == [] and agent.ledger.count_ignored() == 1
    agent.update_config(SyncConfig())  # on retire la règle : la période est rescannée
    assert len(agent.sync_once().new_cvs) == 1 and agent.ledger.count_ignored() == 0


# ---------------------------------------------------------------- aperçu avant import
def test_preview_counts_and_writes_nothing(agent, fake, tmp_path):
    add(fake, subject="A importer")
    add(fake, subject="Newsletter", automatic_reason="newsletter")
    add(fake, subject="Vieux", received_at=fake_now() - timedelta(days=90))
    report = agent.preview(SyncConfig(mode="last_days", days=30))
    assert (report.emails_with_cv, report.to_import, report.ignored) == (2, 1, 1)
    assert report.ignored_by_rule == {"automatic": 1}
    assert agent.ledger.count_cvs() == 0 and agent.ledger.count_ignored() == 0
    assert not (tmp_path / "cvs").exists()
    assert agent.sync_config.mode == "last_days" and agent.ledger.get_state(agent._cursor_key) is None
    assert agent.preview(SyncConfig(mode="all")).emails_with_cv == 3  # d'autres réglages, sans les enregistrer


def test_preview_shows_what_is_already_imported(agent, fake):
    add(fake, subject="Deja pris")
    agent.sync_once()
    assert agent.preview().already_imported == 1 and agent.preview().to_import == 0


def fake_now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- profils, avertissements, démarrage
def test_profiles_are_recognised_and_custom_detected():
    assert SyncConfig().profile == "prudent" and PROFILES["new_only"].config.profile == "new_only"
    assert PROFILES["everything"].config.profile == "everything"
    assert SyncConfig(ignored_senders=["x.com"]).profile == "custom"


def test_warnings_for_risky_settings():
    assert SyncConfig().warnings == []
    assert "non lu" in SyncConfig(unread_only=True).warnings[0]
    assert any("historique" in w for w in SyncConfig(mode="all").warnings)
    assert any("automatiques" in w for w in SyncConfig(ignore_automatic=False).warnings)


def test_setup_is_needed_until_the_recruiter_confirms(agent):
    assert agent.status().needs_setup is True
    agent.apply_profile("prudent")
    assert agent.status().needs_setup is False


def test_settings_survive_a_restart_including_rules(tmp_path, fake):
    ledger = Ledger(tmp_path / "l.db")
    first = GmailAgent(ledger=ledger, cv_dir=tmp_path / "cvs", mode="fake", client=fake)
    first.update_config(SyncConfig(ignored_senders=["x.com"], max_attachment_mb=5, folder="Candidatures"))
    reborn = GmailAgent(ledger=ledger, cv_dir=tmp_path / "cvs", mode="fake", client=fake)
    assert reborn.sync_config.ignored_senders == ["x.com"] and reborn.sync_config.folder == "Candidatures"
    assert reborn.status().needs_setup is False


# ---------------------------------------------------------------- API (ce que le frontend utilisera)
@pytest.fixture
def api(agent):
    set_agent(agent)
    app = FastAPI()
    app.include_router(router)
    yield TestClient(app)
    set_agent(None)


def test_api_profiles_and_round_trip(api):
    profiles = api.get("/gmail/profiles").json()
    assert [p["name"] for p in profiles] == ["prudent", "new_only", "everything"]
    assert api.get("/gmail/status").json()["needs_setup"] is True
    config = api.put("/gmail/config/profile/new_only").json()
    assert config["mode"] == "new_only" and config["profile"] == "new_only"
    assert api.put("/gmail/config/profile/inconnu").status_code == 404
    current = api.get("/gmail/config").json()  # le frontend renvoie tel quel l'objet reçu (champs calculés inclus)
    current["ignored_senders"] = ["linkedin.com"]
    saved = api.put("/gmail/config", json=current).json()
    assert saved["profile"] == "custom" and saved["ignored_senders"] == ["linkedin.com"]
    assert api.get("/gmail/status").json()["needs_setup"] is False


def test_api_preview_ignored_and_recover(api, fake):
    add(fake, subject="Auto", automatic_reason="newsletter")
    preview = api.post("/gmail/preview").json()
    assert preview["ignored"] == 1 and preview["samples"][0]["outcome"] == "ignored"
    assert api.post("/gmail/preview", json={"ignore_automatic": False}).json()["to_import"] == 1
    api.post("/gmail/sync")
    ignored = api.get("/gmail/ignored").json()
    assert len(ignored) == 1 and ignored[0]["rule"] == "automatic"
    recovered = api.post(f"/gmail/ignored/{ignored[0]['id']}/recover").json()
    assert recovered["imported"]["subject"] == "Auto"
    assert api.get("/gmail/ignored").json() == []
    assert api.post("/gmail/ignored/999/recover").status_code == 404


# ---------------------------------------------------------------- vrais clients (Gmail simulé, IMAP : lecture d'un email)
class _Req:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return self.data


class StubGmail:
    def __init__(self, message):
        self.message, self.queries = message, []

    def users(self):
        return self

    def messages(self):
        return self

    def list(self, **kw):
        self.queries.append(kw["q"])
        return _Req({"messages": [{"id": "m1"}]})

    def get(self, userId, id, format):
        return _Req(self.message)


GMAIL_MSG = {
    "id": "m1",
    "internalDate": "1790000000000",
    "labelIds": ["INBOX"],
    "payload": {
        "headers": [
            {"name": "From", "value": "Offres <jobs@site.com>"},
            {"name": "Subject", "value": "Une offre"},
            {"name": "List-Unsubscribe", "value": "<mailto:stop@site.com>"},
        ],
        "parts": [{"filename": "CV.pdf", "body": {"attachmentId": "a1", "size": 123}}],
    },
}


def test_gmail_folder_label_and_automatic_detection():
    stub = StubGmail(GMAIL_MSG)
    client = GmailApiClient(stub)
    message = client.list_cv_messages(None, 10, folder="Mes candidatures")[0]
    assert "label:Mes-candidatures" in stub.queries[0]
    assert message.automatic_reason and message.attachments[0].size == 123
    client.list_cv_messages(None, 10, folder="INBOX")
    assert "in:inbox" in stub.queries[1]
    assert client.get_message("m1").id == "m1"


def test_imap_reads_automatic_headers_and_quotes_folders():
    raw = (
        b"From: Promo <promo@site.com>\r\nSubject: Offre\r\nDate: Mon, 05 Oct 2026 10:00:00 +0000\r\n"
        b"Precedence: bulk\r\nMIME-Version: 1.0\r\nContent-Type: multipart/mixed; boundary=B\r\n\r\n"
        b"--B\r\nContent-Type: text/plain\r\n\r\nbonjour\r\n--B\r\nContent-Type: application/pdf\r\n"
        b'Content-Disposition: attachment; filename="cv.pdf"\r\nContent-Transfer-Encoding: 7bit\r\n\r\n%PDF-1.4 x\r\n--B--\r\n'
    )
    message = ImapMailClient("h", "u", "p")._parse("imap-1-1", raw)
    assert message is not None and "Precedence" in message.automatic_reason
    assert _quote_folder("Mes candidatures") == '"Mes candidatures"' and _quote_folder("INBOX") == "INBOX"
