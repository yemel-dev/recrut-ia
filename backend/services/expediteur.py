"""Transport des mails aux candidats : l'interface commune, le message MIME, et le faux expéditeur.

Le service d'envoi (envoi_mails.py) ne connaît que cette interface. Deux implémentations :
- FauxExpediteur : mode démo et tests, n'envoie rien, garde les messages en mémoire ;
- GmailExpediteur (expediteur_gmail.py) : API Gmail, avec une autorisation d'envoi séparée de celle de la lecture.
Rien ici ne touche à la récupération des candidatures (agent mail).
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Protocol


class EchecEnvoi(Exception):
    """Le mail n'est pas parti. `raison` est destinée au recruteur."""

    def __init__(self, raison: str) -> None:
        super().__init__(raison)
        self.raison = raison


@dataclass(frozen=True)
class FilOrigine:
    """Le mail de candidature auquel on répond (pour rester dans le même fil)."""

    thread_id: str
    message_id: str  # en-tête Message-ID du mail d'origine
    references: str = ""


@dataclass(frozen=True)
class MailSortant:
    destinataire: str
    objet: str
    corps: str
    fil: FilOrigine | None = None
    html: str | None = None  # version mise en forme (services/mail_html.py), envoyée avec le texte


class Expediteur(Protocol):
    def etat(self) -> dict:
        """{"autorise": bool, "compte": str | None, "motif": str | None, "reconnexion": bool}"""

    def fil(self, message_id: str) -> FilOrigine | None:
        """Fil du mail de candidature (identifiant Gmail du message), ou None s'il est introuvable."""

    def envoyer(self, mail: MailSortant) -> str:
        """Envoie le mail et renvoie son identifiant ; lève EchecEnvoi en cas d'échec."""


def construire_mime(mail: MailSortant, expediteur: str | None = None) -> EmailMessage:
    """Message en UTF-8 : texte, plus la version mise en forme quand elle existe (multipart/alternative) ;
    en réponse dans le fil, avec In-Reply-To et References."""
    message = EmailMessage()
    message["To"] = mail.destinataire
    if expediteur:
        message["From"] = expediteur
    message["Subject"] = mail.objet
    message["Message-ID"] = make_msgid(domain="injara.local")
    if mail.fil:
        message["In-Reply-To"] = mail.fil.message_id
        message["References"] = f"{mail.fil.references} {mail.fil.message_id}".strip()
    message.set_content(mail.corps, charset="utf-8")
    if mail.html:
        message.add_alternative(mail.html, subtype="html", charset="utf-8")
    return message


@dataclass
class ExpediteurIndisponible:
    """Aucun moyen d'envoyer (compte non lié, IMAP…) : l'état explique pourquoi."""

    motif: str
    reconnexion: bool = False

    def etat(self) -> dict:
        return {"autorise": False, "compte": None, "motif": self.motif, "reconnexion": self.reconnexion}

    def fil(self, message_id: str) -> FilOrigine | None:
        return None

    def envoyer(self, mail: MailSortant) -> str:
        raise EchecEnvoi(self.motif)


@dataclass
class FauxExpediteur:
    """N'envoie rien : garde les mails en mémoire (mode démo, tests). `echecs` : adresses qui échouent."""

    compte: str = "recrutement@demo.injara"
    autorise: bool = True
    echecs: set[str] = field(default_factory=set)
    envoyes: list[MailSortant] = field(default_factory=list)
    fils: dict[str, FilOrigine] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def etat(self) -> dict:
        if not self.autorise:
            return {"autorise": False, "compte": None, "motif": "L'envoi de mails n'est pas autorisé.", "reconnexion": False}
        return {"autorise": True, "compte": self.compte, "motif": None, "reconnexion": False, "simule": True}

    def fil(self, message_id: str) -> FilOrigine | None:
        return self.fils.get(message_id) or FilOrigine(thread_id=f"fil-{message_id}", message_id=f"<{message_id}@demo.injara>")

    def envoyer(self, mail: MailSortant) -> str:
        if mail.destinataire in self.echecs:
            raise EchecEnvoi(f"Adresse refusée par le serveur : {mail.destinataire}")
        construire_mime(mail, self.compte)  # vérifie que le message se construit
        with self._lock:
            self.envoyes.append(mail)
            return f"faux-{len(self.envoyes)}"
