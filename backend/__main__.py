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


def _detacher_stdin() -> int:
    """Déplace le tube stdin d'Electron sur un descripteur privé et met NUL à la place de stdin.

    Sous Windows, une lecture en attente sur le stdin du processus bloque la création de tout sous-processus
    (constaté : la sonde du moteur d'analyse, puis l'import de torch, restaient figés indéfiniment).
    """
    fd = os.dup(0)  # non héritable par les sous-processus
    nul = os.open(os.devnull, os.O_RDONLY)
    os.dup2(nul, 0)
    os.close(nul)
    if sys.platform == "win32":
        import ctypes
        import msvcrt

        ctypes.windll.kernel32.SetStdHandle(-10, msvcrt.get_osfhandle(0))  # STD_INPUT_HANDLE
    sys.stdin = open(0, closefd=False)  # noqa: SIM115
    return fd


def _surveiller_parent(fd: int, nettoyer=None) -> None:
    """Bloque jusqu'à la fermeture du tube d'Electron (arrêté ou planté), puis termine le processus."""
    try:
        while os.read(fd, 1024):
            pass
    except OSError:
        pass
    logging.getLogger("injara").info("Electron s'est arrêté : arrêt du backend.")
    if nettoyer is not None:
        nettoyer()  # le tunnel ne doit pas survivre à l'application : il laisserait le lien public ouvert
    os._exit(0)


def _port_demande() -> int:
    """Port fixe (INJARA_PORT) quand un tunnel nommé pointe dessus ; sinon 0 : un port libre choisi par le système."""
    brut = (os.getenv("INJARA_PORT") or "").strip()
    if not brut:
        return 0
    if not brut.isdigit() or not 0 < int(brut) < 65536:
        raise SystemExit(f"Erreur : INJARA_PORT invalide ({brut!r}).")
    return int(brut)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [backend] %(message)s", stream=sys.stderr)
    try:
        app = create_app(load_settings())
    except RuntimeError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 2

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((HOTE, _port_demande()))
    # Écouter avant d'annoncer le port : les requêtes arrivées pendant le démarrage d'uvicorn attendent
    # dans la file au lieu d'être refusées.
    sock.listen(128)
    port = sock.getsockname()[1]
    tunnel = app.state.services.tunnel
    tunnel.port = port

    if os.getenv("INJARA_WATCH_STDIN", "1") == "1":
        threading.Thread(target=_surveiller_parent, args=(_detacher_stdin(), tunnel.arreter), name="surveillance-parent", daemon=True).start()

    print(f"INJARA_PORT={port}", flush=True)
    config = uvicorn.Config(app, log_level="warning", access_log=False)
    try:
        uvicorn.Server(config).run(sockets=[sock])
    finally:
        tunnel.arreter()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
