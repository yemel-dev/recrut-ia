"""Intégration de l'agent mail (backend/agent) dans INJARA.

L'agent reste inchangé ; ce service :
- lui donne ses chemins dans le dossier de données d'INJARA (CV, registre, compte mail, identifiants Google) ;
- le crée à la première utilisation (sa restauration du compte peut passer par le réseau) ;
- mémorise le choix « surveillance automatique » et l'applique à chaque connexion ; la surveillance s'arrête
  à la déconnexion (les CV seront chiffrés avec la clé de session) ;
- enregistre le fichier d'identifiants Google (credentials.json) fourni par l'entreprise.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Callable

from ..agent import GmailAgent, create_agent
from ..agent.errors import NotConnectedError
from ..agent.settings import GmailSettings, load_settings
from ..database.repositories import ParametreRepository
from .erreurs import Conflit, ErreurValidation

log = logging.getLogger("injara.agent")

CLE_SURVEILLANCE = "agent_mail.surveillance"
TAILLE_MAX_IDENTIFIANTS = 64 * 1024


def parametres_agent(data_dir: Path, mode: str) -> GmailSettings:
    """Réglages de l'agent, avec tous ses fichiers rangés dans le dossier de données d'INJARA.

    Les réglages de réglage fin (GMAIL_POLL_MINUTES, GMAIL_LOOKBACK_DAYS…) restent lus par l'agent depuis
    l'environnement. GMAIL_CREDENTIALS_PATH peut pointer vers un credentials.json partagé en développement.
    """
    base = load_settings()
    secrets = data_dir / "secrets"
    credentials = Path(os.environ["GMAIL_CREDENTIALS_PATH"]) if os.getenv("GMAIL_CREDENTIALS_PATH") else secrets / "credentials.json"
    return dataclasses.replace(
        base,
        mode=mode,
        cv_dir=data_dir / "cvs",
        ledger_path=data_dir / "agent_mail.db",
        account_path=secrets / "compte_mail.json",
        token_path=secrets / "jeton_gmail.json",
        credentials_path=credentials,
    )


class AgentMailService:
    def __init__(
        self,
        data_dir: Path,
        mode: str,
        parametres: ParametreRepository,
        fabrique: Callable[[GmailSettings], GmailAgent] = create_agent,
    ) -> None:
        self.reglages = parametres_agent(data_dir, mode)
        self.parametres = parametres
        self._fabrique = fabrique
        self._agent: GmailAgent | None = None
        self._lock = threading.Lock()

    # --- Agent ----------------------------------------------------------------------

    def agent(self) -> GmailAgent:
        """L'instance unique de l'agent, créée au premier appel."""
        with self._lock:
            if self._agent is None:
                self._agent = self._fabrique(self.reglages)
            return self._agent

    def etat(self) -> dict[str, Any]:
        return {
            "mode": self.reglages.mode,
            "surveillance_souhaitee": self.surveillance_souhaitee(),
            "identifiants_google": self.reglages.credentials_path.exists(),
        }

    # --- Surveillance automatique ------------------------------------------------------

    def surveillance_souhaitee(self) -> bool:
        return self.parametres.get(CLE_SURVEILLANCE) == "1"

    def definir_surveillance(self, active: bool) -> dict[str, Any]:
        agent = self.agent()
        if active:
            try:
                agent.start_watching()
            except NotConnectedError as exc:
                raise Conflit("Liez d'abord une boîte mail pour activer la surveillance.") from exc
        else:
            agent.stop_watching()
        self.parametres.set(CLE_SURVEILLANCE, "1" if active else "0")
        return agent.status().model_dump(mode="json")

    def session_ouverte(self) -> None:
        """À la connexion : prépare l'agent en arrière-plan et reprend la surveillance si elle était demandée."""
        threading.Thread(target=self._reprendre, name="agent-mail-demarrage", daemon=True).start()

    def _reprendre(self) -> None:
        try:
            agent = self.agent()
            if agent.connected and self.surveillance_souhaitee():
                agent.start_watching()
        except Exception:
            log.exception("Reprise de l'agent mail impossible")

    def session_fermee(self) -> None:
        """À la déconnexion : la surveillance s'arrête (le choix reste mémorisé pour la prochaine connexion)."""
        with self._lock:
            agent = self._agent
        if agent is not None:
            agent.stop_watching()

    # --- Identifiants Google ------------------------------------------------------------

    def enregistrer_identifiants_google(self, contenu: str) -> dict[str, Any]:
        """Enregistre le credentials.json (« ID client OAuth », type « Application de bureau ») de l'entreprise."""
        erreur = {"fichier": "Ce fichier n'est pas un fichier d'identifiants Google valide (credentials.json)."}
        if len(contenu.encode("utf-8")) > TAILLE_MAX_IDENTIFIANTS:
            raise ErreurValidation(erreur)
        try:
            donnees = json.loads(contenu)
        except ValueError as exc:
            raise ErreurValidation(erreur) from exc
        client = donnees.get("installed") if isinstance(donnees, dict) else None
        if not isinstance(client, dict) or not client.get("client_id") or not client.get("client_secret"):
            if isinstance(donnees, dict) and "web" in donnees:
                erreur["fichier"] = "Ce fichier est prévu pour une application web : créez un ID client de type « Application de bureau »."
            raise ErreurValidation(erreur)
        chemin = self.reglages.credentials_path
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(json.dumps(donnees), encoding="utf-8")
        return self.etat()

    # --- Arrêt -------------------------------------------------------------------------

    def arreter(self) -> None:
        self.session_fermee()
