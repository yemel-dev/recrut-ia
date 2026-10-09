"""Envoi des mails aux candidats par l'API Gmail.

- Une seule fenêtre Google donne la lecture (gmail.readonly, pour l'agent mail) et l'envoi (gmail.send) : c'est la
  connexion de la boîte (assistant de démarrage, page Boîte mail). Le même accord est rangé dans deux jetons : celui
  de l'agent (lecture, inchangé pour lui) et <données>/secrets/jeton_envoi_gmail.json pour l'envoi.
- gmail.readonly suffit aussi pour lire l'identifiant du fil et les en-têtes du mail de candidature, et l'adresse du
  compte. (gmail.metadata n'est pas demandé : il interdirait la recherche de l'agent dans la boîte.)
- Le compte autorisé doit être celui qui lit les candidatures.
- Une boîte liée par IMAP passe par SMTP (services/expediteur_smtp.py).
"""
from __future__ import annotations

import base64
import json
import logging
import threading
from pathlib import Path
from typing import Any, Callable

from .erreurs import Conflit
from .expediteur import EchecEnvoi, FilOrigine, MailSortant, construire_mime

log = logging.getLogger("injara.mails.gmail")

SCOPES_ENVOI = ["https://www.googleapis.com/auth/gmail.send", "https://www.googleapis.com/auth/gmail.readonly"]
NOM_JETON = "jeton_envoi_gmail.json"


def _reconnexion(motif: str) -> dict:
    return {"autorise": False, "compte": None, "motif": motif, "reconnexion": True}


class GmailExpediteur:
    def __init__(
        self,
        credentials_path: Path,
        token_path: Path,
        compte_lecture: Callable[[], tuple[str | None, str | None]],
        fabrique_service: Callable[[Any], Any] | None = None,
        flux_autorisation: Callable[[Path, list[str]], Any] | None = None,
        jeton_lecture: Path | None = None,
    ) -> None:
        """compte_lecture() -> (fournisseur, adresse) du compte qui lit les candidatures (agent mail) ;
        jeton_lecture : jeton de l'agent mail, écrit avec le même accord Google."""
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.jeton_lecture = jeton_lecture
        self.compte_lecture = compte_lecture
        self._fabrique_service = fabrique_service or _service_gmail
        self._flux = flux_autorisation or _flux_navigateur
        self._lock = threading.Lock()
        self._service = None

    # --- État et autorisation -----------------------------------------------------------------------------------

    def etat(self) -> dict:
        fournisseur, adresse = self.compte_lecture()
        if fournisseur is None:
            return {"autorise": False, "compte": None, "motif": "Liez d'abord la boîte mail de recrutement (page Boîte mail).", "reconnexion": False}
        if fournisseur != "gmail_oauth":
            return {
                "autorise": False, "compte": None, "reconnexion": False,
                "motif": "L'envoi passe par un compte Gmail connecté avec Google. Votre boîte est liée par IMAP : l'envoi n'est pas disponible.",
            }
        if not self.token_path.exists():
            return {"autorise": False, "compte": None, "motif": "Google n'a pas encore autorisé l'envoi depuis cette boîte : reconnectez-la une fois.", "reconnexion": False}
        try:
            creds, compte = self._identifiants()
        except EchecEnvoi as exc:
            return _reconnexion(exc.raison)
        if adresse and compte and compte.lower() != adresse.lower():
            return _reconnexion(f"L'envoi est autorisé pour {compte}, mais les candidatures arrivent sur {adresse} : reconnectez le bon compte.")
        return {"autorise": True, "compte": compte, "motif": None, "reconnexion": False}

    def autoriser(self) -> dict:
        """Reconnexion depuis Paramètres › Mails aux candidats : même fenêtre Google que la connexion de la boîte."""
        fournisseur, adresse = self.compte_lecture()
        if fournisseur != "gmail_oauth":
            raise Conflit("Liez d'abord la boîte Gmail de recrutement avec Google (page Boîte mail).")
        self.connecter(adresse_attendue=adresse)
        return self.etat()

    def connecter(self, adresse_attendue: str | None = None) -> str:
        """Ouvre le navigateur sur la page Google (bloque jusqu'à la fin) : lecture et envoi d'un seul accord.
        Range l'accord pour l'envoi et pour l'agent mail, puis renvoie l'adresse du compte."""
        if not self.credentials_path.exists():
            raise Conflit("La connexion avec Google n'est pas configurée sur cet ordinateur : utilisez le mot de passe de la boîte.")
        creds = self._flux(self.credentials_path, SCOPES_ENVOI)
        if not set(SCOPES_ENVOI) <= set(creds.scopes or []):
            raise Conflit("Google n'a pas tout autorisé : recommencez et laissez cochées toutes les cases proposées par Google.")
        compte = self._fabrique_service(creds).users().getProfile(userId="me").execute().get("emailAddress", "")
        if adresse_attendue and compte.lower() != adresse_attendue.lower():
            raise Conflit(f"Vous vous êtes connecté avec {compte}, mais les candidatures arrivent sur {adresse_attendue}. Recommencez avec ce compte.")
        with self._lock:
            _ecrire_secret(self.token_path, json.dumps({"jeton": json.loads(creds.to_json()), "compte": compte}))
            if self.jeton_lecture is not None:
                _ecrire_secret(self.jeton_lecture, creds.to_json())  # format attendu par l'agent mail
            self._service = None
        log.info("Boîte Google connectée (lecture et envoi) : %s", compte)
        return compte

    def revoquer(self) -> dict:
        with self._lock:
            self.token_path.unlink(missing_ok=True)
            self._service = None
        return self.etat()

    # --- Envoi --------------------------------------------------------------------------------------------------

    def fil(self, message_id: str) -> FilOrigine | None:
        try:
            message = (
                self._service_envoi()
                .users().messages()
                .get(userId="me", id=message_id, format="metadata", metadataHeaders=["Message-ID", "References"])
                .execute()
            )
        except EchecEnvoi:
            raise
        except Exception as exc:  # message supprimé, identifiant d'une autre boîte…
            log.info("Fil introuvable pour %s : %s", message_id, exc)
            return None
        entetes = {h["name"].lower(): h["value"] for h in message.get("payload", {}).get("headers", [])}
        if not message.get("threadId") or not entetes.get("message-id"):
            return None
        return FilOrigine(thread_id=message["threadId"], message_id=entetes["message-id"], references=entetes.get("references", ""))

    def envoyer(self, mail: MailSortant) -> str:
        _, compte = self._identifiants()
        brut = base64.urlsafe_b64encode(construire_mime(mail, compte).as_bytes()).decode("ascii")
        corps = {"raw": brut}
        if mail.fil:
            corps["threadId"] = mail.fil.thread_id
        try:
            return self._service_envoi().users().messages().send(userId="me", body=corps).execute()["id"]
        except EchecEnvoi:
            raise
        except Exception as exc:
            raise EchecEnvoi(raison_lisible(exc)) from exc

    # --- Interne ------------------------------------------------------------------------------------------------

    def _identifiants(self):
        """Jeton d'envoi valide (rafraîchi si besoin) et adresse du compte. Lève EchecEnvoi s'il faut reconnecter."""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
        except ImportError as exc:
            raise EchecEnvoi("Bibliothèques Google absentes (google-auth-oauthlib).") from exc
        if not self.token_path.exists():
            raise EchecEnvoi("L'envoi de mails n'est pas autorisé.")
        try:
            donnees = json.loads(self.token_path.read_text(encoding="utf-8"))
            creds = Credentials.from_authorized_user_info(donnees["jeton"], SCOPES_ENVOI)
        except Exception as exc:
            raise EchecEnvoi("Autorisation d'envoi illisible : reconnectez le compte.") from exc
        if not creds.valid:
            if not (creds.expired and creds.refresh_token):
                raise EchecEnvoi("Autorisation d'envoi expirée : reconnectez le compte.")
            try:
                creds.refresh(Request())
            except Exception as exc:
                raise EchecEnvoi("Autorisation d'envoi retirée ou expirée : reconnectez le compte.") from exc
            with self._lock:
                self.token_path.write_text(json.dumps({**donnees, "jeton": json.loads(creds.to_json())}), encoding="utf-8")
        return creds, donnees.get("compte")

    def _service_envoi(self):
        with self._lock:
            if self._service is None:
                creds, _ = self._identifiants()
                self._service = self._fabrique_service(creds)
            return self._service


def _ecrire_secret(chemin: Path, contenu: str) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(contenu, encoding="utf-8")
    try:
        chemin.chmod(0o600)
    except OSError:  # sans effet sous Windows
        pass


def raison_lisible(exc: Exception) -> str:
    """Message d'échec compréhensible par le recruteur."""
    statut = getattr(getattr(exc, "resp", None), "status", None)
    if statut in (401, 403):
        return "Gmail refuse l'envoi : l'autorisation a été retirée ou ne suffit plus. Reconnectez le compte."
    if statut == 400:
        return "Gmail a refusé ce message (adresse du destinataire invalide ?)."
    if statut == 429:
        return "Limite d'envoi Gmail atteinte : réessayez plus tard."
    if statut and statut >= 500:
        return "Gmail est momentanément indisponible : réessayez plus tard."
    return f"Envoi impossible : {exc}"


def _service_gmail(creds):
    from googleapiclient.discovery import build

    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _flux_navigateur(credentials_path: Path, scopes: list[str]):
    from google_auth_oauthlib.flow import InstalledAppFlow

    flux = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes)
    return flux.run_local_server(port=0, prompt="consent")
