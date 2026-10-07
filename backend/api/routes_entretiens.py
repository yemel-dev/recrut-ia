"""Routes des entretiens vidéo côté recruteur (session obligatoire)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from .securite import session_requise

router = APIRouter(tags=["Entretiens"], dependencies=[Depends(session_requise)])


def _service(request: Request):
    return request.app.state.services.entretiens


class Planification(BaseModel):
    date_entretien: datetime | None = None


class Statut(BaseModel):
    statut: str


class Consentement(BaseModel):
    accepte: bool


class Alerte(BaseModel):
    type: str
    details: dict[str, Any] | None = None


class Resultats(BaseModel):
    score_regard: float | None = None
    score_contenu: float | None = None
    score_confiance: float | None = None
    transcription: str | None = None
    resume: str | None = None


@router.post("/candidatures/{candidature_id}/entretiens", status_code=201)
def planifier(candidature_id: int, corps: Planification, request: Request):
    return _service(request).planifier(candidature_id, corps.date_entretien)


@router.get("/candidatures/{candidature_id}/entretiens")
def lister_candidature(candidature_id: int, request: Request):
    return _service(request).lister(candidature_id)


@router.get("/entretiens")
def lister(request: Request, statut: str | None = None):
    return _service(request).lister(statut=statut)


@router.get("/entretiens/{entretien_id}")
def consulter(entretien_id: int, request: Request):
    return _service(request).consulter(entretien_id)


@router.put("/entretiens/{entretien_id}/statut")
def changer_statut(entretien_id: int, corps: Statut, request: Request):
    return _service(request).changer_statut(entretien_id, corps.statut)


@router.put("/entretiens/{entretien_id}/consentement")
def consentement(entretien_id: int, corps: Consentement, request: Request):
    return _service(request).enregistrer_consentement(entretien_id, corps.accepte)


@router.post("/entretiens/{entretien_id}/alertes", status_code=201)
def alerte(entretien_id: int, corps: Alerte, request: Request):
    return _service(request).signaler_alerte(entretien_id, corps.type, corps.details)


@router.put("/entretiens/{entretien_id}/resultats")
def resultats(entretien_id: int, corps: Resultats, request: Request):
    return _service(request).enregistrer_resultats(entretien_id, **corps.model_dump())
