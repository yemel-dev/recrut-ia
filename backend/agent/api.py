"""API locale du Module 1 — le "pont" vers le frontend Electron.

Le frontend n'a besoin que de ces routes HTTP (JSON). Swagger : /docs.
Intégration dans l'app principale : app.include_router(router)
"""
from __future__ import annotations

import threading

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from .accounts import ImapConfig, detect_imap
from .agent import GmailAgent, create_agent
from .client import FakeMailClient
from .errors import GmailAuthRequired, GmailModuleError, ImapAuthError, ImapConnectionError, NotConnectedError
from .diagnostics import run_audit
from .importer import MAX_ZIP_BYTES
from .schemas import PROFILES, ProfileInfo, SyncConfig, AgentEvent, CVMetadata, GmailStatus, IgnoredItem, ImportResult, PreviewResult, RecoverResult, RejectedFile, SyncResult

router = APIRouter(prefix="/gmail", tags=["Module 1 — Gmail"])

_agent: GmailAgent | None = None
_lock = threading.Lock()


def get_agent() -> GmailAgent:
    """Instance unique de l'agent (créée au premier appel)."""
    global _agent
    with _lock:
        if _agent is None:
            _agent = create_agent()
        return _agent


def set_agent(agent: GmailAgent | None) -> None:
    """Pour les tests, ou pour que l'app principale injecte sa propre instance."""
    global _agent
    _agent = agent


@router.get("/status", response_model=GmailStatus)
def status(agent: GmailAgent = Depends(get_agent)):
    return agent.status()


@router.post("/connect", response_model=GmailStatus)
def connect(agent: GmailAgent = Depends(get_agent)):
    """Gmail / Google Workspace : ouvre le navigateur pour l'autorisation OAuth2 (première fois seulement)."""
    try:
        agent.connect()
    except GmailAuthRequired as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return agent.status()


class ImapConnectBody(BaseModel):
    email: str
    password: str  # mot de passe d'application, jamais le mot de passe principal
    host: str | None = None  # facultatif si l'hébergeur est connu (Gmail, Yahoo...)
    port: int = 993
    folder: str = "INBOX"


@router.get("/imap/detect")
def imap_detect(email: str):
    """Aide le formulaire : pré-remplit le serveur IMAP d'après l'adresse saisie."""
    preset = detect_imap(email)
    if preset is None:
        return {"known": False, "host": None, "port": 993, "help": "Serveur inconnu : demandez l'adresse IMAP à votre hébergeur (ex. imap.mail.ovh.net)."}
    return {"known": True, "host": preset.host, "port": preset.port, "help": preset.help}


@router.post("/connect/imap", response_model=GmailStatus)
def connect_imap(body: ImapConnectBody, agent: GmailAgent = Depends(get_agent)):
    """Connexion IMAP : hébergeurs pro (OVH...) et adresses simples (Gmail perso, Yahoo...)."""
    if "@" not in body.email:
        raise HTTPException(status_code=422, detail="Adresse e-mail invalide")
    host, port = body.host, body.port
    if not host:
        preset = detect_imap(body.email)
        if preset is None:
            raise HTTPException(status_code=422, detail="Serveur IMAP inconnu : renseignez le champ 'host'")
        host, port = preset.host, preset.port
    try:
        agent.connect_imap(ImapConfig(body.email.strip(), host.strip(), port, body.folder), body.password)
    except ImapAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except ImapConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return agent.status()


@router.post("/disconnect", response_model=GmailStatus)
def disconnect(agent: GmailAgent = Depends(get_agent)):
    agent.disconnect()
    return agent.status()


@router.post("/sync", response_model=SyncResult)
def sync(agent: GmailAgent = Depends(get_agent)):
    """Vérifie la boîte mail maintenant et télécharge les nouveaux CV."""
    try:
        return agent.sync_once()
    except NotConnectedError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/watch/start", response_model=GmailStatus)
def watch_start(
    poll_minutes: float | None = Query(None, gt=0, description="Intervalle de vérification"),
    agent: GmailAgent = Depends(get_agent),
):
    try:
        agent.start_watching(poll_minutes)
    except NotConnectedError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return agent.status()


@router.post("/watch/stop", response_model=GmailStatus)
def watch_stop(agent: GmailAgent = Depends(get_agent)):
    agent.stop_watching()
    return agent.status()


@router.get("/cvs", response_model=list[CVMetadata])
def list_cvs(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0), agent: GmailAgent = Depends(get_agent)):
    return agent.ledger.list_cvs(limit, offset)


@router.post("/cvs/upload", response_model=ImportResult)
async def upload_cvs(files: list[UploadFile] = File(...), agent: GmailAgent = Depends(get_agent)):
    """Bouton « Importer des CV » : plusieurs fichiers PDF/DOCX et/ou des archives ZIP en une fois.

    Fonctionne même si aucune boîte mail n'est connectée.
    """
    payload: list[tuple[str, bytes]] = []
    too_big: list[RejectedFile] = []
    for upload in files:
        name = upload.filename or "cv"
        data = await upload.read(MAX_ZIP_BYTES + 1)
        if len(data) > MAX_ZIP_BYTES:
            too_big.append(RejectedFile(filename=name, reason="fichier trop volumineux (max 200 Mo)"))
        else:
            payload.append((name, data))
    result = await run_in_threadpool(agent.import_files, payload)
    result.rejected.extend(too_big)
    return result


@router.get("/config", response_model=SyncConfig)
def get_config(agent: GmailAgent = Depends(get_agent)):
    """Règle de récupération actuelle (période, nouveaux seulement, non lus)."""
    return agent.sync_config


@router.put("/config", response_model=SyncConfig)
def put_config(config: SyncConfig, agent: GmailAgent = Depends(get_agent)):
    """Change la règle. Exemples : {"mode":"new_only"} | {"mode":"last_days","days":14,"unread_only":true}
    | {"mode":"since_date","since_date":"2026-10-01"} | {"mode":"all"}"""
    return agent.update_config(config)


@router.get("/profiles", response_model=list[ProfileInfo])
def list_profiles():
    """Profils prédéfinis (Prudent, Nouveaux seulement, Tout importer) : le frontend n'a pas à les coder en dur."""
    return list(PROFILES.values())


@router.put("/config/profile/{name}", response_model=SyncConfig)
def apply_profile(name: str, agent: GmailAgent = Depends(get_agent)):
    try:
        return agent.apply_profile(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Profil inconnu : {name}")


@router.post("/preview", response_model=PreviewResult)
def preview(config: SyncConfig | None = None, agent: GmailAgent = Depends(get_agent)):
    """Aperçu AVANT import. Sans corps : évalue les réglages actuels. Avec un corps (même forme que /config) :
    évalue ces réglages sans les enregistrer. Ne télécharge ni n'enregistre rien."""
    try:
        return agent.preview(config)
    except NotConnectedError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/ignored", response_model=list[IgnoredItem])
def list_ignored(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0), agent: GmailAgent = Depends(get_agent)):
    """Onglet « Ignorés » : ce que les règles ont écarté, avec la raison."""
    return agent.ledger.list_ignored(limit, offset)


@router.post("/ignored/{ignored_id}/recover", response_model=RecoverResult)
def recover_ignored(ignored_id: int, agent: GmailAgent = Depends(get_agent)):
    """Bouton « Récupérer quand même »."""
    try:
        return agent.recover_ignored(ignored_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Élément introuvable dans la liste des ignorés")
    except NotConnectedError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except GmailModuleError as exc:
        raise HTTPException(status_code=410, detail=str(exc))


@router.get("/diagnostics")
def diagnostics(days: int = Query(7, ge=1, le=90), limit: int = Query(30, ge=1, le=100), agent: GmailAgent = Depends(get_agent)):
    """Audit : pour chaque email récent, dit si l'agent le récupère et pourquoi (sinon)."""
    try:
        return run_audit(agent, days, limit)
    except NotConnectedError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/events", response_model=list[AgentEvent])
def events(after_id: int = Query(0, ge=0, description="Dernier id reçu"), agent: GmailAgent = Depends(get_agent)):
    """Le frontend interroge cette route toutes les quelques secondes pour afficher
    les notifications ('3 nouveaux CV récupérés')."""
    return agent.events_since(after_id)


class SimulatedEmail(BaseModel):
    sender_name: str | None = None
    subject: str | None = None


@router.post("/dev/simulate-email")
def simulate_email(body: SimulatedEmail | None = None, agent: GmailAgent = Depends(get_agent)):
    """DEV UNIQUEMENT (mode fake) : fait arriver un faux email avec un CV."""
    if not isinstance(agent.client, FakeMailClient):
        raise HTTPException(status_code=409, detail="Disponible uniquement avec GMAIL_MODE=fake")
    body = body or SimulatedEmail()
    message = agent.client.add_random_message(body.sender_name, body.subject)
    return {"message_id": message.id, "sender": message.sender, "subject": message.subject}
