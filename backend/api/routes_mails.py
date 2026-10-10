"""Routes des mails aux candidats (session obligatoire) : réglages, envois, autorisation d'envoi."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ..services.erreurs import Conflit
from ..services.expediteur_smtp import SmtpExpediteur
from .securite import session_requise

router = APIRouter(tags=["Mails aux candidats"], dependencies=[Depends(session_requise)])


def _services(request: Request):
    return request.app.state.services


class Modele(BaseModel):
    objet: str = ""
    corps: str = ""


class Envoi(BaseModel):
    candidatures: list[int]
    echecs_seulement: bool = False


class EnvoiUn(BaseModel):
    forcer: bool = False


# --- Envois groupés (poste) ---------------------------------------------------------------------------------------


@router.get("/postes/{poste_id}/envois/{type_}")
def preparer_envoi(poste_id: int, type_: str, request: Request):
    return _services(request).envoi_mails.preparer(poste_id, type_)


@router.post("/postes/{poste_id}/envois/{type_}")
def envoyer_lot(poste_id: int, type_: str, corps: Envoi, request: Request):
    return _services(request).envoi_mails.envoyer_lot(poste_id, type_, corps.candidatures, corps.echecs_seulement)


@router.get("/postes/{poste_id}/cloture")
def apercu_cloture(poste_id: int, request: Request):
    """Avant de clôturer le poste : candidats qui recevront la réponse négative, exclus, blocages."""
    return _services(request).cloture_poste.apercu(poste_id)


# --- Un candidat (fiche) ------------------------------------------------------------------------------------------


@router.get("/candidatures/{candidature_id}/mails")
def etat_mails(candidature_id: int, request: Request):
    return _services(request).envoi_mails.etat_candidature(candidature_id)


@router.get("/candidatures/{candidature_id}/mails/{type_}")
def preparer_un(candidature_id: int, type_: str, request: Request, forcer: bool = False):
    return _services(request).envoi_mails.preparer_un(candidature_id, type_, forcer)


@router.post("/candidatures/{candidature_id}/mails/{type_}")
def envoyer_un(candidature_id: int, type_: str, corps: EnvoiUn, request: Request):
    return _services(request).envoi_mails.envoyer_un(candidature_id, type_, corps.forcer)


@router.get("/mails/autorisation")
def autorisation(request: Request):
    return _services(request).envoi_mails.expediteur().etat()


@router.post("/mails/autorisation")
def autoriser(request: Request):
    """Gmail : ouvre le navigateur sur la page d'autorisation Google (répond quand c'est fini).
    SMTP : reteste la connexion au serveur d'envoi."""
    expediteur = _services(request).envoi_mails.expediteur()
    if isinstance(expediteur, SmtpExpediteur):
        return expediteur.etat(retester=True)
    if not hasattr(expediteur, "autoriser"):
        raise Conflit("Mode démo : l'envoi est simulé, aucune autorisation n'est nécessaire.")
    return expediteur.autoriser()


class ServeurSmtp(BaseModel):
    hote: str | None = None  # vide : détection automatique
    port: int | None = None


@router.put("/mails/smtp")
def serveur_smtp(corps: ServeurSmtp, request: Request):
    services = _services(request)
    services.reglages_mails.definir_serveur_smtp(corps.hote, corps.port)
    expediteur = services.envoi_mails.expediteur()
    return expediteur.etat(retester=True) if isinstance(expediteur, SmtpExpediteur) else expediteur.etat()


@router.delete("/mails/autorisation")
def revoquer(request: Request):
    expediteur = _services(request).envoi_mails.expediteur()
    if not hasattr(expediteur, "revoquer"):
        raise Conflit("Mode démo : l'envoi est simulé.")
    return expediteur.revoquer()


# --- Réglages ---------------------------------------------------------------------------------------------------


@router.get("/parametres/mails")
def reglages(request: Request):
    return _services(request).reglages_mails.consulter()


@router.put("/parametres/mails/modeles/{type_}")
def enregistrer_modele(type_: str, corps: Modele, request: Request):
    return _services(request).reglages_mails.enregistrer_modele(type_, corps.objet, corps.corps)


@router.delete("/parametres/mails/modeles/{type_}")
def retablir_modele(type_: str, request: Request):
    return _services(request).reglages_mails.retablir_modele(type_)


@router.post("/parametres/mails/modeles/{type_}/apercu")
def apercu_modele(type_: str, corps: Modele, request: Request):
    profil = _services(request).entreprise.consulter()
    return _services(request).reglages_mails.apercu(type_, corps.objet, corps.corps, profil)
