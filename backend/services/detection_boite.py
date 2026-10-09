"""Détection de la boîte mail à partir de la seule adresse : l'utilisateur n'a rien de technique à saisir.

À partir de l'adresse, on trouve qui héberge la boîte et comment s'y connecter :
- adresses grand public connues (Gmail, Yahoo, Outlook…) : réglages connus d'avance ;
- domaine de l'entreprise : on lit ses serveurs de messagerie (enregistrements MX) pour reconnaître l'hébergeur
  (Google Workspace, Microsoft 365, OVHcloud…) ; sinon on essaie les serveurs habituels (imap.domaine, mail.domaine).
La méthode proposée est « google » (fenêtre de connexion Google) ou « mot_de_passe » (mot de passe de la boîte, ou
mot de passe d'application avec des étapes guidées), ou « impossible » avec une explication simple.
"""
from __future__ import annotations

import logging
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Callable

from .erreurs import ErreurValidation

log = logging.getLogger("injara.boite")

DELAI_S = 4
PORT_IMAP = 993


@dataclass
class Detection:
    email: str
    fournisseur: str  # nom affiché : « Gmail », « Google Workspace », « OVHcloud », « votre hébergeur »…
    methode: str  # google | mot_de_passe | impossible
    hote: str | None = None  # serveur de lecture (IMAP) ; None : à demander à l'utilisateur
    port: int = PORT_IMAP
    mot_de_passe_application: bool = False  # il faut créer un mot de passe d'application (étapes guidées)
    etapes: list[str] = field(default_factory=list)
    lien: str | None = None  # page à ouvrir pour créer le mot de passe d'application
    avertissement: str | None = None
    google_possible: bool = False  # compte Google : la connexion avec Google pourrait remplacer le mot de passe

    def dict(self) -> dict:
        return asdict(self)


_ETAPES_GOOGLE = [
    "Ouvrez la page « Mots de passe des applications » de votre compte Google avec le bouton ci-dessous.",
    "Connectez-vous si Google le demande. Si la page indique que l'option n'est pas disponible, activez d'abord la "
    "« Validation en deux étapes » dans la sécurité du compte, puis revenez sur cette page.",
    "Donnez un nom, par exemple « INJARA », puis cliquez sur « Créer ».",
    "Copiez le code de 16 lettres affiché et collez-le ci-dessous.",
]
_ETAPES_YAHOO = [
    "Ouvrez la page de sécurité de votre compte Yahoo avec le bouton ci-dessous.",
    "Cliquez sur « Générer un mot de passe d'application » (ou « Gérer les mots de passe d'application »).",
    "Donnez un nom, par exemple « INJARA », puis cliquez sur « Générer ».",
    "Copiez le mot de passe affiché et collez-le ci-dessous.",
]
LIEN_GOOGLE = "https://myaccount.google.com/apppasswords"
LIEN_YAHOO = "https://login.yahoo.com/account/security"

_DOMAINES_GMAIL = {"gmail.com", "googlemail.com"}
_DOMAINES_YAHOO = {"yahoo.com", "yahoo.fr", "ymail.com", "rocketmail.com"}
_DOMAINES_MICROSOFT = {"outlook.com", "outlook.fr", "hotmail.com", "hotmail.fr", "live.com", "live.fr", "msn.com"}

# Hébergeur reconnu à ses serveurs MX : (fragment du nom du serveur MX, nom affiché, serveur IMAP)
_HEBERGEURS_MX: list[tuple[str, str, str]] = [
    ("google.com", "Google Workspace", "imap.gmail.com"),
    ("googlemail.com", "Google Workspace", "imap.gmail.com"),
    ("protection.outlook.com", "Microsoft 365", "outlook.office365.com"),
    ("ovh.net", "OVHcloud", "ssl0.ovh.net"),
    ("zoho.eu", "Zoho Mail", "imap.zoho.eu"),
    ("zoho.com", "Zoho Mail", "imap.zoho.com"),
    ("hostinger.com", "Hostinger", "imap.hostinger.com"),
    ("gandi.net", "Gandi", "mail.gandi.net"),
    ("privateemail.com", "Namecheap", "mail.privateemail.com"),
    ("yandex", "Yandex", "imap.yandex.com"),
]

_AVERTISSEMENT_MICROSOFT = (
    "Microsoft 365 bloque souvent la connexion par mot de passe depuis d'autres applications. Si elle est refusée, "
    "demandez à la personne qui gère vos mails d'autoriser IMAP et l'envoi SMTP pour cette boîte."
)


def _serveurs_mx(domaine: str) -> list[str]:
    try:
        import dns.resolver
    except ImportError:
        log.info("dnspython absent : pas de recherche des serveurs de messagerie")
        return []
    resolveur = dns.resolver.Resolver()
    resolveur.lifetime = DELAI_S
    try:
        reponses = sorted(resolveur.resolve(domaine, "MX"), key=lambda r: r.preference)
    except Exception as exc:  # domaine inexistant, pas de réseau…
        log.info("Serveurs MX de %s introuvables : %s", domaine, exc)
        return []
    return [str(r.exchange).rstrip(".").lower() for r in reponses]


def _repond(hote: str, port: int = PORT_IMAP) -> bool:
    try:
        with socket.create_connection((hote, port), timeout=DELAI_S):
            return True
    except OSError:
        return False


class DetectionBoite:
    def __init__(
        self,
        google_disponible: Callable[[], bool],
        serveurs_mx: Callable[[str], list[str]] = _serveurs_mx,
        repond: Callable[[str], bool] = _repond,
    ) -> None:
        """google_disponible() : la connexion avec Google est configurée (identifiants de l'application présents)."""
        self.google_disponible = google_disponible
        self._mx = serveurs_mx
        self._repond = repond
        self._cache: dict[str, tuple[str, str | None]] = {}  # domaine -> (fournisseur, serveur IMAP)
        self._lock = threading.Lock()

    def detecter(self, email: str) -> Detection:
        email = (email or "").strip()
        local, _, domaine = email.rpartition("@")
        domaine = domaine.lower()
        if not local or "." not in domaine or " " in email:
            raise ErreurValidation({"email": "Adresse e-mail invalide."})

        if domaine in _DOMAINES_GMAIL:
            return self._google(email, "Gmail", "imap.gmail.com")
        if domaine in _DOMAINES_YAHOO:
            return Detection(
                email, "Yahoo", "mot_de_passe", "imap.mail.yahoo.com", mot_de_passe_application=True,
                etapes=_ETAPES_YAHOO, lien=LIEN_YAHOO,
            )
        if domaine in _DOMAINES_MICROSOFT:
            return Detection(
                email, "Outlook", "impossible",
                avertissement=(
                    "Les adresses Outlook et Hotmail n'acceptent plus la connexion depuis d'autres applications. "
                    "Utilisez l'adresse de votre entreprise, ou une adresse Gmail ou Yahoo dédiée au recrutement."
                ),
            )

        fournisseur, hote = self._hebergeur(domaine)
        if hote == "imap.gmail.com":
            return self._google(email, fournisseur, hote)
        detection = Detection(email, fournisseur, "mot_de_passe", hote)
        if fournisseur == "Microsoft 365":
            detection.avertissement = _AVERTISSEMENT_MICROSOFT
        return detection

    # --- Interne ------------------------------------------------------------------------------------------------

    def _google(self, email: str, fournisseur: str, hote: str) -> Detection:
        if self.google_disponible():
            return Detection(email, fournisseur, "google", hote, google_possible=True)
        return Detection(
            email, fournisseur, "mot_de_passe", hote, mot_de_passe_application=True,
            etapes=_ETAPES_GOOGLE, lien=LIEN_GOOGLE,
        )

    def _hebergeur(self, domaine: str) -> tuple[str, str | None]:
        with self._lock:
            if domaine in self._cache:
                return self._cache[domaine]
        resultat = self._chercher(domaine)
        if resultat[1]:  # un échec (réseau coupé…) n'est pas mémorisé
            with self._lock:
                self._cache[domaine] = resultat
        return resultat

    def _chercher(self, domaine: str) -> tuple[str, str | None]:
        mx = self._mx(domaine)
        for serveur in mx:
            for fragment, nom, hote in _HEBERGEURS_MX:
                if fragment in serveur:
                    return nom, hote
        # Hébergeur inconnu : serveurs habituels, puis le serveur MX lui-même (petits hébergeurs, serveur maison)
        candidats = list(dict.fromkeys([f"imap.{domaine}", f"mail.{domaine}", *mx[:1]]))
        with ThreadPoolExecutor(max_workers=len(candidats)) as groupe:
            reponses = list(groupe.map(self._repond, candidats))
        for hote, ok in zip(candidats, reponses):
            if ok:
                return "votre hébergeur", hote
        return "votre hébergeur", None
