"""Routes de l'agent mail.

- /gmail/* : l'API de l'agent (backend/agent/api.py), montée telle quelle mais protégée par la session.
- /agent/* : ce qu'INJARA ajoute autour (surveillance mémorisée, identifiants Google).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Request
from pydantic import BaseModel

from ..agent import api as api_agent
from .securite import session_requise

router = APIRouter(prefix="/agent", tags=["Agent mail"], dependencies=[Depends(session_requise)])


def _service(request: Request):
    return request.app.state.services.agent_mail


class Surveillance(BaseModel):
    active: bool


class IdentifiantsGoogle(BaseModel):
    contenu: str


@router.get("/etat")
def etat(request: Request):
    return _service(request).etat()


@router.put("/surveillance")
def surveillance(corps: Surveillance, request: Request):
    return _service(request).definir_surveillance(corps.active)


@router.post("/identifiants-google")
def identifiants_google(corps: IdentifiantsGoogle, request: Request):
    return _service(request).enregistrer_identifiants_google(corps.contenu)


def monter(app: FastAPI) -> None:
    """Monte l'API de l'agent (session obligatoire) et lui fournit l'instance gérée par INJARA."""
    app.include_router(router)
    app.include_router(api_agent.router, dependencies=[Depends(session_requise)])
    app.dependency_overrides[api_agent.get_agent] = lambda: app.state.services.agent_mail.agent()
