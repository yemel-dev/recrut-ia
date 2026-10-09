"""Envoi par SMTP (boîtes liées par IMAP), avec de faux serveurs : aucune connexion réseau."""
from __future__ import annotations

import smtplib
from datetime import datetime, timedelta, timezone

import pytest

from backend.services.expediteur import EchecEnvoi, MailSortant
from backend.services.expediteur_smtp import CompteImap, SmtpExpediteur, deviner_serveur

from .test_envoi_mails import decider, ids, planifier, poste  # noqa: F401
from .test_traitement import boite, services  # noqa: F401

COMPTE = CompteImap("recrutement@cabinet.cm", "mot-de-passe", "imap.cabinet.cm", 993, "INBOX")


class FauxSmtp:
    def __init__(self, journal, hote, port, refus=None):
        self.journal, self.hote, self.port, self.refus = journal, hote, port, refus
        journal["connexions"].append((hote, port))

    def login(self, email, mot_de_passe):
        if self.refus:
            raise self.refus
        self.journal["logins"].append(email)

    def send_message(self, message):
        self.journal["envoyes"].append(message)

    def quit(self):
        pass


class FauxImap:
    def __init__(self, journal, validite="7", dossiers=(b'(\\HasNoChildren \\Sent) "/" "Sent Items"',)):
        self.journal, self.validite, self.dossiers = journal, validite, dossiers

    def login(self, email, mot_de_passe):
        pass

    def select(self, dossier, readonly=False):
        self.journal["selections"].append((dossier, readonly))
        return "OK", [b"1"]

    def response(self, code):
        return code, [self.validite.encode()]

    def uid(self, commande, uid, requete):
        return "OK", [(b"1 (BODY[HEADER.FIELDS (MESSAGE-ID REFERENCES)] {60}", f"Message-ID: <cv-{uid}@candidat.cm>\r\nReferences: <a@x>\r\n\r\n".encode())]

    def list(self):
        return "OK", list(self.dossiers)

    def append(self, dossier, drapeaux, date, message):
        self.journal["copies"].append(dossier)

    def logout(self):
        pass


def fabriquer(compte=COMPTE, reglage=None, refus_par_port=None, imap_validite="7", dossiers=None):
    journal = {"connexions": [], "logins": [], "envoyes": [], "selections": [], "copies": []}
    refus_par_port = refus_par_port or {}

    def smtp(hote, port):
        erreur = refus_par_port.get(port)
        if isinstance(erreur, OSError):
            journal["connexions"].append((hote, port))
            raise erreur
        return FauxSmtp(journal, hote, port, erreur)

    imap_options = {"validite": imap_validite}
    if dossiers is not None:
        imap_options["dossiers"] = dossiers
    exp = SmtpExpediteur(lambda: compte, lambda: reglage, connexion_smtp=smtp, connexion_imap=lambda h, p: FauxImap(journal, **imap_options))
    return exp, journal


@pytest.mark.parametrize(
    ("email", "imap", "attendu"),
    [
        ("rh@cabinet.cm", "imap.cabinet.cm", ("smtp.cabinet.cm", [465, 587])),
        ("rh@cabinet.cm", "mail.cabinet.cm", ("mail.cabinet.cm", [465, 587])),
        ("rh@gmail.com", "imap.gmail.com", ("smtp.gmail.com", [465])),
        ("rh@yahoo.fr", "imap.mail.yahoo.com", ("smtp.mail.yahoo.com", [465])),
        ("rh@outlook.com", "outlook.office365.com", ("smtp.office365.com", [587])),
    ],
)
def test_serveur_devine(email, imap, attendu):
    assert deviner_serveur(email, imap) == attendu


def test_connexion_testee_une_fois_puis_gardee(tmp_path):
    exp, journal = fabriquer()
    etat = exp.etat()
    assert etat["autorise"] is True and etat["compte"] == "recrutement@cabinet.cm" and etat["transport"] == "smtp"
    assert etat["serveur"] == {"hote": "smtp.cabinet.cm", "port": 465, "auto": True}
    exp.etat()
    assert len(journal["connexions"]) == 1  # résultat gardé
    exp.etat(retester=True)
    assert len(journal["connexions"]) == 2


def test_port_587_si_465_injoignable():
    exp, journal = fabriquer(refus_par_port={465: ConnectionRefusedError("refusé")})
    etat = exp.etat()
    assert etat["autorise"] is True and etat["serveur"]["port"] == 587
    assert journal["connexions"] == [("smtp.cabinet.cm", 465), ("smtp.cabinet.cm", 587)]


def test_mot_de_passe_refuse():
    exp, _ = fabriquer(refus_par_port={465: smtplib.SMTPAuthenticationError(535, b"5.7.8 Authentication failed")})
    etat = exp.etat()
    assert etat["autorise"] is False and "mot de passe" in etat["motif"]
    with pytest.raises(EchecEnvoi, match="mot de passe"):
        exp.envoyer(MailSortant("awa@gmail.com", "Objet", "Corps"))


def test_microsoft_365_explique():
    compte = CompteImap("rh@entreprise.cm", "x", "outlook.office365.com", 993, "INBOX")
    exp, _ = fabriquer(compte=compte, reglage={"hote": "smtp.office365.com", "port": 587},
                       refus_par_port={587: smtplib.SMTPAuthenticationError(535, b"5.7.139 Authentication unsuccessful, SmtpClientAuthentication is disabled")})
    assert "Microsoft 365" in exp.etat()["motif"]


def test_serveur_injoignable():
    exp, _ = fabriquer(refus_par_port={465: OSError("injoignable"), 587: OSError("injoignable")})
    etat = exp.etat()
    assert etat["autorise"] is False and "injoignable" in etat["motif"]


def test_reglage_manuel_du_serveur():
    exp, journal = fabriquer(reglage={"hote": "mail.ovh.net", "port": 587})
    assert exp.etat()["serveur"] == {"hote": "mail.ovh.net", "port": 587, "auto": False}
    assert journal["connexions"] == [("mail.ovh.net", 587)]


def test_envoi_dans_le_fil_et_copie_dans_envoyes():
    exp, journal = fabriquer()
    fil = exp.fil("imap-7-42")
    assert fil.message_id == "<cv-42@candidat.cm>" and fil.references == "<a@x>"
    assert journal["selections"] == [("INBOX", True)]  # lecture seule
    exp.envoyer(MailSortant("awa@gmail.com", "Re: Candidature", "Bonjour Awa Ndong,", fil))
    message = journal["envoyes"][0]
    assert message["From"] == "recrutement@cabinet.cm" and message["To"] == "awa@gmail.com"
    assert message["In-Reply-To"] == "<cv-42@candidat.cm>" and "<cv-42@candidat.cm>" in message["References"]
    assert journal["copies"] == ['"Sent Items"']


def test_fil_introuvable():
    exp, _ = fabriquer(imap_validite="8")
    assert exp.fil("imap-7-42") is None  # boîte renumérotée
    assert exp.fil("18c2a-gmail") is None  # pas un identifiant IMAP


def test_gmail_en_imap_pas_de_copie_et_sans_dossier_envoyes():
    compte = CompteImap("rh@gmail.com", "x", "imap.gmail.com", 993, "INBOX")
    exp, journal = fabriquer(compte=compte)
    exp.envoyer(MailSortant("awa@x.cm", "Objet", "Corps"))
    assert journal["copies"] == []  # Gmail range lui-même les messages envoyés
    exp2, journal2 = fabriquer(dossiers=(b'(\\HasNoChildren) "/" INBOX',))
    exp2.envoyer(MailSortant("awa@x.cm", "Objet", "Corps"))
    assert journal2["envoyes"] and journal2["copies"] == []  # pas de dossier « Envoyés » repérable : envoi quand même


def test_mot_de_passe_absent_du_coffre():
    exp = SmtpExpediteur(lambda: None, lambda: None)
    etat = exp.etat()
    assert etat["autorise"] is False and "reliez de nouveau" in etat["motif"]


# --- Avec le service d'envoi ---------------------------------------------------------------------------------


def test_invitation_par_smtp_dans_le_fil(connecte, services, poste, boite, tmp_path):  # noqa: F811
    exp, journal = fabriquer()
    services.envoi_mails.expediteur = lambda: exp
    a, _, _ = ids(services)
    services.candidatures.candidatures.maj(a, cle="imap-7-42")  # candidature reçue par une boîte IMAP
    decider(connecte, a, "retenu")
    planifier(connecte, a)
    preparation = connecte.get(f"/postes/{poste}/envois/invitation").json()
    assert preparation["autorisation"]["transport"] == "smtp" and preparation["blocages"] == []
    r = connecte.post(f"/postes/{poste}/envois/invitation", json={"candidatures": [a]}).json()
    assert r["envoyes"] == 1
    message = journal["envoyes"][0]
    assert message["To"] == "c0@x.cm" and message["In-Reply-To"] == "<cv-42@candidat.cm>"
    assert message["Subject"].startswith("Re: Candidature DEV-2026-04")


def test_reglage_du_serveur_par_l_api(connecte, services):  # noqa: F811
    assert connecte.put("/mails/smtp", json={"hote": "pas un hôte", "port": 587}).status_code == 422
    assert connecte.put("/mails/smtp", json={"hote": "smtp.cabinet.cm", "port": 0}).status_code == 422
    assert connecte.put("/mails/smtp", json={"hote": "smtp.cabinet.cm", "port": 587}).status_code == 200
    assert services.reglages_mails.serveur_smtp() == {"hote": "smtp.cabinet.cm", "port": 587}
    connecte.put("/mails/smtp", json={"hote": ""})
    assert services.reglages_mails.serveur_smtp() is None
