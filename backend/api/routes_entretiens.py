"""Routes des entretiens vidéo côté recruteur (session obligatoire)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..services.erreurs import Indisponible
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
async def changer_statut(entretien_id: int, corps: Statut, request: Request):
    resultat = await run_in_threadpool(_service(request).changer_statut, entretien_id, corps.statut)
    if resultat["statut"] == "termine":
        await run_in_threadpool(request.app.state.services.regard.cloturer, entretien_id)
        resultat = _service(request).consulter(entretien_id)  # avec le score de regard
    if resultat["statut"] in ("termine", "annule"):  # la salle de visio se ferme avec l'entretien
        await request.app.state.services.signalisation.fermer(resultat["code_invitation"])
    return resultat


@router.put("/entretiens/{entretien_id}/consentement")
def consentement(entretien_id: int, corps: Consentement, request: Request):
    return _service(request).enregistrer_consentement(entretien_id, corps.accepte)


@router.post("/entretiens/{entretien_id}/alertes", status_code=201)
def alerte(entretien_id: int, corps: Alerte, request: Request):
    return _service(request).signaler_alerte(entretien_id, corps.type, corps.details)


@router.put("/entretiens/{entretien_id}/resultats")
def resultats(entretien_id: int, corps: Resultats, request: Request):
    return _service(request).enregistrer_resultats(entretien_id, **corps.model_dump())


# --- Accès à distance, lien du candidat, salle de visio ---------------------------------------------------


@router.get("/tunnel")
def etat_tunnel(request: Request):
    return request.app.state.services.tunnel.etat()


@router.post("/tunnel")
def demarrer_tunnel(request: Request):
    return request.app.state.services.tunnel.demarrer()


@router.delete("/tunnel")
def arreter_tunnel(request: Request):
    tunnel = request.app.state.services.tunnel
    tunnel.arreter()
    return tunnel.etat()


@router.get("/entretiens/{entretien_id}/lien")
def lien(entretien_id: int, request: Request):
    entretien = _service(request).pour_invitation(entretien_id)
    url = request.app.state.services.tunnel.url
    if url is None:
        raise Indisponible("L'accès à distance n'est pas activé : activez-le pour obtenir le lien du candidat.")
    return {"lien": f"{url}/public/entretien/{entretien['code_invitation']}", "expire_le": entretien["expire_le"]}


@router.post("/entretiens/{entretien_id}/salle")
def salle(entretien_id: int, request: Request):
    """Ticket à usage unique pour que l'interface du recruteur ouvre sa connexion de signalisation."""
    entretien = _service(request).pour_invitation(entretien_id)
    return {"ticket": request.app.state.services.signalisation.creer_ticket(entretien["code_invitation"]), "ice": request.app.state.services.reseau.serveurs_ice()}


# --- Réseau de la visio : serveur TURN ----------------------------------------------------------------------


class Turn(BaseModel):
    urls: list[str]
    username: str
    credential: str


@router.get("/reseau")
def etat_reseau(request: Request):
    return request.app.state.services.reseau.etat()


@router.put("/reseau/turn")
def configurer_turn(corps: Turn, request: Request):
    return request.app.state.services.reseau.configurer(corps.urls, corps.username, corps.credential)


@router.delete("/reseau/turn")
def supprimer_turn(request: Request):
    return request.app.state.services.reseau.supprimer()


@router.get("/reseau/test")
def serveurs_a_tester(request: Request):
    """Les serveurs avec leurs identifiants, pour que l'interface vérifie que le TURN relaie bien (candidat « relay »)."""
    return {"ice": request.app.state.services.reseau.pour_test()}


# --- Analyse du regard et de la tête -----------------------------------------------------------------------


@router.get("/regard")
def etat_regard(request: Request):
    return {"disponible": request.app.state.services.regard.disponible()}


@router.put("/entretiens/{entretien_id}/regard")
async def analyser_regard(entretien_id: int, request: Request):
    """Une image (JPEG) du candidat ; renvoie son état du moment et les événements relevés."""
    image = await request.body()
    return await run_in_threadpool(request.app.state.services.regard.analyser_image, entretien_id, image)


# --- Enregistrement (chiffré, après consentement du candidat) ---------------------------------------------


@router.put("/entretiens/{entretien_id}/enregistrement", status_code=204)
async def ajouter_enregistrement(entretien_id: int, request: Request):
    """Un morceau de l'enregistrement, en octets bruts, à la suite des précédents."""
    donnees = await request.body()
    await run_in_threadpool(_service(request).ajouter_enregistrement, entretien_id, donnees)


@router.get("/entretiens/{entretien_id}/enregistrement")
def lire_enregistrement(entretien_id: int, request: Request):
    morceaux = _service(request).lire_enregistrement(entretien_id)
    return StreamingResponse(morceaux, media_type="application/octet-stream")
