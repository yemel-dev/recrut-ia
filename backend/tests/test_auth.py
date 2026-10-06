from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.config import Settings
from backend.services import cles

from .conftest import EMAIL, JETON, KDF_RAPIDE, MOT_DE_PASSE


# --- Jeton de lancement ------------------------------------------------------------


def test_sans_jeton_toute_requete_est_refusee(app):
    brut = TestClient(app)
    assert brut.get("/auth/etat").status_code == 401
    assert brut.post("/auth/compte", json={"email": EMAIL, "mot_de_passe": MOT_DE_PASSE}).status_code == 401


def test_mauvais_jeton_refuse(app):
    assert TestClient(app, headers={"X-Injara-Token": "faux"}).get("/auth/etat").status_code == 401


def test_le_backend_refuse_de_demarrer_sans_jeton(tmp_path):
    with pytest.raises(RuntimeError):
        create_app(Settings(data_dir=tmp_path, token="", kdf=KDF_RAPIDE))


def test_pas_de_documentation_exposee(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


# --- Premier lancement et création du compte --------------------------------------


def test_premier_lancement_aucun_compte(client):
    assert client.get("/auth/etat").json() == {"compte_existe": False, "connecte": False, "email": None}


def test_creation_renvoie_une_cle_de_recuperation(client, cle_recuperation):
    assert re.fullmatch(r"[A-Z2-7]{4}(-[A-Z2-7]{4}){7}", cle_recuperation)
    etat = client.get("/auth/etat").json()
    assert etat["compte_existe"] is True
    assert etat["connecte"] is False  # la création ne connecte pas : on passe par l'écran de connexion


@pytest.mark.parametrize(
    ("email", "mot_de_passe", "champ"),
    [
        ("pas-un-email", MOT_DE_PASSE, "email"),
        (EMAIL, "court", "mot_de_passe"),
        (EMAIL, "onze-caract", "mot_de_passe"),
        (EMAIL, " " * 20, "mot_de_passe"),
    ],
)
def test_creation_valide_les_champs(client, email, mot_de_passe, champ):
    reponse = client.post("/auth/compte", json={"email": email, "mot_de_passe": mot_de_passe})
    assert reponse.status_code == 422
    assert champ in reponse.json()["champs"]
    assert client.get("/auth/etat").json()["compte_existe"] is False


def test_douze_caracteres_suffisent(client):
    assert client.post("/auth/compte", json={"email": EMAIL, "mot_de_passe": "a" * 12}).status_code == 201


def test_champ_manquant_message_en_francais(client):
    reponse = client.post("/auth/compte", json={"email": EMAIL})
    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {"mot_de_passe": "Champ obligatoire."}


def test_un_seul_compte_par_installation(client, cle_recuperation):
    reponse = client.post("/auth/compte", json={"email": "autre@x.cm", "mot_de_passe": MOT_DE_PASSE})
    assert reponse.status_code == 409


def test_mot_de_passe_et_cle_jamais_stockes_en_clair(app, client, cle_recuperation):
    compte = app.state.services.auth.comptes.get()
    contenu = repr(compte).encode()
    assert MOT_DE_PASSE.encode() not in contenu
    assert cle_recuperation.encode() not in contenu
    assert compte["mot_de_passe_hash"].startswith("$argon2id$")


# --- Connexion / déconnexion -------------------------------------------------------


def test_connexion_ouvre_une_session(connecte):
    assert connecte.get("/auth/etat").json() == {"compte_existe": True, "connecte": True, "email": EMAIL}


def test_connexion_insensible_a_la_casse_de_l_email(client, cle_recuperation):
    reponse = client.post("/auth/connexion", json={"email": "  RH@Entreprise.CM ", "mot_de_passe": MOT_DE_PASSE})
    assert reponse.status_code == 200


@pytest.mark.parametrize(("email", "mot_de_passe"), [(EMAIL, "mauvais-mot-de-passe"), ("autre@x.cm", MOT_DE_PASSE)])
def test_connexion_refusee_message_identique(client, cle_recuperation, email, mot_de_passe):
    reponse = client.post("/auth/connexion", json={"email": email, "mot_de_passe": mot_de_passe})
    assert reponse.status_code == 401
    assert reponse.json()["detail"] == "Email ou mot de passe incorrect."


def test_connexion_sans_compte(client):
    assert client.post("/auth/connexion", json={"email": EMAIL, "mot_de_passe": MOT_DE_PASSE}).status_code == 401


def test_deconnexion_invalide_la_session(connecte):
    assert connecte.post("/auth/deconnexion").status_code == 204
    assert connecte.get("/auth/etat").json()["connecte"] is False


def test_session_perdue_au_redemarrage(settings, connecte):
    """La session vit en mémoire : un nouveau backend (même base) ne la connaît pas."""
    jeton_session = connecte.headers["X-Injara-Session"]
    nouvelle_app = create_app(settings)
    try:
        client = TestClient(nouvelle_app, headers={"X-Injara-Token": JETON, "X-Injara-Session": jeton_session})
        assert client.get("/auth/etat").json() == {"compte_existe": True, "connecte": False, "email": None}
    finally:
        nouvelle_app.state.db.close()


def test_cle_de_donnees_disponible_en_session(app, connecte):
    auth = app.state.services.auth
    cle = auth.cle_de_donnees(connecte.headers["X-Injara-Session"])
    assert len(cle) == 32


# --- Mot de passe oublié ------------------------------------------------------------


def test_recuperation_change_le_mot_de_passe_et_conserve_la_cle_de_donnees(app, client, cle_recuperation):
    auth = app.state.services.auth
    jeton = client.post("/auth/connexion", json={"email": EMAIL, "mot_de_passe": MOT_DE_PASSE}).json()["jeton_session"]
    cle_avant = auth.cle_de_donnees(jeton)

    nouveau = "un-tout-nouveau-mot-de-passe"
    reponse = client.post("/auth/recuperation", json={"cle_de_recuperation": cle_recuperation, "nouveau_mot_de_passe": nouveau})
    assert reponse.status_code == 200
    nouvelle_cle_recuperation = reponse.json()["cle_de_recuperation"]
    assert nouvelle_cle_recuperation != cle_recuperation

    # La récupération ferme la session ouverte
    assert auth.session_valide(jeton) is None
    # L'ancien mot de passe ne marche plus, le nouveau oui, et la clé de données est la même
    assert client.post("/auth/connexion", json={"email": EMAIL, "mot_de_passe": MOT_DE_PASSE}).status_code == 401
    jeton = client.post("/auth/connexion", json={"email": EMAIL, "mot_de_passe": nouveau}).json()["jeton_session"]
    assert auth.cle_de_donnees(jeton) == cle_avant

    # L'ancienne clé de récupération est révoquée, la nouvelle fonctionne
    assert client.post("/auth/recuperation", json={"cle_de_recuperation": cle_recuperation, "nouveau_mot_de_passe": nouveau}).status_code == 422
    assert client.post("/auth/recuperation", json={"cle_de_recuperation": nouvelle_cle_recuperation, "nouveau_mot_de_passe": nouveau}).status_code == 200


def test_recuperation_tolere_la_saisie(client, cle_recuperation):
    saisie = cle_recuperation.lower().replace("-", " ")
    reponse = client.post("/auth/recuperation", json={"cle_de_recuperation": saisie, "nouveau_mot_de_passe": "a" * 12})
    assert reponse.status_code == 200


def test_recuperation_mauvaise_cle(client, cle_recuperation):
    reponse = client.post("/auth/recuperation", json={"cle_de_recuperation": "AAAA-BBBB-CCCC-DDDD-EEEE-FFFF-GGGG-HHHH", "nouveau_mot_de_passe": "a" * 12})
    assert reponse.status_code == 422
    assert reponse.json()["champs"] == {"cle_de_recuperation": "Clé de récupération incorrecte."}


def test_recuperation_valide_le_nouveau_mot_de_passe(client, cle_recuperation):
    reponse = client.post("/auth/recuperation", json={"cle_de_recuperation": cle_recuperation, "nouveau_mot_de_passe": "court"})
    assert reponse.status_code == 422
    assert "nouveau_mot_de_passe" in reponse.json()["champs"]


# --- Primitives de chiffrement ------------------------------------------------------


def test_enveloppe_aller_retour_et_alteration_detectee():
    cle, protection = cles.nouvelle_cle_de_donnees(), cles.nouvelle_cle_de_donnees()
    chiffre = cles.envelopper(cle, protection)
    assert cles.desenvelopper(chiffre, protection) == cle
    with pytest.raises(cles.CleInvalide):
        cles.desenvelopper(chiffre, cles.nouvelle_cle_de_donnees())
    altere = chiffre[:-1] + bytes([chiffre[-1] ^ 1])
    with pytest.raises(cles.CleInvalide):
        cles.desenvelopper(altere, protection)
