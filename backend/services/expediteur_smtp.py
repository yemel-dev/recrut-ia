"""Envoi des mails aux candidats par SMTP, pour les boîtes liées par IMAP (adresses pro hors Google, Yahoo…).

- Mêmes identifiants que la lecture : l'adresse et le mot de passe (d'application) déjà enregistrés par l'agent mail
  (coffre du système). L'agent mail n'est pas modifié : on lit seulement le compte qu'il a enregistré.
- Serveur d'envoi deviné d'après le serveur de lecture (imap.domaine → smtp.domaine), ports 465 (SSL) puis 587
  (STARTTLS) ; modifiable dans Paramètres › Mails aux candidats si la détection échoue.
- La connexion est testée avant le premier envoi (résultat gardé en mémoire tant que les réglages ne changent pas).
- Réponse dans le fil : l'en-tête Message-ID du mail de candidature est relu en IMAP (lecture seule).
- Une copie du mail envoyé est déposée dans le dossier « Envoyés » de la boîte quand il est repérable (sinon
  l'historique d'INJARA fait foi) ; Gmail le fait de lui-même.
- Microsoft 365 / Outlook désactive souvent l'envoi par mot de passe : le message d'erreur le dit.
"""
from __future__ import annotations

import hashlib
import imaplib
import logging
import re
import smtplib
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from .expediteur import EchecEnvoi, FilOrigine, MailSortant, construire_mime

log = logging.getLogger("injara.mails.smtp")

DELAI_S = 20
PORT_SSL, PORT_STARTTLS = 465, 587

# Serveurs d'envoi connus d'avance (domaine de l'adresse -> hôte, port)
SERVEURS_CONNUS: dict[str, tuple[str, int]] = {
    "gmail.com": ("smtp.gmail.com", PORT_SSL),
    "googlemail.com": ("smtp.gmail.com", PORT_SSL),
    "yahoo.com": ("smtp.mail.yahoo.com", PORT_SSL),
    "yahoo.fr": ("smtp.mail.yahoo.com", PORT_SSL),
    "ymail.com": ("smtp.mail.yahoo.com", PORT_SSL),
    "outlook.com": ("smtp.office365.com", PORT_STARTTLS),
    "hotmail.com": ("smtp.office365.com", PORT_STARTTLS),
    "hotmail.fr": ("smtp.office365.com", PORT_STARTTLS),
    "live.fr": ("smtp.office365.com", PORT_STARTTLS),
}
_DOMAINES_GMAIL = ("gmail.com", "googlemail.com")
_MICROSOFT = re.compile(r"5\.7\.139|SmtpClientAuthentication|basic authentication is disabled|5\.7\.3", re.IGNORECASE)


@dataclass(frozen=True)
class CompteImap:
    email: str
    mot_de_passe: str
    hote_imap: str
    port_imap: int
    dossier: str


def deviner_serveur(email: str, hote_imap: str) -> tuple[str, list[int]]:
    """Hôte SMTP probable et ports à essayer, dans l'ordre."""
    domaine = email.rsplit("@", 1)[-1].lower()
    if domaine in SERVEURS_CONNUS:
        hote, port = SERVEURS_CONNUS[domaine]
        return hote, [port]
    hote = hote_imap.lower()
    if hote.startswith("imap."):
        hote = "smtp." + hote[len("imap."):]
    return hote, [PORT_SSL, PORT_STARTTLS]


def raison_lisible(exc: Exception, hote: str) -> str:
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        texte = (exc.smtp_error or b"").decode("utf-8", "replace") if isinstance(exc.smtp_error, bytes) else str(exc.smtp_error)
        if _MICROSOFT.search(texte) or "office365" in hote or "outlook" in hote:
            return (
                "Microsoft 365 / Outlook refuse l'envoi par mot de passe (souvent désactivé par l'administrateur). "
                "Demandez à votre administrateur d'autoriser « SMTP AUTH » pour cette boîte."
            )
        return (
            "Le serveur d'envoi refuse l'adresse ou le mot de passe. Pour Gmail ou Yahoo, utilisez un mot de passe "
            "d'application ; sinon vérifiez le mot de passe auprès de votre hébergeur."
        )
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return "Le serveur d'envoi a refusé l'adresse du destinataire."
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return "Le serveur d'envoi refuse d'envoyer depuis cette adresse."
    if isinstance(exc, (socket.gaierror, ConnectionRefusedError, socket.timeout, TimeoutError, smtplib.SMTPConnectError, ssl.SSLError, OSError)):
        return f"Serveur d'envoi {hote} injoignable : vérifiez son adresse et son port dans Paramètres › Mails aux candidats."
    if isinstance(exc, smtplib.SMTPResponseException):
        return f"Le serveur d'envoi a refusé le message (code {exc.smtp_code})."
    return f"Envoi impossible : {exc}"


class SmtpExpediteur:
    def __init__(
        self,
        compte: Callable[[], CompteImap | None],
        reglage: Callable[[], dict | None],
        connexion_smtp: Callable[[str, int], Any] | None = None,
        connexion_imap: Callable[[str, int], Any] | None = None,
    ) -> None:
        """compte() : compte IMAP lié (ou None) ; reglage() : {"hote", "port"} saisis par l'entreprise, ou None."""
        self.compte = compte
        self.reglage = reglage
        self._smtp = connexion_smtp or _connexion_smtp
        self._imap = connexion_imap or _connexion_imap
        self._lock = threading.Lock()
        self._verifie: dict[str, tuple[bool, str | None, int | None]] = {}  # empreinte des réglages -> résultat

    # --- État ---------------------------------------------------------------------------------------------------

    def serveur(self) -> tuple[str, list[int]] | None:
        compte = self.compte()
        if compte is None:
            return None
        reglage = self.reglage() or {}
        if reglage.get("hote"):
            return reglage["hote"], [int(reglage.get("port") or PORT_SSL)]
        return deviner_serveur(compte.email, compte.hote_imap)

    def etat(self, retester: bool = False) -> dict:
        compte = self.compte()
        if compte is None:
            return {"autorise": False, "compte": None, "motif": "Mot de passe de la boîte introuvable : reliez de nouveau la boîte (page Boîte mail).", "reconnexion": True, "transport": "smtp"}
        hote, ports = self.serveur()
        cle = self._empreinte(compte, hote, ports)
        with self._lock:
            if retester:
                self._verifie.pop(cle, None)
            resultat = self._verifie.get(cle)
        if resultat is None:
            resultat = self._tester(compte, hote, ports)
            with self._lock:
                self._verifie[cle] = resultat
        ok, motif, port = resultat
        return {
            "autorise": ok,
            "compte": compte.email if ok else None,
            "motif": motif,
            "reconnexion": False,
            "transport": "smtp",
            "serveur": {"hote": hote, "port": port or ports[0], "auto": not (self.reglage() or {}).get("hote")},
        }

    # --- Envoi --------------------------------------------------------------------------------------------------

    def fil(self, message_id: str) -> FilOrigine | None:
        """Message-ID du mail de candidature, relu en IMAP (lecture seule) : « imap-<validité>-<uid> »."""
        compte = self.compte()
        m = re.fullmatch(r"imap-(\d+)-(\d+)", message_id or "")
        if compte is None or m is None:
            return None
        validite, uid = m.groups()
        try:
            imap = self._imap(compte.hote_imap, compte.port_imap)
            try:
                imap.login(compte.email, compte.mot_de_passe)
                imap.select(_nom_dossier(compte.dossier), readonly=True)
                _, donnees = imap.response("UIDVALIDITY")
                if donnees and donnees[0] and donnees[0].decode() != validite:
                    return None  # la boîte a été renumérotée : on ne retrouve plus le message
                typ, reponse = imap.uid("FETCH", uid, "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID REFERENCES)])")
            finally:
                _fermer_imap(imap)
        except Exception as exc:
            log.info("Fil IMAP introuvable pour %s : %s", message_id, exc)
            return None
        brut = b"".join(p[1] for p in reponse or [] if isinstance(p, tuple)) if typ == "OK" else b""
        entetes = _entetes(brut.decode("utf-8", "replace"))
        if not entetes.get("message-id"):
            return None
        return FilOrigine(thread_id="", message_id=entetes["message-id"], references=entetes.get("references", ""))

    def envoyer(self, mail: MailSortant) -> str:
        etat = self.etat()
        if not etat["autorise"]:
            raise EchecEnvoi(etat["motif"])
        compte = self.compte()
        hote, port = etat["serveur"]["hote"], etat["serveur"]["port"]
        message = construire_mime(mail, compte.email)
        try:
            smtp = self._smtp(hote, port)
            try:
                smtp.login(compte.email, compte.mot_de_passe)
                smtp.send_message(message)
            finally:
                _fermer_smtp(smtp)
        except Exception as exc:
            if isinstance(exc, smtplib.SMTPAuthenticationError):
                with self._lock:
                    self._verifie.clear()  # mot de passe changé entre-temps : on retestera
            raise EchecEnvoi(raison_lisible(exc, hote)) from exc
        self._copier_dans_envoyes(compte, message)
        return message["Message-ID"]

    # --- Interne ------------------------------------------------------------------------------------------------

    def _tester(self, compte: CompteImap, hote: str, ports: list[int]) -> tuple[bool, str | None, int | None]:
        derniere = None
        for port in ports:
            try:
                smtp = self._smtp(hote, port)
                try:
                    smtp.login(compte.email, compte.mot_de_passe)
                finally:
                    _fermer_smtp(smtp)
                log.info("Serveur d'envoi %s:%d accepté pour %s", hote, port, compte.email)
                return True, None, port
            except smtplib.SMTPAuthenticationError as exc:
                return False, raison_lisible(exc, hote), port  # le serveur répond : inutile d'essayer un autre port
            except Exception as exc:
                derniere = exc
        return False, raison_lisible(derniere, hote), None

    def _copier_dans_envoyes(self, compte: CompteImap, message) -> None:
        if compte.email.rsplit("@", 1)[-1].lower() in _DOMAINES_GMAIL:
            return  # Gmail range lui-même les messages envoyés par SMTP
        try:
            imap = self._imap(compte.hote_imap, compte.port_imap)
            try:
                imap.login(compte.email, compte.mot_de_passe)
                _, dossiers = imap.list()
                envoyes = next((_dossier_de(l) for l in dossiers or [] if b"\\Sent" in l), None)
                if envoyes:
                    imap.append(envoyes, "\\Seen", imaplib.Time2Internaldate(time.time()), message.as_bytes())
            finally:
                _fermer_imap(imap)
        except Exception as exc:  # une copie manquante n'empêche pas l'envoi
            log.info("Copie dans « Envoyés » impossible : %s", exc)

    @staticmethod
    def _empreinte(compte: CompteImap, hote: str, ports: list[int]) -> str:
        brut = f"{compte.email}|{hote}|{ports}|{compte.mot_de_passe}".encode()
        return hashlib.sha256(brut).hexdigest()


def _connexion_smtp(hote: str, port: int):
    contexte = ssl.create_default_context()
    if port == PORT_SSL:
        return smtplib.SMTP_SSL(hote, port, timeout=DELAI_S, context=contexte)
    smtp = smtplib.SMTP(hote, port, timeout=DELAI_S)
    smtp.starttls(context=contexte)
    return smtp


def _connexion_imap(hote: str, port: int):
    return imaplib.IMAP4_SSL(hote, port, ssl_context=ssl.create_default_context(), timeout=DELAI_S)


def _fermer_smtp(smtp) -> None:
    try:
        smtp.quit()
    except Exception:
        pass


def _fermer_imap(imap) -> None:
    try:
        imap.logout()
    except Exception:
        pass


def _nom_dossier(dossier: str) -> str:
    return f'"{dossier}"' if " " in dossier else dossier


def _dossier_de(ligne: bytes) -> str:
    """Nom du dossier dans une ligne de réponse LIST : (\\HasNoChildren \\Sent) "/" "Sent Items"."""
    texte = ligne.decode("utf-8", "replace")
    nom = texte.rsplit(" ", 1)[-1] if not texte.endswith('"') else '"' + texte.rstrip('"').rsplit('"', 1)[-1] + '"'
    return nom


def _entetes(brut: str) -> dict[str, str]:
    entetes: dict[str, str] = {}
    cle = None
    for ligne in brut.splitlines():
        if ligne[:1] in (" ", "\t") and cle:
            entetes[cle] += " " + ligne.strip()
        elif ":" in ligne:
            cle, valeur = ligne.split(":", 1)
            cle = cle.strip().lower()
            entetes[cle] = valeur.strip()
    return entetes
