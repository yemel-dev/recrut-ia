"""Routes protégées par la session : profil entreprise, postes, tableau de bord.

Les routes ne font que relayer vers services/ ; la validation métier y est faite.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from .securite import session_requise

router = APIRouter(dependencies=[Depends(session_requise)])


def _services(request: Request):
    return request.app.state.services


# --- Entreprise ---------------------------------------------------------------------


class ProfilEntreprise(BaseModel):
    nom: str | None = None
    secteur: str | None = None
    ville: str | None = None
    email_pro: str | None = None
    telephone: str | None = None
    description: str | None = None


@router.get("/entreprise", tags=["Entreprise"])
def consulter_entreprise(request: Request):
    return _services(request).entreprise.consulter()


@router.put("/entreprise", tags=["Entreprise"])
def enregistrer_entreprise(corps: ProfilEntreprise, request: Request):
    return _services(request).entreprise.enregistrer(corps.model_dump())


# --- Postes -------------------------------------------------------------------------


class PosteSaisi(BaseModel):
    intitule: str | None = None
    description: str | None = None
    competences_requises: list[str] | None = None
    experience_min_annees: int | None = None
    niveau_formation: str | None = None
    reference_interne: str | None = None
    departement: str | None = None
    lieu: str | None = None
    teletravail: str | None = None
    type_contrat: str | None = None
    duree: str | None = None
    date_limite: str | None = None
    competences_comportementales: list[str] | None = None
    langues: list[str] | None = None
    remuneration: str | None = None
    processus_selection: str | None = None
    documents_demandes: list[str] | None = None
    statut: str | None = None
    poids_competences: int | None = None
    poids_experience: int | None = None
    poids_formation: int | None = None
    poids_adequation: int | None = None


class ChangementStatut(BaseModel):
    statut: str


@router.get("/postes", tags=["Postes"])
def lister_postes(request: Request, statut: str | None = None):
    return _services(request).postes.lister(statut)


@router.post("/postes", status_code=201, tags=["Postes"])
def creer_poste(corps: PosteSaisi, request: Request):
    return _services(request).postes.creer(corps.model_dump())


@router.get("/postes/{poste_id}", tags=["Postes"])
def consulter_poste(poste_id: int, request: Request):
    return _services(request).postes.consulter(poste_id)


@router.put("/postes/{poste_id}", tags=["Postes"])
def modifier_poste(poste_id: int, corps: PosteSaisi, request: Request):
    services = _services(request)
    donnees = corps.model_dump()
    if donnees.get("statut") == "cloture" and services.postes.consulter(poste_id)["statut"] != "cloture":
        # Clôture par le formulaire : mêmes effets que par le statut (réponses négatives aux non retenus)
        services.postes.modifier(poste_id, {**donnees, "statut": services.postes.consulter(poste_id)["statut"]})
        return services.cloture_poste.cloturer(poste_id)
    return services.postes.modifier(poste_id, donnees)


@router.put("/postes/{poste_id}/statut", tags=["Postes"])
def changer_statut(poste_id: int, corps: ChangementStatut, request: Request):
    """« clôturé » : les non retenus passent à « écarté » et reçoivent la réponse négative (bilan dans « cloture »)."""
    services = _services(request)
    if corps.statut == "cloture":
        return services.cloture_poste.cloturer(poste_id)
    return services.postes.changer_statut(poste_id, corps.statut)


@router.delete("/postes/{poste_id}", status_code=204, tags=["Postes"])
def supprimer_poste(poste_id: int, request: Request):
    _services(request).postes.supprimer(poste_id)


# --- Tableau de bord ------------------------------------------------------------------


@router.get("/tableau-de-bord", tags=["Tableau de bord"])
def tableau_de_bord(request: Request):
    return _services(request).tableau_de_bord.synthese()
