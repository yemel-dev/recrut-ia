"""Signalisation WebRTC d'un entretien : relaie offre, réponse et candidats ICE entre le recruteur et le candidat.

La vidéo ne passe pas par ici : les deux navigateurs l'échangent directement (pair à pair). Ce service ne fait que
mettre en relation. Une « salle » par entretien, avec au plus un recruteur et un candidat.

Authentification (les WebSocket ne passent pas par le jeton de lancement) :
- candidat : le code du lien d'invitation ;
- recruteur : un ticket à usage unique et de courte durée, demandé avec sa session (`creer_ticket`).
"""
from __future__ import annotations

import json
import os
import secrets
import time
from dataclasses import dataclass
from typing import Any, Protocol

from .erreurs import Introuvable

DUREE_TICKET = 60.0  # secondes
TAILLE_MAX_MESSAGE = 64 * 1024
TYPES_RELAYES = ("offre", "reponse", "ice")


SERVEURS_ICE_PAR_DEFAUT = [{"urls": ["stun:stun.l.google.com:19302"]}]


def serveurs_ice() -> list[dict[str, Any]]:
    """Serveurs STUN/TURN donnés aux deux navigateurs. INJARA_ICE_SERVERS (JSON) ajoute un TURN pour les réseaux stricts."""
    try:
        serveurs = json.loads(os.getenv("INJARA_ICE_SERVERS") or "")
    except ValueError:
        return SERVEURS_ICE_PAR_DEFAUT
    return serveurs if isinstance(serveurs, list) and serveurs else SERVEURS_ICE_PAR_DEFAUT


class Canal(Protocol):
    async def send_text(self, data: str) -> None: ...
    async def close(self, code: int = 1000, reason: str | None = None) -> None: ...


@dataclass
class Salle:
    recruteur: Canal | None = None
    candidat: Canal | None = None

    def autre(self, role: str) -> Canal | None:
        return self.candidat if role == "recruteur" else self.recruteur


class SignalisationService:
    def __init__(self) -> None:
        self._salles: dict[str, Salle] = {}
        self._tickets: dict[str, tuple[str, float]] = {}  # ticket -> (code, expiration)

    def creer_ticket(self, code: str) -> str:
        self._purger_tickets()
        ticket = secrets.token_urlsafe(24)
        self._tickets[ticket] = (code, time.monotonic() + DUREE_TICKET)
        return ticket

    def consommer_ticket(self, ticket: str) -> str:
        """Code de l'entretien associé au ticket ; le ticket est détruit (usage unique)."""
        self._purger_tickets()
        code, _ = self._tickets.pop(ticket, (None, 0))
        if code is None:
            raise Introuvable("Ticket invalide ou expiré.")
        return code

    def _purger_tickets(self) -> None:
        maintenant = time.monotonic()
        for ticket in [t for t, (_, exp) in self._tickets.items() if exp < maintenant]:
            del self._tickets[ticket]

    async def rejoindre(self, code: str, role: str, canal: Canal) -> None:
        """Place le canal dans la salle ; un ancien canal du même rôle est remplacé (reconnexion)."""
        salle = self._salles.setdefault(code, Salle())
        ancien = getattr(salle, role)
        setattr(salle, role, canal)
        if ancien is not None:
            try:
                await ancien.close(code=4000, reason="Remplacé par une nouvelle connexion.")
            except Exception:  # noqa: BLE001  (l'ancien canal est peut-être déjà fermé)
                pass
        await self._annoncer(code)

    async def quitter(self, code: str, role: str, canal: Canal) -> None:
        salle = self._salles.get(code)
        if salle is None or getattr(salle, role) is not canal:
            return  # déjà remplacé par une reconnexion
        setattr(salle, role, None)
        if salle.recruteur is None and salle.candidat is None:
            del self._salles[code]
        else:
            await self._annoncer(code)

    async def relayer(self, code: str, role: str, texte: str) -> bool:
        """Transmet un message de signalisation à l'autre participant. Renvoie False si le message est refusé."""
        if len(texte) > TAILLE_MAX_MESSAGE:
            return False
        try:
            message = json.loads(texte)
        except ValueError:
            return False
        if not isinstance(message, dict) or message.get("type") not in TYPES_RELAYES:
            return False
        salle = self._salles.get(code)
        destinataire = salle.autre(role) if salle else None
        if destinataire is not None:
            await destinataire.send_text(json.dumps({"type": message["type"], "donnees": message.get("donnees")}))
        return True

    async def vers_candidat(self, code: str, message: dict[str, Any]) -> None:
        """Message du serveur au candidat (sous-titres), s'il est dans la salle."""
        salle = self._salles.get(code)
        if salle is not None and salle.candidat is not None:
            try:
                await salle.candidat.send_text(json.dumps(message))
            except Exception:  # noqa: BLE001  (canal mort : nettoyé à la déconnexion)
                pass

    async def fermer(self, code: str) -> None:
        """Ferme la salle (entretien terminé ou annulé)."""
        salle = self._salles.pop(code, None)
        if salle is None:
            return
        for canal in (salle.recruteur, salle.candidat):
            if canal is not None:
                try:
                    await canal.close(code=4001, reason="Entretien terminé.")
                except Exception:  # noqa: BLE001
                    pass

    async def _annoncer(self, code: str) -> None:
        """Dit à chacun qui est présent ; le recruteur relance alors une négociation WebRTC si les deux sont là."""
        salle = self._salles[code]
        etat: dict[str, Any] = {"type": "presence", "recruteur": salle.recruteur is not None, "candidat": salle.candidat is not None}
        for canal in (salle.recruteur, salle.candidat):
            if canal is not None:
                try:
                    await canal.send_text(json.dumps(etat))
                except Exception:  # noqa: BLE001  (canal mort : son nettoyage se fera à la déconnexion)
                    pass
