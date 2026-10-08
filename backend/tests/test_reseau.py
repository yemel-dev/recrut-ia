"""Réseau de la visio : serveur TURN configuré par le recruteur, donné aux deux navigateurs."""
from __future__ import annotations

import json

import pytest

from .test_entretien_visio import anonyme, entretien  # noqa: F401
from .test_traitement import boite, services  # noqa: F401

TURN = {"urls": ["turn:relais.exemple.com:3478", "turns:relais.exemple.com:443"], "username": "awa", "credential": "s3cret"}
STUN = {"urls": ["stun:stun.l.google.com:19302"]}


def test_par_defaut_stun_seul(connecte):
    assert connecte.get("/reseau").json() == {"turn": {"configure": False}, "cloudflare": {"configure": False, "erreur": None}, "source_forcee": False}
    assert connecte.get("/reseau/test").status_code == 404  # rien à tester sans TURN


def test_turn_donne_aux_deux_navigateurs(connecte, anonyme, entretien):  # noqa: F811
    etat = connecte.put("/reseau/turn", json=TURN).json()
    assert etat["turn"] == {"configure": True, "urls": TURN["urls"], "username": "awa"}
    assert "s3cret" not in json.dumps(connecte.get("/reseau").json())  # le mot de passe ne ressort jamais de la configuration

    attendu = [STUN, {"urls": TURN["urls"], "username": "awa", "credential": "s3cret"}]
    assert anonyme.get(f"/public/api/{entretien['code_invitation']}").json()["ice"] == attendu  # côté candidat
    assert connecte.post(f"/entretiens/{entretien['id']}/salle").json()["ice"] == attendu  # côté recruteur
    assert connecte.get("/reseau/test").json() == {"ice": attendu}


def test_identifiants_chiffres_en_base(connecte, app):
    connecte.put("/reseau/turn", json=TURN)
    brut = app.state.services.reseau.parametres.get("reseau_turn")
    assert "s3cret" not in brut and "relais.exemple.com" not in brut


def test_suppression_du_turn(connecte):
    connecte.put("/reseau/turn", json=TURN)
    assert connecte.delete("/reseau/turn").json()["turn"] == {"configure": False}
    assert connecte.get("/reseau/test").status_code == 404


@pytest.mark.parametrize(
    "corps",
    [
        {**TURN, "urls": []},
        {**TURN, "urls": ["http://relais.exemple.com"]},  # ni turn: ni turns:
        {**TURN, "urls": ["stun:stun.exemple.com:3478"]},  # un STUN n'est pas un TURN
        {**TURN, "urls": ["turn:a b"]},
        {**TURN, "urls": [f"turn:h{i}.exemple.com" for i in range(6)]},
        {**TURN, "username": " "},
        {**TURN, "credential": ""},
    ],
)
def test_turn_invalide_refuse(connecte, corps):
    assert connecte.put("/reseau/turn", json=corps).status_code == 422
    assert connecte.get("/reseau").json()["turn"] == {"configure": False}


def test_la_variable_d_environnement_l_emporte(connecte, anonyme, entretien, monkeypatch):  # noqa: F811
    connecte.put("/reseau/turn", json=TURN)
    forces = [{"urls": ["turn:force.exemple.com"], "username": "u", "credential": "p"}]
    monkeypatch.setenv("INJARA_ICE_SERVERS", json.dumps(forces))
    assert connecte.get("/reseau").json()["source_forcee"] is True
    assert anonyme.get(f"/public/api/{entretien['code_invitation']}").json()["ice"] == forces


def test_reseau_exige_une_session(client):
    assert client.get("/reseau").status_code == 401
    assert client.put("/reseau/turn", json=TURN).status_code == 401
    assert client.get("/reseau/test").status_code == 401


# --- Cloudflare Realtime TURN : identifiants temporaires -----------------------------------------------------

import urllib.error  # noqa: E402

from backend.services import reseau as module_reseau  # noqa: E402

REPONSE_CLOUDFLARE = {
    "iceServers": {
        "urls": [
            "stun:stun.cloudflare.com:3478", "turn:turn.cloudflare.com:3478?transport=udp",
            "turn:turn.cloudflare.com:53?transport=udp", "turns:turn.cloudflare.com:5349?transport=tcp",
        ],
        "username": "u-temporaire", "credential": "c-temporaire",
    }
}


class FauxCloudflare:
    """Remplace urllib.request.urlopen : enregistre les appels, aucun accès réseau."""

    def __init__(self, reponse=None, erreur=None):
        self.reponse, self.erreur, self.appels = reponse, erreur, []

    def __call__(self, requete, timeout):
        self.appels.append(requete)
        if self.erreur:
            raise self.erreur
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.reponse).encode()


@pytest.fixture
def cloudflare(app, monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_TURN_TOKEN_ID", "cle-123")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "jeton-secret")
    faux = FauxCloudflare(REPONSE_CLOUDFLARE)
    app.state.services.reseau._ouvrir = faux
    return faux


def test_cloudflare_identifiants_temporaires_au_bon_format(connecte, app, cloudflare):
    ice = app.state.services.reseau.serveurs_ice()
    assert ice[0] == STUN
    cf = ice[1]
    assert isinstance(ice, list) and cf["username"] == "u-temporaire" and cf["credential"] == "c-temporaire"
    assert cf["urls"] == ["stun:stun.cloudflare.com:3478", "turn:turn.cloudflare.com:3478?transport=udp", "turns:turn.cloudflare.com:5349?transport=tcp"]  # sans le port 53

    requete = cloudflare.appels[0]
    assert requete.full_url == "https://rtc.live.cloudflare.com/v1/turn/keys/cle-123/credentials/generate"
    assert requete.get_method() == "POST" and requete.get_header("Authorization") == "Bearer jeton-secret"
    assert requete.get_header("User-agent") == "INJARA/1.0"
    assert json.loads(requete.data) == {"ttl": 86400}


def test_cloudflare_identifiants_gardes_en_memoire(app, cloudflare):
    for _ in range(5):
        app.state.services.reseau.serveurs_ice()
    assert len(cloudflare.appels) == 1


def test_cloudflare_renouvelle_avant_l_expiration(app, cloudflare, monkeypatch):
    reseau = app.state.services.reseau
    reseau.serveurs_ice()
    t = {"v": 0.0}
    monkeypatch.setattr(module_reseau.time, "monotonic", lambda: t["v"])
    reseau._cloudflare = (reseau._cloudflare[0], 1000.0)  # expire à t = 1000
    t["v"] = 999.0
    reseau.serveurs_ice()
    assert len(cloudflare.appels) == 1
    t["v"] = 1001.0
    reseau.serveurs_ice()
    assert len(cloudflare.appels) == 2


def test_cloudflare_en_panne_retombe_sur_le_stun_sans_insister(app, cloudflare):
    cloudflare.erreur = urllib.error.HTTPError("u", 401, "Unauthorized", {}, None)
    reseau = app.state.services.reseau
    assert reseau.serveurs_ice() == [STUN]
    assert "401" in reseau.etat()["cloudflare"]["erreur"]
    assert "jeton-secret" not in json.dumps(reseau.etat())
    for _ in range(4):
        reseau.serveurs_ice()
    assert len(cloudflare.appels) == 1  # pause après un échec : le chargement des pages n'est pas ralenti


def test_cloudflare_reponse_inattendue(app, cloudflare):
    cloudflare.reponse = {"result": "bizarre"}
    assert app.state.services.reseau.serveurs_ice() == [STUN]


def test_cloudflare_non_configure_aucun_appel(app):
    faux = FauxCloudflare(REPONSE_CLOUDFLARE)
    app.state.services.reseau._ouvrir = faux
    assert app.state.services.reseau.serveurs_ice() == [STUN] and faux.appels == []


def test_le_turn_saisi_l_emporte_sur_cloudflare(connecte, app, cloudflare):
    connecte.put("/reseau/turn", json=TURN)
    assert app.state.services.reseau.serveurs_ice()[1]["username"] == "awa" and cloudflare.appels == []


def test_cloudflare_donne_aux_deux_navigateurs_et_au_test(connecte, anonyme, entretien, cloudflare):  # noqa: F811
    assert connecte.get("/reseau").json()["cloudflare"] == {"configure": True, "erreur": None}
    candidat = anonyme.get(f"/public/api/{entretien['code_invitation']}").json()["ice"]
    recruteur = connecte.post(f"/entretiens/{entretien['id']}/salle").json()["ice"]
    assert candidat == recruteur and candidat[1]["username"] == "u-temporaire"
    assert connecte.get("/reseau/test").json()["ice"] == candidat


def test_test_cloudflare_explique_l_echec_et_reessaie_aussitot(connecte, app, cloudflare):
    cloudflare.erreur = urllib.error.HTTPError("u", 403, "Forbidden", {}, None)
    app.state.services.reseau.serveurs_ice()  # échec : pause de 60 s
    reponse = connecte.get("/reseau/test")
    assert reponse.status_code == 503 and "403" in reponse.json()["detail"]
    assert len(cloudflare.appels) == 2  # le test n'attend pas la pause
    cloudflare.erreur = None
    assert connecte.get("/reseau/test").status_code == 200
