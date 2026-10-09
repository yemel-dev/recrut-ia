"""Modèles de mail, variables et mode test."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.api.app import create_app
from backend.database.repositories import ParametreRepository
from backend.services import modeles_mail as m
from backend.services.reglages_mails import ReglagesMailsService


def test_modeles_par_defaut_du_cahier():
    assert m.MODELES_PAR_DEFAUT["invitation"]["objet"] == "Votre candidature au poste de {poste} – invitation à un entretien"
    assert m.MODELES_PAR_DEFAUT["refus"]["objet"] == "Votre candidature au poste de {poste}"
    for modele in m.MODELES_PAR_DEFAUT.values():
        assert m.variables_inconnues(modele["objet"] + modele["corps"]) == []
        assert "score" not in modele["corps"].lower() and "classement" not in modele["corps"].lower()


@pytest.mark.parametrize(
    ("nom", "attendu"),
    [
        ("Awa Ndong", "Awa Ndong"),
        ("Jean-Paul Fotso", "Jean-Paul Fotso"),
        (None, "Madame, Monsieur"),
        ("", "Madame, Monsieur"),
        ("Awa", "Madame, Monsieur"),  # un seul mot
        ("Curriculum Vitae 2024", "Madame, Monsieur"),  # chiffres
        ("cv_final@mail", "Madame, Monsieur"),
        ("Un Deux Trois Quatre Cinq", "Madame, Monsieur"),
        ("Expérience Professionnelle", "Madame, Monsieur"),  # titre de section pris pour un nom
        ("Compétences Techniques", "Madame, Monsieur"),
        ("Développeuse Python", "Madame, Monsieur"),
    ],
)
def test_civilite_nom(nom, attendu):
    assert m.civilite_nom(nom) == attendu


def test_remplir_et_ligne_message_vide():
    modele = "Bonjour {civilite_nom},\n\n{message}\n\nCordialement,\n{entreprise}"
    assert m.remplir(modele, {"civilite_nom": "Madame, Monsieur", "message": "", "entreprise": "INJARA"}) == (
        "Bonjour Madame, Monsieur,\n\nCordialement,\nINJARA"
    )
    assert "Pièce d'identité" in m.remplir(modele, {"message": "Pièce d'identité", "civilite_nom": "x", "entreprise": "y"})


def test_formats_de_date_et_duree():
    debut = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)
    local = debut.astimezone()
    assert m.formater_heure(debut) == f"{local.hour} h 00"
    assert m.formater_date(datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)).endswith("octobre 2026")
    assert (m.formater_duree(30), m.formater_duree(60), m.formater_duree(90), m.formater_duree(120)) == (
        "30 minutes", "1 heure", "1 h 30", "2 heures",
    )
    assert m.formater_lieu("en_ligne", None).startswith("en ligne")
    assert m.formater_lieu("sur_site", " Bonapriso, Douala ") == "Bonapriso, Douala"


# --- Réglages par l'API ---------------------------------------------------------------------------------------


def test_modifier_et_retablir_un_modele(connecte):
    reglages = connecte.get("/parametres/mails").json()
    assert reglages["modeles"]["refus"]["par_defaut"] is True
    assert reglages["variables"] == list(m.VARIABLES)

    r = connecte.put("/parametres/mails/modeles/refus", json={"objet": "Candidature {poste}", "corps": "Bonjour {civilite_nom}"})
    assert r.status_code == 200 and r.json()["modeles"]["refus"] == {"objet": "Candidature {poste}", "corps": "Bonjour {civilite_nom}", "par_defaut": False}

    r = connecte.put("/parametres/mails/modeles/refus", json={"objet": "Votre note : {score}", "corps": "x"})
    assert r.status_code == 422 and "{score}" in r.json()["champs"]["objet"]
    assert connecte.put("/parametres/mails/modeles/refus", json={"objet": "", "corps": ""}).status_code == 422
    assert connecte.put("/parametres/mails/modeles/inconnu", json={"objet": "a", "corps": "b"}).status_code == 422

    assert connecte.delete("/parametres/mails/modeles/refus").json()["modeles"]["refus"]["par_defaut"] is True


def test_apercu_avec_valeurs_d_exemple(connecte):
    connecte.put("/entreprise", json={"nom": "Cabinet Ndong"})
    modele = m.MODELES_PAR_DEFAUT["invitation"]
    apercu = connecte.post("/parametres/mails/modeles/invitation/apercu", json=modele).json()
    assert apercu["objet"] == "Votre candidature au poste de Développeur Python – invitation à un entretien"
    assert "Bonjour Awa Ndong," in apercu["corps"] and "Cabinet Ndong" in apercu["corps"] and "{" not in apercu["corps"]


def test_mode_test_actif_par_defaut_en_developpement(connecte):
    assert connecte.get("/parametres/mails").json()["mode_test"] == {"actif": True, "adresse": "", "par_defaut": True}
    assert connecte.put("/parametres/mails/mode-test", json={"actif": True, "adresse": ""}).status_code == 422
    assert connecte.put("/parametres/mails/mode-test", json={"actif": True, "adresse": "pas-une-adresse"}).status_code == 422
    r = connecte.put("/parametres/mails/mode-test", json={"actif": True, "adresse": "RH.Test@Exemple.cm"})
    assert r.json()["mode_test"] == {"actif": True, "adresse": "rh.test@exemple.cm", "par_defaut": False}
    assert connecte.put("/parametres/mails/mode-test", json={"actif": False, "adresse": ""}).json()["mode_test"]["actif"] is False


def test_mode_test_inactif_par_defaut_en_production(settings):
    import dataclasses

    app = create_app(dataclasses.replace(settings, environnement="production"))
    try:
        service = ReglagesMailsService(ParametreRepository(app.state.db), "production")
        assert service.mode_test()["actif"] is False
        assert app.state.services.reglages_mails.mode_test()["actif"] is False
    finally:
        app.state.services.traitement.arreter()
        app.state.db.close()


def test_reglages_exigent_la_session(client):
    assert client.get("/parametres/mails").status_code == 401
