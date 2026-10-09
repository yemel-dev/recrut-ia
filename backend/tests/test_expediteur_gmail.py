"""Expéditeur Gmail : autorisation séparée, compte vérifié, message dans le fil — sans jamais appeler Google."""
from __future__ import annotations

import base64
import email
import json
from datetime import datetime, timedelta, timezone
from email import policy

import pytest

google_creds = pytest.importorskip("google.oauth2.credentials")

from backend.services.erreurs import Conflit  # noqa: E402
from backend.services.expediteur import EchecEnvoi, FilOrigine, MailSortant  # noqa: E402
from backend.services.expediteur_gmail import SCOPES_ENVOI, GmailExpediteur, raison_lisible  # noqa: E402


def identifiants(scopes=SCOPES_ENVOI, expire_dans=timedelta(hours=1)):
    return google_creds.Credentials(
        token="jeton", refresh_token="rafraichir", client_id="id", client_secret="secret",
        token_uri="https://oauth2.googleapis.com/token", scopes=scopes,
        expiry=(datetime.now(timezone.utc) + expire_dans).replace(tzinfo=None),
    )


class _Execute:
    def __init__(self, resultat=None, erreur=None):
        self.resultat, self.erreur = resultat, erreur

    def execute(self):
        if self.erreur:
            raise self.erreur
        return self.resultat


class FauxGmail:
    """Imite service.users().messages().send/get et users().getProfile."""

    def __init__(self, compte="recrutement@cabinet.cm", erreur_envoi=None):
        self.compte, self.erreur_envoi, self.envoyes = compte, erreur_envoi, []

    def users(self):
        return self

    def messages(self):
        return self

    def getProfile(self, userId):
        return _Execute({"emailAddress": self.compte})

    def get(self, userId, id, format, metadataHeaders):
        if id == "inconnu":
            return _Execute(erreur=RuntimeError("404"))
        return _Execute({"threadId": f"fil-{id}", "payload": {"headers": [{"name": "Message-ID", "value": f"<{id}@mail.gmail.com>"}]}})

    def send(self, userId, body):
        self.envoyes.append(body)
        return _Execute({"id": f"envoye-{len(self.envoyes)}"}, self.erreur_envoi)


def expediteur(tmp_path, compte_lecture=("gmail_oauth", "recrutement@cabinet.cm"), service=None, flux=None):
    credentials = tmp_path / "credentials.json"
    credentials.write_text("{}", encoding="utf-8")
    service = service or FauxGmail()
    return GmailExpediteur(
        credentials, tmp_path / "secrets" / "jeton_envoi_gmail.json", lambda: compte_lecture,
        fabrique_service=lambda creds: service, flux_autorisation=flux or (lambda chemin, scopes: identifiants()),
    ), service


def test_pas_encore_autorise_puis_autorise(tmp_path):
    exp, _ = expediteur(tmp_path)
    etat = exp.etat()
    assert etat["autorise"] is False and "Autoriser l'envoi" in etat["motif"] and etat["reconnexion"] is False
    etat = exp.autoriser()
    assert etat == {"autorise": True, "compte": "recrutement@cabinet.cm", "motif": None, "reconnexion": False}
    stocke = json.loads((tmp_path / "secrets" / "jeton_envoi_gmail.json").read_text(encoding="utf-8"))
    assert stocke["compte"] == "recrutement@cabinet.cm" and set(stocke["jeton"]["scopes"]) == set(SCOPES_ENVOI)


def test_autre_compte_refuse(tmp_path):
    exp, _ = expediteur(tmp_path, service=FauxGmail(compte="perso@gmail.com"))
    with pytest.raises(Conflit, match="perso@gmail.com"):
        exp.autoriser()
    assert not (tmp_path / "secrets" / "jeton_envoi_gmail.json").exists()


def test_autorisations_incompletes_refusees(tmp_path):
    exp, _ = expediteur(tmp_path, flux=lambda chemin, scopes: identifiants(scopes=[SCOPES_ENVOI[1]]))
    with pytest.raises(Conflit, match="toutes les autorisations"):
        exp.autoriser()


def test_boite_imap_ou_non_liee(tmp_path):
    imap, _ = expediteur(tmp_path, compte_lecture=("imap", "rh@cabinet.cm"))
    assert "IMAP" in imap.etat()["motif"]
    with pytest.raises(Conflit):
        imap.autoriser()
    aucune, _ = expediteur(tmp_path, compte_lecture=(None, None))
    assert "Liez d'abord" in aucune.etat()["motif"]


def test_compte_de_lecture_change_reconnexion(tmp_path):
    exp, _ = expediteur(tmp_path)
    exp.autoriser()
    exp.compte_lecture = lambda: ("gmail_oauth", "autre@cabinet.cm")
    etat = exp.etat()
    assert etat["autorise"] is False and etat["reconnexion"] is True and "autre@cabinet.cm" in etat["motif"]


def test_jeton_expire_sans_rafraichissement_possible(tmp_path):
    exp, _ = expediteur(tmp_path, flux=lambda chemin, scopes: identifiants(expire_dans=timedelta(hours=-1)))
    jeton = tmp_path / "secrets" / "jeton_envoi_gmail.json"
    jeton.parent.mkdir(parents=True)
    expire = identifiants(expire_dans=timedelta(hours=-1))
    donnees = json.loads(expire.to_json())
    donnees.pop("refresh_token")
    jeton.write_text(json.dumps({"jeton": donnees, "compte": "recrutement@cabinet.cm"}), encoding="utf-8")
    etat = exp.etat()
    assert etat["reconnexion"] is True and "reconnectez" in etat["motif"]


def test_envoi_dans_le_fil(tmp_path):
    exp, service = expediteur(tmp_path)
    exp.autoriser()
    fil = exp.fil("18c2a")
    assert fil == FilOrigine(thread_id="fil-18c2a", message_id="<18c2a@mail.gmail.com>", references="")
    assert exp.fil("inconnu") is None
    identifiant = exp.envoyer(MailSortant("awa@x.cm", "Re: Candidature DEV", "Bonjour Awa Ndong,\n\nÀ bientôt.", fil))
    assert identifiant == "envoye-1"
    corps = service.envoyes[0]
    assert corps["threadId"] == "fil-18c2a"
    message = email.message_from_bytes(base64.urlsafe_b64decode(corps["raw"]), policy=policy.default)
    assert message["To"] == "awa@x.cm" and message["From"] == "recrutement@cabinet.cm"
    assert message["In-Reply-To"] == "<18c2a@mail.gmail.com>" and message["Subject"] == "Re: Candidature DEV"
    assert message.get_content().strip() == "Bonjour Awa Ndong,\n\nÀ bientôt."


def test_echec_de_l_api_lisible(tmp_path):
    class ErreurHttp(Exception):
        def __init__(self, statut):
            super().__init__(f"HTTP {statut}")
            self.resp = type("Reponse", (), {"status": statut})()

    exp, _ = expediteur(tmp_path, service=FauxGmail(erreur_envoi=ErreurHttp(403)))
    exp.autoriser()
    with pytest.raises(EchecEnvoi, match="Reconnectez"):
        exp.envoyer(MailSortant("awa@x.cm", "Objet", "Corps"))
    assert "Limite" in raison_lisible(ErreurHttp(429))
    assert "invalide" in raison_lisible(ErreurHttp(400))


def test_revoquer(tmp_path):
    exp, _ = expediteur(tmp_path)
    exp.autoriser()
    assert exp.revoquer()["autorise"] is False
    with pytest.raises(EchecEnvoi):
        exp.envoyer(MailSortant("awa@x.cm", "Objet", "Corps"))


def test_mode_demo_pas_d_autorisation_a_donner(connecte):
    assert connecte.get("/mails/autorisation").json()["simule"] is True
    assert connecte.post("/mails/autorisation").status_code == 409
