"""Routes publiques de l'entretien : page du candidat, consentement et signalisation WebRTC.

Elles répondent sans le jeton de lancement (le candidat arrive par le tunnel) : voir `securite.PREFIXE_PUBLIC`.
Le candidat s'identifie par le code de son lien. Rien d'autre de l'API n'est accessible de cette façon.
Les WebSocket échappent au middleware du jeton : chacune s'authentifie elle-même (code du lien ou ticket du recruteur).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..services.erreurs import Introuvable

DOSSIER_WEB = Path(__file__).resolve().parents[1] / "web" / "candidat"
EN_TETES = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",  # le code du lien est dans l'adresse de la page
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; media-src 'self' blob:; "
        "connect-src 'self' wss: ws:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
}

router = APIRouter(prefix="/public", tags=["Entretien (candidat)"])


class Consentement(BaseModel):
    accepte: bool
    consignes: bool = False  # le candidat s'engage à fermer les autres applications et fenêtres


class Signal(BaseModel):
    type: str
    duree_s: float | None = Field(default=None, ge=0, le=86400)
    raison: str | None = Field(default=None, max_length=40)


def _fichier(nom: str, type_: str) -> FileResponse:
    return FileResponse(DOSSIER_WEB / nom, media_type=type_, headers=EN_TETES)


@router.get("/entretien/{code}")
def page(code: str):
    return _fichier("index.html", "text/html; charset=utf-8")


@router.get("/candidat.js")
def script():
    return _fichier("candidat.js", "text/javascript; charset=utf-8")


@router.get("/candidat.css")
def style():
    return _fichier("candidat.css", "text/css; charset=utf-8")


# Polices et logo de la page : liste fermée (aucun chemin fourni par la requête n'atteint le disque).
POLICES = {"unbounded.woff2", "instrument-sans.woff2"}
MARQUE = {"symbole.webp", "logotype.webp"}


@router.get("/polices/{nom}")
def police(nom: str):
    if nom not in POLICES:
        raise Introuvable("Fichier introuvable.")
    return _fichier(f"polices/{nom}", "font/woff2")


@router.get("/marque/{nom}")
def marque(nom: str):
    if nom not in MARQUE:
        raise Introuvable("Fichier introuvable.")
    return _fichier(f"marque/{nom}", "image/webp")


@router.get("/api/{code}")
def presenter(code: str, request: Request, response: Response):
    response.headers.update(EN_TETES)
    return {**request.app.state.services.entretiens.presenter_au_candidat(code), "ice": request.app.state.services.reseau.serveurs_ice()}


@router.post("/api/{code}/consentement")
def consentement(code: str, corps: Consentement, request: Request, response: Response):
    response.headers.update(EN_TETES)
    return request.app.state.services.entretiens.consentement_candidat(code, corps.accepte, corps.consignes)


@router.post("/api/{code}/signal", status_code=204)
def signal(code: str, corps: Signal, request: Request, response: Response):
    response.headers.update(EN_TETES)
    details = corps.model_dump(exclude={"type"}, exclude_none=True)
    request.app.state.services.entretiens.signal_candidat(code, corps.type, details)


@router.websocket("/ws/candidat/{code}")
async def signalisation_candidat(ws: WebSocket, code: str):
    try:
        entretien = ws.app.state.services.entretiens.entretien_du_lien(code)
    except Introuvable:
        await ws.close(code=4404)
        return
    await _boucle(ws, entretien["code_invitation"], "candidat")


@router.websocket("/ws/recruteur")
async def signalisation_recruteur(ws: WebSocket):
    try:
        code = ws.app.state.services.signalisation.consommer_ticket(ws.query_params.get("ticket", ""))
    except Introuvable:
        await ws.close(code=4401)
        return
    await _boucle(ws, code, "recruteur")


async def _boucle(ws: WebSocket, code: str, role: str) -> None:
    signal = ws.app.state.services.signalisation
    await ws.accept()
    await signal.rejoindre(code, role, ws)
    try:
        while True:
            if not await signal.relayer(code, role, await ws.receive_text()):
                await ws.close(code=1008)  # message hors protocole
                return
    except WebSocketDisconnect:
        pass
    finally:
        await signal.quitter(code, role, ws)
