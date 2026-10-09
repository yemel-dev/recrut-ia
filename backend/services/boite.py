"""Connexion de la boîte de recrutement en une fois, et assistant de démarrage.

Une seule connexion sert à l'agent mail (lecture des candidatures) et aux mails aux candidats (envoi) :
- compte Google : une fenêtre Google accorde la lecture et l'envoi (services/expediteur_gmail.py) ;
- autre boîte : adresse et mot de passe, serveur trouvé d'après l'adresse (services/detection_boite.py) ; l'envoi
  passe par SMTP avec les mêmes identifiants et il est essayé tout de suite.
L'agent mail n'est pas modifié : on appelle ses méthodes de connexion habituelles.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from ..agent.accounts import ImapConfig
from ..agent.errors import GmailAuthRequired, ImapAuthError, ImapConnectionError
from ..database.repositories import EntrepriseRepository, ParametreRepository
from .agent_mail import AgentMailService
from .detection_boite import DetectionBoite
from .erreurs import Conflit, ErreurValidation
from .expediteur_gmail import GmailExpediteur
from .expediteur_smtp import SmtpExpediteur

log = logging.getLogger("injara.boite")

CLE_ACCUEIL = "accueil.termine"


class BoiteService:
    def __init__(
        self,
        agent_mail: AgentMailService,
        detection: DetectionBoite,
        gmail: GmailExpediteur,
        expediteur: Callable[[], Any],
        parametres: ParametreRepository,
        entreprise: EntrepriseRepository,
    ) -> None:
        """expediteur() : l'expéditeur des mails en service (démo, Gmail ou SMTP selon la boîte liée)."""
        self.agent_mail = agent_mail
        self.detection = detection
        self.gmail = gmail
        self.expediteur = expediteur
        self.parametres = parametres
        self.entreprise = entreprise

    # --- Connexion ----------------------------------------------------------------------------------------------

    def detecter(self, email: str) -> dict:
        return self.detection.detecter(email).dict()

    def connecter_google(self, email: str | None = None) -> dict:
        agent = self.agent_mail.agent()
        if self.agent_mail.reglages.mode != "fake":
            self.gmail.connecter(adresse_attendue=(email or "").strip() or None)
        try:
            agent.connect()  # le jeton vient d'être écrit : pas de seconde fenêtre
        except GmailAuthRequired as exc:
            raise Conflit(str(exc)) from exc
        return self.etat(retester=True)

    def connecter_mot_de_passe(self, email: str, mot_de_passe: str, hote: str | None = None) -> dict:
        if not mot_de_passe:
            raise ErreurValidation({"mot_de_passe": "Saisissez le mot de passe."})
        detection = self.detection.detecter(email)
        if detection.methode == "impossible":
            raise ErreurValidation({"email": detection.avertissement or "Cette adresse ne peut pas être connectée."})
        hote = (hote or "").strip() or detection.hote
        if not hote:
            raise ErreurValidation(
                {"hote": "Le serveur de cette boîte n'a pas été trouvé automatiquement. Indiquez-le ci-dessous : "
                         "votre hébergeur ou la personne qui gère vos mails peut vous le donner."}
            )
        try:
            self.agent_mail.agent().connect_imap(ImapConfig(detection.email, hote, detection.port, "INBOX"), mot_de_passe.strip())
        except ImapAuthError as exc:
            message = (
                "Code refusé. Collez le mot de passe d'application créé à l'étape précédente (pas le mot de passe habituel du compte)."
                if detection.mot_de_passe_application
                else "Mot de passe refusé. Vérifiez-le, puis réessayez."
            )
            if detection.avertissement:
                message += " " + detection.avertissement
            raise ErreurValidation({"mot_de_passe": message}) from exc
        except ImapConnectionError as exc:
            raise ErreurValidation(
                {"hote": f"Le serveur {hote} ne répond pas. Vérifiez votre connexion Internet, ou corrigez l'adresse du serveur."}
            ) from exc
        return self.etat(retester=True)

    def etat(self, retester: bool = False) -> dict:
        """Boîte liée, lecture et envoi : ce que l'assistant et la page Boîte mail affichent."""
        agent = self.agent_mail.agent()
        expediteur = self.expediteur()
        envoi = expediteur.etat(retester=True) if retester and isinstance(expediteur, SmtpExpediteur) else expediteur.etat()
        return {
            "connectee": agent.connected,
            "email": agent.account_email,
            "fournisseur": agent.provider,
            "envoi": envoi,
        }

    # --- Assistant de démarrage ---------------------------------------------------------------------------------

    def accueil(self) -> dict:
        entreprise = bool((self.entreprise.get() or {}).get("nom"))
        boite = self.agent_mail.agent().connected
        termine = self.parametres.get(CLE_ACCUEIL) == "1"
        return {"a_faire": not termine and not (entreprise and boite), "entreprise": entreprise, "boite": boite}

    def terminer_accueil(self) -> dict:
        self.parametres.set(CLE_ACCUEIL, "1")
        return self.accueil()
