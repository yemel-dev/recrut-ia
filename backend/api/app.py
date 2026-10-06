"""Assemblage de l'application FastAPI."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ..config import MIN_TOKEN_LENGTH, Settings
from ..database.db import Database
from ..database.repositories import CompteRepository, EntrepriseRepository, PosteRepository
from ..services.auth import AuthService
from ..services.entreprise import EntrepriseService
from ..services.postes import PostesService
from ..services.tableau_de_bord import TableauDeBordService
from ..services.erreurs import Conflit, ErreurService, ErreurValidation, Introuvable, NonAutorise
from . import routes_auth, routes_metier
from .securite import JetonDeLancementMiddleware


@dataclass
class Services:
    auth: AuthService
    entreprise: EntrepriseService
    postes: PostesService
    tableau_de_bord: TableauDeBordService


def construire_services(db: Database, settings: Settings) -> Services:
    entreprise = EntrepriseService(EntrepriseRepository(db))
    postes = PostesService(PosteRepository(db))
    return Services(
        auth=AuthService(CompteRepository(db), settings.kdf),
        entreprise=entreprise,
        postes=postes,
        tableau_de_bord=TableauDeBordService(entreprise, postes),
    )


def create_app(settings: Settings) -> FastAPI:
    if len(settings.token) < MIN_TOKEN_LENGTH:
        raise RuntimeError("INJARA_TOKEN absent ou trop court : le backend doit être lancé par l'application INJARA.")
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    db = Database(settings.database_url)

    app = FastAPI(title="INJARA", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.db = db
    app.state.services = construire_services(db, settings)
    app.add_middleware(JetonDeLancementMiddleware, jeton=settings.token)
    _gestionnaires_erreurs(app)

    app.include_router(routes_auth.router)
    app.include_router(routes_metier.router)
    return app


_STATUTS = {ErreurValidation: 422, NonAutorise: 401, Introuvable: 404, Conflit: 409}


def _gestionnaires_erreurs(app: FastAPI) -> None:
    @app.exception_handler(ErreurService)
    async def erreur_service(_request: Request, exc: ErreurService):
        corps: dict = {"detail": exc.message}
        if isinstance(exc, ErreurValidation):
            corps["champs"] = exc.champs
        return JSONResponse(corps, status_code=_STATUTS.get(type(exc), 400))

    @app.exception_handler(RequestValidationError)
    async def erreur_format(_request: Request, exc: RequestValidationError):
        champs = {}
        for erreur in exc.errors():
            emplacement = [str(p) for p in erreur.get("loc", ()) if p not in ("body", "query", "path")]
            champ = emplacement[0] if emplacement else "requete"
            champs.setdefault(champ, "Champ obligatoire." if erreur.get("type") == "missing" else "Valeur invalide.")
        return JSONResponse({"detail": "Certains champs sont invalides.", "champs": champs}, status_code=422)
