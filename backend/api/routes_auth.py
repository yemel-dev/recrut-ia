"""Routes publiques (avec le jeton de lancement mais sans session) : état, création du compte, connexion, récupération."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ..services.auth import AuthService
from .securite import EN_TETE_SESSION, service_auth

router = APIRouter(prefix="/auth", tags=["Compte"])


class CreationCompte(BaseModel):
    email: str
    mot_de_passe: str


class Connexion(BaseModel):
    email: str
    mot_de_passe: str


class Recuperation(BaseModel):
    cle_de_recuperation: str
    nouveau_mot_de_passe: str


@router.get("/etat")
def etat(request: Request, auth: AuthService = Depends(service_auth)):
    session = auth.session_valide(request.headers.get(EN_TETE_SESSION))
    return {
        "compte_existe": auth.compte_existe(),
        "connecte": session is not None,
        "email": session.email if session else None,
    }


@router.post("/compte", status_code=201)
def creer_compte(corps: CreationCompte, auth: AuthService = Depends(service_auth)):
    return {"cle_de_recuperation": auth.creer_compte(corps.email, corps.mot_de_passe)}


@router.post("/connexion")
def connexion(corps: Connexion, auth: AuthService = Depends(service_auth)):
    resultat = auth.connecter(corps.email, corps.mot_de_passe)
    return {"jeton_session": resultat.jeton_session, "email": resultat.email}


@router.post("/deconnexion", status_code=204)
def deconnexion(auth: AuthService = Depends(service_auth)):
    auth.deconnecter()


@router.post("/recuperation")
def recuperation(corps: Recuperation, auth: AuthService = Depends(service_auth)):
    resultat = auth.reinitialiser(corps.cle_de_recuperation, corps.nouveau_mot_de_passe)
    return {"cle_de_recuperation": resultat.nouvelle_cle_de_recuperation}
