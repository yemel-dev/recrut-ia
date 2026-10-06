"""Tests IMAP + multi-comptes — faux serveur IMAP en mémoire, aucun réseau."""
import imaplib
from email.message import EmailMessage
from email.utils import formatdate

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.agent import GmailAgent
from backend.agent.accounts import AccountStore, ImapConfig, MemorySecretStore, detect_imap
from backend.agent.agent import create_agent
from backend.agent.api import router, set_agent
from backend.agent.client import fake_cv_bytes
from backend.agent.errors import ImapAuthError, ImapConnectionError
from backend.agent.ledger import Ledger
from backend.agent.settings import load_settings


def make_mail(sender, subject, attachments):
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"], msg["Date"] = sender, "rh@entreprise.cm", subject, formatdate()
    msg.set_content("Bonjour, veuillez trouver mon CV.")
    for filename, data in attachments:
        sub = "pdf" if filename.endswith(".pdf") else "octet-stream"
        msg.add_attachment(data, maintype="application", subtype=sub, filename=filename)
    return msg.as_bytes()


class FakeImapServer:
    password = "app-pass"
    reachable = True

    def __init__(self):
        self.mails: dict[int, bytes] = {}
        self.fetched_full: list[int] = []

    def add(self, *args):
        uid = len(self.mails) + 1
        self.mails[uid] = make_mail(*args)
        return uid


@pytest.fixture
def server(monkeypatch):
    srv = FakeImapServer()

    class FakeImap:
        def __init__(self, host, port=993, timeout=None):
            if not srv.reachable:
                raise OSError("connexion refusée")

        def login(self, user, password):
            if password != srv.password:
                raise imaplib.IMAP4.error("AUTHENTICATIONFAILED")
            return "OK", [b"ok"]

        def select(self, folder, readonly=False):
            return ("OK", [str(len(srv.mails)).encode()]) if folder == "INBOX" else ("NO", [b"inconnu"])

        def response(self, code):
            return code, [b"7"]

        def uid(self, command, *args):
            if command == "SEARCH":
                return "OK", [b" ".join(str(u).encode() for u in srv.mails)]
            uid = int(args[0])
            if args[1] == "(BODYSTRUCTURE)":
                import email

                names = [p.get_filename() for p in email.message_from_bytes(srv.mails[uid]).walk() if p.get_filename()]
                body = " ".join(f'("application" "pdf" ("name" "{n}"))' for n in names) or '("text" "plain")'
                return "OK", [f"{uid} (UID {uid} BODYSTRUCTURE ({body}))".encode()]
            srv.fetched_full.append(uid)
            return "OK", [(f"{uid} (UID {uid} BODY[] {{{len(srv.mails[uid])}}}".encode(), srv.mails[uid]), b")"]

        def list(self):
            return "OK", [b'(\\HasNoChildren) "/" "INBOX"', b'(\\HasNoChildren) "/" "Junk"']

        def logout(self):
            return "BYE", []

    monkeypatch.setattr("backend.agent.imap_client.imaplib.IMAP4_SSL", FakeImap)
    return srv


CFG = ImapConfig("rh@entreprise.cm", "imap.mail.ovh.net")


@pytest.fixture
def agent(tmp_path):
    return GmailAgent(
        ledger=Ledger(tmp_path / "l.db"),
        cv_dir=tmp_path / "cvs",
        mode="real",
        account_store=AccountStore(tmp_path / "account.json", MemorySecretStore()),
    )


def test_detect_known_and_unknown_hosts():
    assert detect_imap("moi@gmail.com").host == "imap.gmail.com"
    assert detect_imap("x@yahoo.fr").host == "imap.mail.yahoo.com"
    assert detect_imap("contact@entreprise.com") is None


def test_imap_sync_downloads_cvs_with_metadata(agent, server):
    server.add("Aïcha Mballa <aicha@gmail.com>", "Candidature — Data Analyst", [("cv.pdf", fake_cv_bytes("a"))])
    server.add("Marketing <promo@x.com>", "Promo", [])  # sans pièce jointe : ignoré
    agent.connect_imap(CFG, "app-pass")
    result = agent.sync_once()
    assert len(result.new_cvs) == 1
    cv = result.new_cvs[0]
    assert (cv.sender_name, cv.sender_email, cv.subject) == ("Aïcha Mballa", "aicha@gmail.com", "Candidature — Data Analyst")
    assert cv.message_id.startswith("imap-7-")
    assert agent.status().provider == "imap"


def test_imap_does_not_refetch_processed_emails(agent, server):
    server.add("A <a@x.cm>", "1", [("cv.pdf", fake_cv_bytes("a"))])
    agent.connect_imap(CFG, "app-pass")
    agent.sync_once()
    server.fetched_full.clear()
    again = agent.sync_once()
    assert again.new_cvs == [] and server.fetched_full == []  # aucun re-téléchargement


def test_wrong_password_is_rejected_and_nothing_saved(agent, server):
    with pytest.raises(ImapAuthError):
        agent.connect_imap(CFG, "mauvais-mdp")
    assert not agent.connected
    assert agent.account_store.load() is None


def test_unreachable_server(agent, server):
    server.reachable = False
    with pytest.raises(ImapConnectionError):
        agent.connect_imap(CFG, "app-pass")


def test_password_goes_to_secret_store_not_to_disk(agent, server, tmp_path):
    agent.connect_imap(CFG, "app-pass")
    assert "app-pass" not in (tmp_path / "account.json").read_text()
    assert agent.account_store.secrets.get("imap:rh@entreprise.cm") == "app-pass"


def test_session_is_restored_at_startup(agent, server, tmp_path):
    server.add("A <a@x.cm>", "1", [("cv.pdf", fake_cv_bytes("a"))])
    agent.connect_imap(CFG, "app-pass")
    reborn = GmailAgent(ledger=Ledger(tmp_path / "l.db"), cv_dir=tmp_path / "cvs", mode="real", account_store=agent.account_store)
    assert reborn.try_restore() is True
    assert reborn.status().account_email == "rh@entreprise.cm"


def test_disconnect_forgets_password(agent, server):
    agent.connect_imap(CFG, "app-pass")
    agent.disconnect()
    assert not agent.connected
    assert agent.account_store.secrets.get("imap:rh@entreprise.cm") is None


def test_each_account_has_its_own_sync_cursor(agent, server):
    agent.connect_imap(CFG, "app-pass")
    agent.sync_once()
    first = agent._cursor_key
    agent.connect_imap(ImapConfig("autre@entreprise.cm", "imap.mail.ovh.net"), "app-pass")
    assert agent._cursor_key != first
    assert agent.status().last_sync_at is None


# ---- API (mode fake : le frontend peut développer son formulaire sans serveur)
@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("GMAIL_LEDGER_PATH", str(tmp_path / "x.db"))
    monkeypatch.setenv("CV_DIR", str(tmp_path / "cvs"))
    set_agent(create_agent(load_settings(), mode="fake"))
    app = FastAPI()
    app.include_router(router)
    yield TestClient(app)
    set_agent(None)


def test_api_detect_and_connect_fake(api):
    assert api.get("/gmail/imap/detect", params={"email": "moi@gmail.com"}).json()["host"] == "imap.gmail.com"
    ok = api.post("/gmail/connect/imap", json={"email": "moi@gmail.com", "password": "abcd"})
    assert ok.status_code == 200 and ok.json()["account_email"] == "moi@gmail.com"
    bad = api.post("/gmail/connect/imap", json={"email": "moi@gmail.com", "password": "mauvais"})
    assert bad.status_code == 401


def test_api_unknown_host_needs_host_field(api):
    r = api.post("/gmail/connect/imap", json={"email": "contact@entreprise.com", "password": "x"})
    assert r.status_code == 422
    r = api.post("/gmail/connect/imap", json={"email": "contact@entreprise.com", "password": "x", "host": "imap.mail.ovh.net"})
    assert r.status_code == 200


# ---- Audit : « pourquoi mon email n'est pas récupéré ? »
from backend.agent.diagnostics import format_report, run_audit
from backend.agent.imap_client import ImapMailClient


def test_new_email_after_first_sync_is_collected(agent, server):
    server.add("A <a@x.cm>", "ancien", [("ancien.pdf", fake_cv_bytes("a"))])
    agent.connect_imap(CFG, "app-pass")
    agent.sync_once()
    server.add("B <b@x.cm>", "nouveau", [("nouveau.pdf", fake_cv_bytes("b"))])
    result = agent.sync_once()
    assert [c.filename for c in result.new_cvs] == ["nouveau.pdf"]


def test_resending_the_same_cv_is_explained(agent, server):
    same = fake_cv_bytes("meme")
    server.add("A <a@x.cm>", "test 1", [("cv.pdf", same)])
    agent.connect_imap(CFG, "app-pass")
    agent.sync_once()
    server.add("A <a@x.cm>", "test 2", [("cv.pdf", same)])  # le même fichier renvoyé
    result = agent.sync_once()
    assert result.new_cvs == [] and result.duplicates_skipped == 1
    assert "même contenu" in result.skipped[0].reason


def test_audit_explains_each_email(agent, server):
    same = fake_cv_bytes("meme")
    server.add("A <a@x.cm>", "premier", [("cv.pdf", same)])
    agent.connect_imap(CFG, "app-pass")
    agent.sync_once()
    server.add("A <a@x.cm>", "renvoi", [("cv.pdf", same)])
    server.add("B <b@x.cm>", "ancien format", [("cv.doc", b"vieux word")])
    server.add("C <c@x.cm>", "rien", [])
    server.add("D <d@x.cm>", "nouveau", [("nouveau.pdf", fake_cv_bytes("d"))])
    report = run_audit(agent, days=7)
    by_subject = {e["subject"]: e for e in report["emails"]}
    assert by_subject["premier"]["results"][0]["verdict"] == "déjà récupéré"
    assert by_subject["renvoi"]["results"][0]["verdict"] == "doublon"
    assert by_subject["nouveau"]["results"][0]["verdict"] == "NOUVEAU"
    assert by_subject["ancien format"]["seen_by_agent"] is False and "cv.doc" in by_subject["ancien format"]["reason"]
    assert by_subject["rien"]["reason"] == "aucune pièce jointe"
    assert "Junk" in report["mailbox"]["folders_on_server"]
    assert report["summary"]["to_be_collected"] == 1
    assert "NOUVEAU" in format_report(report)
    assert agent.ledger.count_cvs() == 1  # l'audit n'enregistre rien


def test_audit_requires_connection(tmp_path):
    from backend.agent.errors import NotConnectedError

    lonely = GmailAgent(ledger=Ledger(tmp_path / "z.db"), cv_dir=tmp_path / "c", mode="real")
    with pytest.raises(NotConnectedError):
        run_audit(lonely)


def test_bodystructure_heuristic_does_not_miss_encoded_names():
    class Conn:
        def __init__(self, text):
            self.text = text

        def uid(self, *args):
            return "OK", [self.text.encode()]

    encoded = '1 (BODYSTRUCTURE ("text" "plain")("application" "octet-stream" ("name" "=?utf-8?q?CV_A=C3=AFcha=2Epdf?=")))'
    assert ImapMailClient._maybe_has_cv(Conn(encoded), "1") is True
    assert ImapMailClient._maybe_has_cv(Conn('1 (BODYSTRUCTURE ("text" "plain" ("charset" "utf-8")))'), "1") is False
