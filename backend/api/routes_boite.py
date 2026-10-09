"""Routes de la connexion de la boîte en une fois et de l'assistant de démarrage (session obligatoire)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from .securite import session_requise

router = APIRouter(tags=["Boîte de recrutement"], dependencies=[Depends(session_requise)])


def _boite(request: Request):
    return request.app.state.services.boite


class ConnexionGoogle(BaseModel):
    email: str | None = None


class ConnexionMotDePasse(BaseModel):
    email: str
    mot_de_passe: str
    hote: str | None = None  # seulement si le serveur n'a pas été trouvé


@router.get("/boite/detection")
def detection(email: str, request: Request):
    """D'après l'adresse : hébergeur, méthode (google, mot_de_passe, impossible) et étapes guidées."""
    return _boite(request).detecter(email)


@router.get("/boite")
def etat(request: Request):
    return _boite(request).etat()


@router.post("/boite/google")
def connecter_google(corps: ConnexionGoogle, request: Request):
    """Ouvre le navigateur sur la page Google (répond quand c'est fini) : lecture et envoi d'un seul accord."""
    return _boite(request).connecter_google(corps.email)


@router.post("/boite/mot-de-passe")
def connecter_mot_de_passe(corps: ConnexionMotDePasse, request: Request):
    return _boite(request).connecter_mot_de_passe(corps.email, corps.mot_de_passe, corps.hote)


@router.get("/accueil")
def accueil(request: Request):
    return _boite(request).accueil()


@router.put("/accueil/termine")
def terminer_accueil(request: Request):
    return _boite(request).terminer_accueil()
