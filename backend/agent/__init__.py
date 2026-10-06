"""Module 1 — Connexion Gmail & récupération des CV.

Usage depuis l'application principale :
    from backend.agent import create_agent
    agent = create_agent()
    agent.sync_once()

Pour exposer l'API au frontend :
    from backend.agent.api import router
    app.include_router(router)
"""
from .agent import GmailAgent, create_agent
from .errors import GmailAuthRequired, NotConnectedError
from .schemas import AgentEvent, CVMetadata, GmailStatus, SyncResult

__all__ = [
    "GmailAgent",
    "create_agent",
    "GmailAuthRequired",
    "NotConnectedError",
    "AgentEvent",
    "CVMetadata",
    "GmailStatus",
    "SyncResult",
]
