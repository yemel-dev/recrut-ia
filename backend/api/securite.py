"""Protection de l'API locale.

1. Jeton de lancement : généré par Electron à chaque démarrage, exigé sur TOUTES les requêtes (en-tête X-Injara-Token).
   Un autre programme de l'ordinateur ne peut donc pas interroger l'API, même s'il trouve le port.
2. Session : exigée sur toutes les routes sauf création de compte, connexion et récupération (en-tête X-Injara-Session).
"""
from __future__ import annotations

import hmac

from fastapi import Depends, Request
from starlette.types import ASGIApp, Receive, Scope, Send

from ..services.auth import AuthService, Session
from ..services.erreurs import NonAutorise

EN_TETE_JETON = "x-injara-token"
EN_TETE_SESSION = "X-Injara-Session"


class JetonDeLancementMiddleware:
    def __init__(self, app: ASGIApp, jeton: str) -> None:
        self.app = app
        self.jeton = jeton.encode("utf-8")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            recu = dict(scope["headers"]).get(EN_TETE_JETON.encode("ascii"), b"")
            if not hmac.compare_digest(recu, self.jeton):
                await _refuser(send)
                return
        await self.app(scope, receive, send)


async def _refuser(send: Send) -> None:
    corps = b'{"detail":"Acc\\u00e8s refus\\u00e9."}'
    await send({
        "type": "http.response.start",
        "status": 401,
        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(corps)).encode())],
    })
    await send({"type": "http.response.body", "body": corps})


def service_auth(request: Request) -> AuthService:
    return request.app.state.services.auth


def session_requise(request: Request, auth: AuthService = Depends(service_auth)) -> Session:
    session = auth.session_valide(request.headers.get(EN_TETE_SESSION))
    if session is None:
        raise NonAutorise("Vous devez être connecté.")
    return session
