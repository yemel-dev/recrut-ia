"""Erreurs métier. L'API les traduit en codes HTTP ; les messages sont destinés à l'utilisateur."""
from __future__ import annotations


class ErreurService(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ErreurValidation(ErreurService):
    """Données invalides. `champs` associe chaque champ fautif à son message."""

    def __init__(self, champs: dict[str, str], message: str = "Certains champs sont invalides.") -> None:
        super().__init__(message)
        self.champs = champs


class NonAutorise(ErreurService):
    pass


class SessionRequise(NonAutorise):
    """Aucune session valide : l'interface doit revenir à l'écran de connexion.

    Distincte des autres 401 (ex. : identifiants de messagerie refusés), qui ne doivent pas déconnecter.
    """


class Introuvable(ErreurService):
    pass


class Conflit(ErreurService):
    pass


class Indisponible(ErreurService):
    """Une fonction dont dépend la demande n'est pas disponible sur ce poste (ex. : aucun tunnel installé)."""
