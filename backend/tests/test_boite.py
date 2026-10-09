"""Connexion de la boîte en une fois (détection d'après l'adresse) et assistant de démarrage."""
from __future__ import annotations

import pytest

from backend.services.detection_boite import DetectionBoite
from backend.services.erreurs import ErreurValidation


def detection(mx=(), repondent=(), google=True):
    appels = []

    def repond(hote):
        appels.append(hote)
        return hote in repondent

    return DetectionBoite(lambda: google, serveurs_mx=lambda domaine: list(mx), repond=repond), appels


def test_adresses_grand_public():
    d, _ = detection()
    gmail = d.detecter("Rh.Cabinet@Gmail.com ")
    assert (gmail.fournisseur, gmail.methode, gmail.hote) == ("Gmail", "google", "imap.gmail.com")
    yahoo = d.detecter("rh@yahoo.fr")
    assert yahoo.methode == "mot_de_passe" and yahoo.mot_de_passe_application and yahoo.lien and len(yahoo.etapes) == 4
    outlook = d.detecter("rh@hotmail.fr")
    assert outlook.methode == "impossible" and "Outlook" in outlook.avertissement


def test_gmail_sans_connexion_google_configuree_mot_de_passe_guide():
    d, _ = detection(google=False)
    gmail = d.detecter("rh@gmail.com")
    assert gmail.methode == "mot_de_passe" and gmail.mot_de_passe_application
    assert gmail.lien == "https://myaccount.google.com/apppasswords" and "Validation en deux étapes" in " ".join(gmail.etapes)


@pytest.mark.parametrize(
    ("mx", "fournisseur", "methode", "hote"),
    [
        (["aspmx.l.google.com"], "Google Workspace", "google", "imap.gmail.com"),
        (["cabinet-cm.mail.protection.outlook.com"], "Microsoft 365", "mot_de_passe", "outlook.office365.com"),
        (["mx1.mail.ovh.net", "mx2.mail.ovh.net"], "OVHcloud", "mot_de_passe", "ssl0.ovh.net"),
        (["mx1.spacemail.com", "mx2.spacemail.com"], "Spacemail", "mot_de_passe", "mail.spacemail.com"),
    ],
)
def test_domaine_de_l_entreprise_reconnu_a_ses_serveurs(mx, fournisseur, methode, hote):
    d, _ = detection(mx=mx)
    r = d.detecter("rh@cabinet.cm")
    assert (r.fournisseur, r.methode, r.hote) == (fournisseur, methode, hote)
    assert (r.avertissement is not None) == (fournisseur == "Microsoft 365")


def test_hebergeur_inconnu_serveurs_habituels_essayes():
    d, appels = detection(mx=["mail.cabinet.cm"], repondent={"mail.cabinet.cm"})
    r = d.detecter("rh@cabinet.cm")
    assert (r.fournisseur, r.methode, r.hote) == ("votre hébergeur", "mot_de_passe", "mail.cabinet.cm")
    assert sorted(appels) == ["imap.cabinet.cm", "mail.cabinet.cm"]
    d.detecter("autre@cabinet.cm")
    assert len(appels) == 2  # résultat gardé pour le domaine


def test_serveur_de_l_hebergeur_des_mx_essaye():
    """mail.domaine accepte la connexion mais ne répond pas comme une boîte : on essaie le serveur de l'hébergeur."""
    d, appels = detection(mx=["mx1.petithebergeur.net"], repondent={"mail.petithebergeur.net"})
    r = d.detecter("rh@cabinet.cm")
    assert r.hote == "mail.petithebergeur.net"
    assert sorted(appels) == sorted(
        ["imap.cabinet.cm", "mail.cabinet.cm", "imap.petithebergeur.net", "mail.petithebergeur.net", "mx1.petithebergeur.net"]
    )


def test_serveur_introuvable_et_adresse_invalide():
    d, _ = detection()
    assert d.detecter("rh@inconnu.cm").hote is None
    for mauvaise in ("", "rh", "rh@local", "a b@x.cm"):
        with pytest.raises(ErreurValidation):
            d.detecter(mauvaise)


def test_serveur_smtp_deduit_pour_les_hebergeurs_connus():
    from backend.services.expediteur_smtp import deviner_serveur

    assert deviner_serveur("rh@cabinet.cm", "outlook.office365.com") == ("smtp.office365.com", [587])
    assert deviner_serveur("rh@cabinet.cm", "ssl0.ovh.net") == ("ssl0.ovh.net", [465])
    assert deviner_serveur("rh@cabinet.cm", "imap.gmail.com") == ("smtp.gmail.com", [465, 587])


# --- API (mode démo de l'agent mail) ---------------------------------------------------------------------------


def test_connexion_par_mot_de_passe_en_une_fois(connecte, app):
    r = connecte.get("/boite/detection", params={"email": "rh@yahoo.fr"})
    assert r.status_code == 200 and r.json()["fournisseur"] == "Yahoo"
    assert connecte.get("/boite").json()["fournisseur"] == "fake"  # mode démo : boîte simulée déjà liée

    refus = connecte.post("/boite/mot-de-passe", json={"email": "rh@yahoo.fr", "mot_de_passe": "mauvais"})
    assert refus.status_code == 422 and "mot de passe d'application" in refus.json()["champs"]["mot_de_passe"]

    app.state.services.boite.detection._mx = lambda domaine: []
    app.state.services.boite.detection._repond = lambda hote: False
    sans_serveur = connecte.post("/boite/mot-de-passe", json={"email": "rh@cabinet.cm", "mot_de_passe": "x"})
    assert sans_serveur.status_code == 422 and "hote" in sans_serveur.json()["champs"]

    ok = connecte.post("/boite/mot-de-passe", json={"email": "rh@cabinet.cm", "mot_de_passe": "secret", "hote": "mail.cabinet.cm"})
    assert ok.status_code == 200, ok.text
    etat = ok.json()
    assert etat["connectee"] is True and etat["email"] == "rh@cabinet.cm" and etat["fournisseur"] == "imap"
    assert etat["envoi"]["autorise"] is True  # mode démo : envoi simulé


def test_connexion_google_mode_demo(connecte):
    r = connecte.post("/boite/google", json={"email": "rh@gmail.com"})
    assert r.status_code == 200, r.text
    assert r.json()["connectee"] is True and r.json()["envoi"]["autorise"] is True


def test_adresse_outlook_refusee_simplement(connecte):
    r = connecte.post("/boite/mot-de-passe", json={"email": "rh@outlook.com", "mot_de_passe": "x"})
    assert r.status_code == 422 and "Outlook" in r.json()["champs"]["email"]


def test_assistant_de_demarrage(connecte):
    assert connecte.get("/accueil").json() == {"a_faire": True, "entreprise": False, "boite": True}  # boîte simulée
    connecte.put("/entreprise", json={"nom": "Cabinet Ndong"})
    connecte.post("/boite/google", json={})
    assert connecte.get("/accueil").json() == {"a_faire": False, "entreprise": True, "boite": True}


def test_assistant_passe_plus_tard(connecte):
    assert connecte.put("/accueil/termine").json()["a_faire"] is False
    assert connecte.get("/accueil").json()["a_faire"] is False


def test_routes_protegees(client):
    for chemin in ("/boite", "/accueil", "/boite/detection?email=a@b.cm"):
        assert client.get(chemin).status_code == 401
