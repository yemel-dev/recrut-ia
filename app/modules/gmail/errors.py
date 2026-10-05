"""Exceptions propres au Module 1 (Gmail)."""


class GmailModuleError(Exception):
    """Erreur de base du module Gmail."""


class GmailAuthRequired(GmailModuleError):
    """Le recruteur doit (re)autoriser l'accès Gmail (OAuth2)."""


class NotConnectedError(GmailModuleError):
    """Une opération a été demandée alors que Gmail n'est pas connecté."""


class ImapAuthError(GmailAuthRequired):
    """Identifiants IMAP refusés (souvent : mot de passe d'application requis)."""


class ImapConnectionError(GmailModuleError):
    """Serveur IMAP injoignable ou dossier introuvable."""
