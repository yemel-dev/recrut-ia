"""Intégration de l'agent mail dans INJARA (mode démo : aucune vraie boîte n'est lue)."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.agent.client import fake_cv_bytes
from backend.services.agent_mail import parametres_agent

from .conftest import EMAIL, JETON, MOT_DE_PASSE

IDENTIFIANTS = {"installed": {"client_id": "abc.apps.googleusercontent.com", "client_secret": "secret", "redirect_uris": ["http://localhost"]}}


def attendre(condition, delai=5.0):
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        if condition():
            return True
        time.sleep(0.05)
    return condition()


def surveillance_active(client) -> bool:
    return client.get("/gmail/status").json()["watching"]


# --- Accès -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("methode", "chemin"),
    [
        ("get", "/gmail/status"),
        ("post", "/gmail/sync"),
        ("get", "/gmail/cvs"),
        ("post", "/gmail/connect/imap"),
        ("get", "/gmail/config"),
        ("get", "/gmail/events"),
        ("get", "/agent/etat"),
        ("put", "/agent/surveillance"),
        ("post", "/agent/identifiants-google"),
    ],
)
def test_routes_de_l_agent_exigent_une_session(client, cle_recuperation, methode, chemin):
    assert getattr(client, methode)(chemin).status_code == 401


def test_routes_de_l_agent_exigent_le_jeton_de_lancement(app):
    assert TestClient(app).get("/gmail/status").status_code == 401


# --- Fonctionnement dans INJARA ----------------------------------------------------------------


def test_statut_en_mode_demo(connecte):
    statut = connecte.get("/gmail/status").json()
    assert statut["mode"] == "fake"
    assert statut["connected"] is True
    assert connecte.get("/agent/etat").json() == {"mode": "fake", "surveillance_souhaitee": False, "identifiants_google": False}


def test_les_cv_sont_ranges_dans_le_dossier_de_donnees(settings, connecte):
    resultat = connecte.post("/gmail/sync").json()
    assert len(resultat["new_cvs"]) == 5
    dossier_cv = (settings.data_dir / "cvs").resolve()
    for cv in resultat["new_cvs"]:
        chemin = Path(cv["saved_path"]).resolve()
        assert chemin.is_relative_to(dossier_cv) and chemin.exists()
    assert connecte.get("/gmail/status").json()["total_cvs"] == 5


def test_import_manuel(settings, connecte):
    reponse = connecte.post(
        "/gmail/cvs/upload",
        files=[("files", ("cv_awa.pdf", fake_cv_bytes("Awa", "pdf"), "application/pdf")), ("files", ("note.txt", b"x", "text/plain"))],
    )
    assert reponse.status_code == 200
    corps = reponse.json()
    assert [c["filename"] for c in corps["imported"]] == ["cv_awa.pdf"]
    assert corps["rejected"][0]["filename"] == "note.txt"
    assert Path(corps["imported"][0]["saved_path"]).resolve().is_relative_to((settings.data_dir / "cvs").resolve())


def test_evenements(connecte):
    connecte.post("/gmail/sync")
    evenements = connecte.get("/gmail/events?after_id=0").json()
    assert any(e["type"] == "new_cvs" for e in evenements)


def test_reglages_et_message_de_validation_de_l_agent(connecte):
    assert connecte.put("/gmail/config/profile/prudent").json()["profile"] == "prudent"
    reponse = connecte.put("/gmail/config", json={"mode": "since_date"})
    assert reponse.status_code == 422
    assert "since_date est obligatoire" in json.dumps(reponse.json(), ensure_ascii=False)


# --- Surveillance automatique ------------------------------------------------------------------


def test_surveillance_memorisee_suspendue_a_la_deconnexion_reprise_a_la_connexion(connecte):
    assert connecte.put("/agent/surveillance", json={"active": True}).json()["watching"] is True
    assert connecte.get("/agent/etat").json()["surveillance_souhaitee"] is True

    connecte.post("/auth/deconnexion")
    jeton = connecte.post("/auth/connexion", json={"email": EMAIL, "mot_de_passe": MOT_DE_PASSE}).json()["jeton_session"]
    connecte.headers["X-Injara-Session"] = jeton
    assert attendre(lambda: surveillance_active(connecte)), "la surveillance doit reprendre après la connexion"


def test_deconnexion_arrete_la_surveillance(app, connecte):
    connecte.put("/agent/surveillance", json={"active": True})
    agent = app.state.services.agent_mail.agent()
    connecte.post("/auth/deconnexion")
    assert agent.watching is False


def test_desactiver_la_surveillance(connecte):
    connecte.put("/agent/surveillance", json={"active": True})
    assert connecte.put("/agent/surveillance", json={"active": False}).json()["watching"] is False
    assert connecte.get("/agent/etat").json()["surveillance_souhaitee"] is False


def test_pas_de_reprise_si_non_demandee(connecte):
    connecte.post("/auth/deconnexion")
    jeton = connecte.post("/auth/connexion", json={"email": EMAIL, "mot_de_passe": MOT_DE_PASSE}).json()["jeton_session"]
    connecte.headers["X-Injara-Session"] = jeton
    time.sleep(0.3)
    assert surveillance_active(connecte) is False


# --- Identifiants Google ----------------------------------------------------------------------


def test_identifiants_google(settings, connecte):
    reponse = connecte.post("/agent/identifiants-google", json={"contenu": json.dumps(IDENTIFIANTS)})
    assert reponse.status_code == 200
    assert reponse.json()["identifiants_google"] is True
    assert json.loads((settings.data_dir / "secrets" / "credentials.json").read_text(encoding="utf-8")) == IDENTIFIANTS


@pytest.mark.parametrize(
    ("contenu", "extrait"),
    [
        ("pas du json", "pas un fichier d'identifiants"),
        (json.dumps({"installed": {"client_id": "x"}}), "pas un fichier d'identifiants"),
        (json.dumps({"web": {"client_id": "x", "client_secret": "y"}}), "Application de bureau"),
        ("x" * (70 * 1024), "pas un fichier d'identifiants"),
    ],
    ids=["pas-json", "incomplet", "application-web", "trop-gros"],
)
def test_identifiants_google_refuses(connecte, contenu, extrait):
    reponse = connecte.post("/agent/identifiants-google", json={"contenu": contenu})
    assert reponse.status_code == 422
    assert extrait in reponse.json()["champs"]["fichier"]


# --- Chemins en mode réel ------------------------------------------------------------------------


def test_chemins_de_l_agent_en_mode_reel(tmp_path, monkeypatch):
    monkeypatch.delenv("GMAIL_CREDENTIALS_PATH", raising=False)
    reglages = parametres_agent(tmp_path, "real")
    assert reglages.mode == "real"
    for chemin in (reglages.cv_dir, reglages.ledger_path, reglages.account_path, reglages.token_path, reglages.credentials_path):
        assert chemin.is_relative_to(tmp_path)


def test_identifiants_google_partages_en_developpement(tmp_path, monkeypatch):
    monkeypatch.setenv("GMAIL_CREDENTIALS_PATH", str(tmp_path / "ailleurs" / "credentials.json"))
    assert parametres_agent(tmp_path / "donnees", "real").credentials_path == tmp_path / "ailleurs" / "credentials.json"


def test_jeton_session_requis_meme_avec_jeton_de_lancement(app, cle_recuperation):
    client = TestClient(app, headers={"X-Injara-Token": JETON, "X-Injara-Session": "invente"})
    assert client.get("/gmail/status").status_code == 401
