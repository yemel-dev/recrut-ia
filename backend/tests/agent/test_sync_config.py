"""Règle de récupération configurable : période, nouveaux seulement, non lus, limite."""
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.agent import GmailAgent
from backend.agent.api import router, set_agent
from backend.agent.client import FakeMailClient, GmailApiClient, fake_cv_bytes
from backend.agent.ledger import Ledger
from backend.agent.schemas import SyncConfig

NOW = datetime.now(timezone.utc)


def ago(days):
    return NOW - timedelta(days=days)


@pytest.fixture
def fake():
    return FakeMailClient()


@pytest.fixture
def make_agent(tmp_path, fake):
    def build(**config):
        agent = GmailAgent(ledger=Ledger(tmp_path / "l.db"), cv_dir=tmp_path / "cvs", mode="fake", client=fake)
        agent.update_config(SyncConfig(**config))
        return agent

    return build


def mail(fake, subject, days_ago=0, **kw):
    return fake.add_message("A <a@x.cm>", subject, [("cv.pdf", fake_cv_bytes(subject))], received_at=None if days_ago == 0 else ago(days_ago), **kw)


def subjects(result):
    return sorted(c.subject for c in result.new_cvs)


def test_last_days_only_takes_the_chosen_period(make_agent, fake):
    mail(fake, "recent", 2)
    mail(fake, "ancien", 10)
    assert subjects(make_agent(mode="last_days", days=5).sync_once()) == ["recent"]


def test_since_date(make_agent, fake):
    mail(fake, "avant", 20)
    mail(fake, "apres", 3)
    boundary = (NOW - timedelta(days=10)).date()
    assert subjects(make_agent(mode="since_date", since_date=boundary).sync_once()) == ["apres"]


def test_all_takes_everything(make_agent, fake):
    mail(fake, "tres-ancien", 400)
    mail(fake, "recent", 1)
    assert subjects(make_agent(mode="all").sync_once()) == ["recent", "tres-ancien"]


def test_new_only_ignores_existing_mail_then_takes_new_ones(make_agent, fake):
    mail(fake, "deja-la", 3)
    agent = make_agent(mode="new_only")
    assert agent.sync_once().new_cvs == []  # le passé est ignoré
    mail(fake, "nouveau")
    assert subjects(agent.sync_once()) == ["nouveau"]


def test_unread_only(make_agent, fake):
    mail(fake, "non-lu")
    lu = mail(fake, "lu")
    fake.mark_read(lu.id)
    assert subjects(make_agent(mode="last_days", days=7, unread_only=True).sync_once()) == ["non-lu"]


def test_changing_the_rule_rescans_and_is_remembered(tmp_path, fake):
    mail(fake, "recent", 2)
    mail(fake, "ancien", 20)
    ledger = Ledger(tmp_path / "l.db")
    agent = GmailAgent(ledger=ledger, cv_dir=tmp_path / "cvs", mode="fake", client=fake)
    agent.update_config(SyncConfig(mode="last_days", days=5))
    assert subjects(agent.sync_once()) == ["recent"]
    agent.update_config(SyncConfig(mode="last_days", days=30))  # on élargit : l'ancien est rattrapé
    assert subjects(agent.sync_once()) == ["ancien"]
    reborn = GmailAgent(ledger=ledger, cv_dir=tmp_path / "cvs", mode="fake", client=fake)  # redémarrage
    assert reborn.sync_config.days == 30


def test_limit_per_sync_never_loses_emails(tmp_path, fake):
    for i in range(5):
        mail(fake, f"cv{i}", i)
    agent = GmailAgent(ledger=Ledger(tmp_path / "l.db"), cv_dir=tmp_path / "cvs", mode="fake", client=fake, max_results=2)
    fake.skip_filter = agent.ledger.has_message  # comme en vrai (Gmail/IMAP)
    total, rounds = [], 0
    while rounds < 10:
        result = agent.sync_once()
        total += result.new_cvs
        rounds += 1
        if not result.truncated:
            break
    assert len(total) == 5 and rounds == 3  # 2 + 2 + 1 : rien de perdu


def test_describe_is_human_readable():
    assert "NON LUS" in SyncConfig(unread_only=True).describe()
    assert "14 derniers jours" in SyncConfig(mode="last_days", days=14).describe()
    assert "01/10/2026" in SyncConfig(mode="since_date", since_date=date(2026, 10, 1)).describe()


def test_api_get_and_put_config(make_agent):
    set_agent(make_agent())
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    assert client.get("/gmail/config").json()["mode"] == "last_days"
    ok = client.put("/gmail/config", json={"mode": "new_only", "unread_only": True})
    assert ok.status_code == 200 and client.get("/gmail/status").json()["sync_config"]["mode"] == "new_only"
    assert client.put("/gmail/config", json={"mode": "since_date"}).status_code == 422  # date manquante
    assert client.put("/gmail/config", json={"mode": "last_days", "days": 0}).status_code == 422
    set_agent(None)


# ---- Vrai client Gmail, avec un faux « service » Google (vérifie la requête envoyée et la lecture des pièces jointes)
class _Req:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return self.data


class StubGmail:
    def __init__(self, ids, messages):
        self.ids, self.bodies, self.queries, self.fetched = ids, messages, [], []

    def users(self):
        return self

    def messages(self):
        return self

    def list(self, **kw):
        self.queries.append(kw["q"])
        return _Req({"messages": [{"id": i} for i in self.ids]})

    def get(self, userId, id, format):
        self.fetched.append(id)
        return _Req(self.bodies[id])


def gmail_message(message_id, labels):
    return {
        "id": message_id,
        "internalDate": str(int(NOW.timestamp() * 1000)),
        "labelIds": labels,
        "payload": {
            "headers": [{"name": "From", "value": "Aicha <a@x.cm>"}, {"name": "Subject", "value": "CV"}],
            "parts": [
                {"mimeType": "text/plain", "filename": "", "body": {}},
                {"mimeType": "multipart/mixed", "filename": "", "body": {}, "parts": [
                    {"filename": "CV.pdf", "body": {"attachmentId": "att1", "size": 10}},
                    {"filename": "logo.png", "body": {"attachmentId": "att2", "size": 5}},
                ]},
            ],
        },
    }


def test_gmail_query_unread_date_and_attachment_parsing():
    stub = StubGmail(["m1"], {"m1": gmail_message("m1", ["INBOX", "UNREAD"])})
    client = GmailApiClient(stub)
    messages = client.list_cv_messages(NOW - timedelta(days=3), 50, unread_only=True)
    assert "is:unread" in stub.queries[0] and "after:" in stub.queries[0]
    assert [a.filename for a in messages[0].attachments] == ["CV.pdf"]  # le logo est écarté
    assert messages[0].unread is True
    stub2 = StubGmail([], {})
    GmailApiClient(stub2).list_cv_messages(None, 50)
    assert "is:unread" not in stub2.queries[0] and "after:" not in stub2.queries[0]


def test_gmail_does_not_refetch_known_messages():
    stub = StubGmail(["m1", "m2"], {"m1": gmail_message("m1", []), "m2": gmail_message("m2", [])})
    client = GmailApiClient(stub)
    client.skip_filter = lambda mid: mid == "m1"
    client.list_cv_messages(None, 50)
    assert stub.fetched == ["m2"]
