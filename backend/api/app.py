"""Assemblage de l'application FastAPI."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ..config import MIN_TOKEN_LENGTH, Settings
from ..database.db import Database
from ..database.repositories import (
    CandidatureRepository,
    CompteRepository,
    EntrepriseRepository,
    ParametreRepository,
    PosteRepository,
    ScoreRepository,
)
from ..ia.ocr import MoteurOCR
from ..ia.semantique import NOM_MODELE, ModeleSemantique, dossier_modeles
from ..services.agent_mail import AgentMailService
from ..services.auth import AuthService
from ..services.candidatures import CandidaturesService
from ..services.entreprise import EntrepriseService
from ..services.postes import PostesService
from ..services.tableau_de_bord import TableauDeBordService
from ..services.traitement import TraitementService
from ..services.erreurs import Conflit, ErreurService, ErreurValidation, Introuvable, NonAutorise, SessionRequise
from . import routes_agent, routes_auth, routes_candidatures, routes_metier
from .securite import JetonDeLancementMiddleware


@dataclass
class Services:
    auth: AuthService
    entreprise: EntrepriseService
    postes: PostesService
    tableau_de_bord: TableauDeBordService
    agent_mail: AgentMailService
    traitement: TraitementService
    candidatures: CandidaturesService


def construire_services(db: Database, settings: Settings, modele: ModeleSemantique | None = None) -> Services:
    entreprise = EntrepriseService(EntrepriseRepository(db))
    postes = PostesService(PosteRepository(db))
    auth = AuthService(CompteRepository(db), settings.kdf)
    agent_mail = AgentMailService(settings.data_dir, settings.mode_agent, ParametreRepository(db))
    modeles = settings.dossier_modeles or dossier_modeles()
    modele = modele or ModeleSemantique(modeles / NOM_MODELE)
    traitement = TraitementService(
        CandidatureRepository(db), ScoreRepository(db), PosteRepository(db), agent_mail, modele,
        cle=auth.cle_session, ocr=MoteurOCR(),
    )
    candidatures = CandidaturesService(CandidatureRepository(db), ScoreRepository(db), PosteRepository(db), traitement)

    auth.a_la_connexion += [agent_mail.session_ouverte, traitement.demarrer]
    auth.a_la_deconnexion += [agent_mail.session_fermee, traitement.arreter]
    postes.a_la_modification.append(traitement.postes_modifies)
    return Services(
        auth=auth,
        entreprise=entreprise,
        postes=postes,
        tableau_de_bord=TableauDeBordService(entreprise, postes),
        agent_mail=agent_mail,
        traitement=traitement,
        candidatures=candidatures,
    )


def create_app(settings: Settings, modele: ModeleSemantique | None = None) -> FastAPI:
    if len(settings.token) < MIN_TOKEN_LENGTH:
        raise RuntimeError("INJARA_TOKEN absent ou trop court : le backend doit être lancé par l'application INJARA.")
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    db = Database(settings.database_url)

    app = FastAPI(title="INJARA", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.db = db
    app.state.services = construire_services(db, settings, modele)
    app.add_middleware(JetonDeLancementMiddleware, jeton=settings.token)
    _gestionnaires_erreurs(app)

    app.include_router(routes_auth.router)
    app.include_router(routes_metier.router)
    app.include_router(routes_candidatures.router)
    routes_agent.monter(app)
    return app


_STATUTS = {ErreurValidation: 422, NonAutorise: 401, SessionRequise: 401, Introuvable: 404, Conflit: 409}


def _gestionnaires_erreurs(app: FastAPI) -> None:
    @app.exception_handler(ErreurService)
    async def erreur_service(_request: Request, exc: ErreurService):
        corps: dict = {"detail": exc.message}
        if isinstance(exc, ErreurValidation):
            corps["champs"] = exc.champs
        if isinstance(exc, SessionRequise):
            corps["code"] = "session_requise"  # seul ce 401 signifie « session perdue »
        return JSONResponse(corps, status_code=_STATUTS.get(type(exc), 400))

    @app.exception_handler(RequestValidationError)
    async def erreur_format(_request: Request, exc: RequestValidationError):
        champs = {}
        for erreur in exc.errors():
            emplacement = [str(p) for p in erreur.get("loc", ()) if p not in ("body", "query", "path")]
            champ = emplacement[0] if emplacement else "requete"
            if erreur.get("type") == "missing":
                message = "Champ obligatoire."
            elif erreur.get("type") == "value_error":  # message rédigé par un validateur (ex. : agent mail)
                message = str(erreur.get("msg", "")).removeprefix("Value error, ") or "Valeur invalide."
            else:
                message = "Valeur invalide."
            champs.setdefault(champ, message)
        return JSONResponse({"detail": "Certains champs sont invalides.", "champs": champs}, status_code=422)
