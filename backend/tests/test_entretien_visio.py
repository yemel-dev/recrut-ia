"""Entretien vidéo : accès public du candidat, signalisation WebRTC, enregistrement chiffré, tunnel."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.services import coffre
from backend.services.tunnel import _MOTIF_CLOUDFLARED, TunnelService

from .conftest import JETON
from .test_entretiens import _candidature, _planifier
from .test_traitement import boite, services  # noqa: F401


@pytest.fixture
def entretien(connecte, services, boite, tmp_path):  # noqa: F811
    return _planifier(connecte, _candidature(connecte, services, boite, tmp_path))


@pytest.fixture
def anonyme(app):
    """Client du candidat : ni jeton de lancement ni session. Contexte ouvert = une seule boucle pour tous les WebSocket."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def sans_session(app):
    """Client d'Electron sans session ouverte : jeton de lancement seulement."""
    return TestClient(app, headers={"X-Injara-Token": JETON})


def _recevoir(ws) -> dict:
    return json.loads(ws.receive_text())


# --- Accès public ----------------------------------------------------------------------------------------


def test_routes_publiques_sans_jeton_mais_reste_de_l_api_ferme(anonyme, entretien):
    code = entretien["code_invitation"]
    assert anonyme.get(f"/public/api/{code}").status_code == 200
    assert anonyme.get("/entretiens").status_code == 401
    assert anonyme.get(f"/entretiens/{entretien['id']}").status_code == 401
    assert anonyme.get("/auth/etat").status_code == 401
    assert anonyme.get("/public/../entretiens").status_code in (401, 404)


def test_presentation_au_candidat(anonyme, entretien):
    infos = anonyme.get(f"/public/api/{entretien['code_invitation']}").json()
    assert infos["statut"] == "planifie" and infos["consentement_enregistrement"] is False
    assert infos["ice"] and infos["ice"][0]["urls"]
    assert set(infos) == {"entreprise", "poste", "date_entretien", "statut", "consentement_enregistrement", "ice"}  # rien d'autre ne fuit


def test_lien_inconnu_ou_expire_ou_clos(anonyme, connecte, app, entretien):
    assert anonyme.get("/public/api/inconnu").status_code == 404
    code = entretien["code_invitation"]
    passe = datetime.now(timezone.utc) - timedelta(minutes=1)
    app.state.services.entretiens.entretiens.maj(entretien["id"], expire_le=passe)
    assert anonyme.get(f"/public/api/{code}").status_code == 404
    app.state.services.entretiens.entretiens.maj(entretien["id"], expire_le=None)
    assert anonyme.get(f"/public/api/{code}").status_code == 200
    connecte.put(f"/entretiens/{entretien['id']}/statut", json={"statut": "annule"})
    assert anonyme.get(f"/public/api/{code}").status_code == 404


def test_expiration_posee_a_la_planification(entretien):
    expire = datetime.fromisoformat(entretien["expire_le"])
    assert timedelta(days=6) < expire - datetime.now(timezone.utc) <= timedelta(days=7)


def test_page_et_ressources_avec_en_tetes_de_securite(anonyme, entretien):
    page = anonyme.get(f"/public/entretien/{entretien['code_invitation']}")
    assert page.status_code == 200 and "text/html" in page.headers["content-type"]
    assert "script-src 'self'" in page.headers["content-security-policy"]
    assert page.headers["referrer-policy"] == "no-referrer" and page.headers["cache-control"] == "no-store"
    assert "<script>" not in page.text  # la CSP interdit les scripts en ligne
    assert anonyme.get("/public/candidat.js").status_code == 200
    assert anonyme.get("/public/candidat.css").status_code == 200
    assert anonyme.get("/public/polices/pt-sans-400.woff2").status_code == 200
    assert anonyme.get("/public/marque/symbole.webp").status_code == 200
    assert anonyme.get("/public/polices/LICENSE-pt-sans.txt").status_code == 404
    assert anonyme.get("/public/marque/..%2F..%2Fapi%2Fapp.py").status_code == 404


def test_consentement_du_candidat(anonyme, connecte, entretien):
    code = entretien["code_invitation"]
    assert anonyme.post(f"/public/api/{code}/consentement", json={"accepte": True}).json()["consentement_enregistrement"] is True
    assert connecte.get(f"/entretiens/{entretien['id']}").json()["consentement_enregistrement"] is True
    anonyme.post(f"/public/api/{code}/consentement", json={"accepte": False})
    assert connecte.get(f"/entretiens/{entretien['id']}").json()["consentement_enregistrement"] is False
    assert anonyme.post("/public/api/inconnu/consentement", json={"accepte": True}).status_code == 404


# --- Signalisation ---------------------------------------------------------------------------------------


def _ticket(connecte, entretien) -> str:
    reponse = connecte.post(f"/entretiens/{entretien['id']}/salle")
    assert reponse.status_code == 200, reponse.text
    return reponse.json()["ticket"]


def test_salle_exige_une_session(sans_session, entretien):
    assert sans_session.post(f"/entretiens/{entretien['id']}/salle").status_code == 401


def test_candidat_refuse_avec_un_mauvais_code(anonyme):
    with pytest.raises(WebSocketDisconnect) as erreur, anonyme.websocket_connect("/public/ws/candidat/inconnu"):
        pass
    assert erreur.value.code in (4404, 1008, 1006)


def test_recruteur_refuse_sans_ticket_valide_et_ticket_a_usage_unique(anonyme, connecte, entretien):
    with pytest.raises(WebSocketDisconnect), anonyme.websocket_connect("/public/ws/recruteur?ticket=faux"):
        pass
    ticket = _ticket(connecte, entretien)
    with anonyme.websocket_connect(f"/public/ws/recruteur?ticket={ticket}") as ws:
        assert _recevoir(ws) == {"type": "presence", "recruteur": True, "candidat": False}
    with pytest.raises(WebSocketDisconnect), anonyme.websocket_connect(f"/public/ws/recruteur?ticket={ticket}"):
        pass


def test_les_deux_participants_s_echangent_offre_reponse_et_ice(anonyme, connecte, entretien):
    code = entretien["code_invitation"]
    with anonyme.websocket_connect(f"/public/ws/candidat/{code}") as candidat:
        assert _recevoir(candidat) == {"type": "presence", "recruteur": False, "candidat": True}
        with anonyme.websocket_connect(f"/public/ws/recruteur?ticket={_ticket(connecte, entretien)}") as recruteur:
            assert _recevoir(recruteur) == {"type": "presence", "recruteur": True, "candidat": True}
            assert _recevoir(candidat) == {"type": "presence", "recruteur": True, "candidat": True}

            recruteur.send_text(json.dumps({"type": "offre", "donnees": {"type": "offer", "sdp": "v=0"}}))
            assert _recevoir(candidat) == {"type": "offre", "donnees": {"type": "offer", "sdp": "v=0"}}
            candidat.send_text(json.dumps({"type": "reponse", "donnees": {"type": "answer", "sdp": "v=0"}}))
            assert _recevoir(recruteur)["type"] == "reponse"
            candidat.send_text(json.dumps({"type": "ice", "donnees": {"candidate": "c1"}}))
            assert _recevoir(recruteur) == {"type": "ice", "donnees": {"candidate": "c1"}}

        assert _recevoir(candidat) == {"type": "presence", "recruteur": False, "candidat": True}  # le recruteur est parti


def test_message_hors_protocole_coupe_la_connexion(anonyme, entretien):
    with anonyme.websocket_connect(f"/public/ws/candidat/{entretien['code_invitation']}") as candidat:
        _recevoir(candidat)
        candidat.send_text(json.dumps({"type": "alerte"}))  # type non relayé
        with pytest.raises(WebSocketDisconnect) as erreur:
            candidat.receive_text()
    assert erreur.value.code == 1008


def test_reconnexion_du_candidat_remplace_l_ancienne_connexion(anonyme, entretien):
    url = f"/public/ws/candidat/{entretien['code_invitation']}"
    with anonyme.websocket_connect(url) as premier:
        _recevoir(premier)
        with anonyme.websocket_connect(url) as second:
            assert _recevoir(second)["candidat"] is True
            with pytest.raises(WebSocketDisconnect) as erreur:
                premier.receive_text()
            assert erreur.value.code == 4000


def test_terminer_l_entretien_ferme_la_salle(anonyme, connecte, entretien):
    code = entretien["code_invitation"]
    with anonyme.websocket_connect(f"/public/ws/candidat/{code}") as candidat:
        _recevoir(candidat)
        assert connecte.put(f"/entretiens/{entretien['id']}/statut", json={"statut": "annule"}).status_code == 200
        with pytest.raises(WebSocketDisconnect) as erreur:
            candidat.receive_text()
    assert erreur.value.code == 4001


# --- Lien et tunnel --------------------------------------------------------------------------------------


def test_lien_indisponible_sans_acces_a_distance(connecte, entretien, monkeypatch):
    monkeypatch.delenv("INJARA_URL_PUBLIQUE", raising=False)
    reponse = connecte.get(f"/entretiens/{entretien['id']}/lien")
    assert reponse.status_code == 503 and "accès à distance" in reponse.json()["detail"]


def test_lien_avec_adresse_publique_fixe(connecte, entretien, monkeypatch):
    monkeypatch.setenv("INJARA_URL_PUBLIQUE", "https://entretiens.exemple.cm/")
    reponse = connecte.get(f"/entretiens/{entretien['id']}/lien").json()
    assert reponse["lien"] == f"https://entretiens.exemple.cm/public/entretien/{entretien['code_invitation']}"
    assert connecte.get("/tunnel").json()["actif"] is True


def test_tunnel_sans_outil_installe(connecte, monkeypatch):
    monkeypatch.delenv("INJARA_URL_PUBLIQUE", raising=False)
    monkeypatch.setattr(TunnelService, "_commande", lambda self, port: None)
    assert connecte.get("/tunnel").json() == {"actif": False, "url": None, "outil": None, "disponible": False}
    assert connecte.post("/tunnel").status_code == 503


def test_tunnel_lance_un_outil_et_lit_son_adresse(app, connecte, monkeypatch):
    monkeypatch.delenv("INJARA_URL_PUBLIQUE", raising=False)
    faux = "import sys,time; print('INF https://abc-def.trycloudflare.com', flush=True); time.sleep(60)"
    monkeypatch.setattr(TunnelService, "_commande", lambda self, port: ("faux", [sys.executable, "-c", faux], _MOTIF_CLOUDFLARED))
    tunnel = app.state.services.tunnel
    tunnel.port = 4242
    try:
        etat = connecte.post("/tunnel").json()
        assert etat["actif"] and etat["url"] == "https://abc-def.trycloudflare.com"
        processus = tunnel._processus
        assert connecte.post("/tunnel").json()["url"] == etat["url"]  # idempotent : pas de second processus
        assert tunnel._processus is processus
        assert connecte.delete("/tunnel").json()["actif"] is False
        assert processus.poll() is not None  # le processus est bien arrêté
    finally:
        tunnel.arreter()


def test_tunnel_arrete_a_la_deconnexion(app, connecte, monkeypatch):
    monkeypatch.delenv("INJARA_URL_PUBLIQUE", raising=False)
    faux = "import time; print('https://x.trycloudflare.com', flush=True); time.sleep(60)"
    monkeypatch.setattr(TunnelService, "_commande", lambda self, port: ("faux", [sys.executable, "-c", faux], _MOTIF_CLOUDFLARED))
    tunnel = app.state.services.tunnel
    tunnel.port = 4242
    connecte.post("/tunnel")
    processus = tunnel._processus
    connecte.post("/auth/deconnexion")
    assert tunnel.url is None and processus.poll() is not None


def test_motifs_d_adresse_de_tunnel():
    assert _MOTIF_CLOUDFLARED.search("2026 INF |  https://quiet-owl-12.trycloudflare.com  |").group(0) == "https://quiet-owl-12.trycloudflare.com"


# --- Enregistrement --------------------------------------------------------------------------------------


def _demarrer(connecte, entretien, consentement=True):
    if consentement:
        assert connecte.put(f"/entretiens/{entretien['id']}/consentement", json={"accepte": True}).status_code == 200
    assert connecte.put(f"/entretiens/{entretien['id']}/statut", json={"statut": "en_cours"}).status_code == 200


def _morceau(connecte, entretien, donnees: bytes):
    return connecte.put(f"/entretiens/{entretien['id']}/enregistrement", content=donnees, headers={"Content-Type": "application/octet-stream"})


def test_enregistrement_refuse_sans_consentement(connecte, entretien):
    _demarrer(connecte, entretien, consentement=False)
    reponse = _morceau(connecte, entretien, b"video")
    assert reponse.status_code == 409 and "consenti" in reponse.json()["detail"]


def test_enregistrement_refuse_hors_entretien_en_cours(connecte, entretien):
    connecte.put(f"/entretiens/{entretien['id']}/consentement", json={"accepte": True})
    assert _morceau(connecte, entretien, b"video").status_code == 409  # encore « planifie »


def test_enregistrement_mp4_reconnu_au_premier_morceau(connecte, settings, entretien):
    _demarrer(connecte, entretien)
    assert _morceau(connecte, entretien, b"\x00\x00\x00\x18ftypisom" + b"\x00" * 20).status_code == 204
    assert (settings.data_dir / "enregistrements" / f"entretien-{entretien['id']}.mp4.injara").is_file()
    assert connecte.get(f"/entretiens/{entretien['id']}").json()["format_enregistrement"] == "mp4"


def test_enregistrement_chiffre_et_relu_a_l_identique(connecte, app, settings, entretien):
    _demarrer(connecte, entretien)
    morceaux = [b"EBML-entete", b"\x00\x01" * 5000, "accentué".encode()]
    for m in morceaux:
        assert _morceau(connecte, entretien, m).status_code == 204

    fichier = settings.data_dir / "enregistrements" / f"entretien-{entretien['id']}.webm.injara"
    brut = fichier.read_bytes()
    assert b"EBML-entete" not in brut and "accentué".encode() not in brut  # rien en clair sur le disque

    reponse = connecte.get(f"/entretiens/{entretien['id']}/enregistrement")
    assert reponse.status_code == 200 and reponse.content == b"".join(morceaux)
    assert connecte.get(f"/entretiens/{entretien['id']}").json()["transcription"] is None
    assert connecte.get("/entretiens").json()[0]["enregistrement"] is True
    assert connecte.get(f"/entretiens/{entretien['id']}").json()["format_enregistrement"] == "webm"


def test_morceau_vide_ou_trop_gros_refuse(connecte, entretien, monkeypatch):
    _demarrer(connecte, entretien)
    assert _morceau(connecte, entretien, b"").status_code == 422
    monkeypatch.setattr("backend.services.entretiens.TAILLE_MAX_MORCEAU", 10)
    assert _morceau(connecte, entretien, b"x" * 11).status_code == 422


def test_pas_d_enregistrement_a_lire(connecte, entretien):
    assert connecte.get(f"/entretiens/{entretien['id']}/enregistrement").status_code == 404


def test_enregistrement_exige_une_session(sans_session, entretien):
    assert sans_session.put(f"/entretiens/{entretien['id']}/enregistrement", content=b"x").status_code == 401
    assert sans_session.get(f"/entretiens/{entretien['id']}/enregistrement").status_code == 401


def test_enregistrement_illisible_avec_une_autre_cle(tmp_path):
    chemin = tmp_path / "e.injara"
    coffre.ajouter_morceau(chemin, b"un", b"a" * 32)
    coffre.ajouter_morceau(chemin, b"deux", b"a" * 32)
    assert list(coffre.lire_morceaux(chemin, b"a" * 32)) == [b"un", b"deux"]
    with pytest.raises(coffre.Indechiffrable):
        list(coffre.lire_morceaux(chemin, b"b" * 32))
    chemin.write_bytes(chemin.read_bytes()[:-3])  # fichier tronqué (arrêt brutal)
    with pytest.raises(coffre.Indechiffrable):
        list(coffre.lire_morceaux(chemin, b"a" * 32))
