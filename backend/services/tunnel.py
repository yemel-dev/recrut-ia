"""Accès à distance : expose le backend local sur Internet par un tunnel pour que le candidat ouvre son lien.

Le recruteur l'active explicitement (rien n'est exposé avant) et il s'arrête à la déconnexion. Seules les routes
publiques de l'entretien (`/public/...`) répondent sans le jeton de lancement ; tout le reste de l'API reste refusé.

Outils pris en charge, détectés dans le PATH : cloudflared (tunnel rapide, sans compte), puis ngrok (compte requis).
INJARA_URL_PUBLIQUE force une adresse existante (nom de domaine, reverse proxy) : aucun tunnel n'est alors lancé.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time

from .erreurs import Indisponible

log = logging.getLogger("injara.tunnel")

DELAI_DEMARRAGE = 30.0
_MOTIF_CLOUDFLARED = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
_MOTIF_NGROK = re.compile(r'"url":\s*"(https://[^"]+)"')


class TunnelService:
    def __init__(self) -> None:
        self.port: int | None = None  # port local du backend, connu une fois la socket ouverte (backend/__main__.py)
        self._processus: subprocess.Popen | None = None
        self._url: str | None = None
        self._outil: str | None = None
        self._lock = threading.Lock()

    @property
    def url(self) -> str | None:
        fixe = (os.getenv("INJARA_URL_PUBLIQUE") or "").strip().rstrip("/")
        if fixe:
            return fixe
        if self._processus is not None and self._processus.poll() is not None:
            self._processus, self._url = None, None  # le tunnel s'est arrêté de lui-même
        return self._url

    def etat(self) -> dict[str, str | bool | None]:
        manuel = bool(os.getenv("INJARA_URL_PUBLIQUE"))
        return {
            "actif": self.url is not None,
            "url": self.url,
            "outil": "manuel" if manuel else self._outil,
            "disponible": manuel or self._commande(0) is not None,  # un outil de tunnel est installé
        }

    def demarrer(self) -> dict[str, str | bool | None]:
        with self._lock:
            if self.url:
                return self.etat()
            port = self.port
            commande = self._commande(port or 0)
            if commande is None or not port:
                raise Indisponible("Aucun outil de tunnel n'est installé (cloudflared ou ngrok). Installez-en un pour inviter à distance.")
            nom, args, motif = commande
            options = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
            processus = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", **options)
            url = self._attendre_url(processus, motif)
            if url is None:
                processus.kill()
                raise Indisponible("Le tunnel n'a pas pu démarrer (connexion Internet ou compte de l'outil à vérifier).")
            self._processus, self._url, self._outil = processus, url, nom
            log.info("Tunnel actif (%s).", nom)
            return self.etat()

    def arreter(self, *_args) -> None:
        with self._lock:
            processus, self._processus, self._url, self._outil = self._processus, None, None, None
        if processus is not None and processus.poll() is None:
            processus.terminate()
            try:
                processus.wait(timeout=5)
            except subprocess.TimeoutExpired:
                processus.kill()

    def _commande(self, port: int) -> tuple[str, list[str], re.Pattern] | None:
        adresse = f"http://127.0.0.1:{port}"
        if chemin := shutil.which("cloudflared"):
            return "cloudflared", [chemin, "tunnel", "--no-autoupdate", "--url", adresse], _MOTIF_CLOUDFLARED
        if chemin := shutil.which("ngrok"):
            return "ngrok", [chemin, "http", adresse, "--log", "stdout", "--log-format", "json"], _MOTIF_NGROK
        return None

    @staticmethod
    def _attendre_url(processus: subprocess.Popen, motif: re.Pattern) -> str | None:
        trouve: list[str] = []

        def lire() -> None:
            for ligne in processus.stdout:  # type: ignore[union-attr]
                if not trouve and (m := motif.search(ligne)):
                    trouve.append(m.group(1) if m.groups() else m.group(0))
                # on continue de lire : un tube plein bloquerait l'outil de tunnel

        threading.Thread(target=lire, name="lecture-tunnel", daemon=True).start()
        fin = time.monotonic() + DELAI_DEMARRAGE
        while time.monotonic() < fin and not trouve and processus.poll() is None:
            time.sleep(0.1)
        return trouve[0] if trouve else None
