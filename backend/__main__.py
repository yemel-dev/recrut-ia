"""Point d'entrée lancé par Electron : python -m backend

- Écoute uniquement sur 127.0.0.1, sur un port libre choisi par le système.
- Annonce ce port sur la sortie standard (ligne « INJARA_PORT=12345 ») pour qu'Electron le lise.
- S'arrête quand Electron ferme l'entrée standard : si Electron plante, le backend ne reste pas orphelin.
"""
from __future__ import annotations

import logging
import os
import socket
import sys
import threading

import uvicorn

from .api.app import create_app
from .config import load_settings

HOTE = "127.0.0.1"


def _surveiller_parent() -> None:
    """Bloque jusqu'à la fermeture de stdin (Electron arrêté ou planté), puis termine le processus."""
    try:
        while sys.stdin.buffer.read(1024):
            pass
    except (OSError, ValueError):
        pass
    logging.getLogger("injara").info("Electron s'est arrêté : arrêt du backend.")
    os._exit(0)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [backend] %(message)s", stream=sys.stderr)
    try:
        app = create_app(load_settings())
    except RuntimeError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 2

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((HOTE, 0))
    port = sock.getsockname()[1]

    if os.getenv("INJARA_WATCH_STDIN", "1") == "1":
        threading.Thread(target=_surveiller_parent, name="surveillance-parent", daemon=True).start()

    print(f"INJARA_PORT={port}", flush=True)
    config = uvicorn.Config(app, log_level="warning", access_log=False)
    uvicorn.Server(config).run(sockets=[sock])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
