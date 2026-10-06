"""Routes des candidatures traitées (session obligatoire) : liste, fiche, choix du poste, top par poste."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from .securite import session_requise

router = APIRouter(tags=["Candidatures"], dependencies=[Depends(session_requise)])


def _service(request: Request):
    return request.app.state.services.candidatures


class Assignation(BaseModel):
    poste_id: int | None = None


class Decision(BaseModel):
    decision: str
    note: str | None = None


@router.get("/candidatures")
def lister(
    request: Request,
    statut: str | None = None,
    lecture: str | None = None,
    poste_id: int | None = None,
    limite: int = 50,
    decalage: int = 0,
):
    return _service(request).lister(statut, lecture, poste_id, limite, decalage)


@router.get("/candidatures/{candidature_id}")
def consulter(candidature_id: int, request: Request):
    return _service(request).consulter(candidature_id)


@router.get("/candidatures/{candidature_id}/cv")
def contenu_cv(candidature_id: int, request: Request):
    """CV déchiffré, pour qu'Electron l'ouvre dans l'application par défaut du système."""
    nom, contenu = _service(request).contenu_cv(candidature_id)
    return Response(
        contenu,
        media_type="application/octet-stream",
        headers={"X-Injara-Nom-Fichier": quote(nom), "Cache-Control": "no-store"},
    )


@router.get("/candidatures/{candidature_id}/rapport")
def rapport(candidature_id: int, request: Request):
    """Toutes les données du rapport PDF du candidat (le PDF est produit par Electron)."""
    return request.app.state.services.rapport.donnees(candidature_id)


@router.put("/candidatures/{candidature_id}/poste")
def assigner(candidature_id: int, corps: Assignation, request: Request):
    return _service(request).assigner(candidature_id, corps.poste_id)


@router.put("/candidatures/{candidature_id}/decision")
def decider(candidature_id: int, corps: Decision, request: Request):
    return _service(request).decider(candidature_id, corps.decision, corps.note)


@router.post("/candidatures/{candidature_id}/automatique")
def rendre_automatique(candidature_id: int, request: Request):
    return _service(request).rendre_automatique(candidature_id)


@router.post("/candidatures/{candidature_id}/relire")
def relire(candidature_id: int, request: Request):
    return _service(request).relancer_lecture(candidature_id)


@router.get("/postes/{poste_id}/classement")
def classement(poste_id: int, request: Request, decision: str | None = None):
    return _service(request).top(poste_id, decision)


@router.get("/traitement/etat")
def etat(request: Request):
    return _service(request).etat()


@router.post("/traitement/relancer")
def relancer(request: Request):
    request.app.state.services.traitement.demander("demande du recruteur", tout_renoter=True)
    return _service(request).etat()
