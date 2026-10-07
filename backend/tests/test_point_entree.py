"""Point d'entrée : la surveillance d'Electron par stdin ne doit pas bloquer les sous-processus."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]

ENFANT = """
import subprocess, sys, threading
from backend.__main__ import _detacher_stdin, _surveiller_parent
threading.Thread(target=_surveiller_parent, args=(_detacher_stdin(),), daemon=True).start()
subprocess.run([sys.executable, "-c", "pass"], stdin=subprocess.DEVNULL, timeout=30, check=True)
print("sous-processus lancé", flush=True)
threading.Event().wait()  # attend la fermeture du tube
"""


def test_sous_processus_pendant_la_surveillance_puis_arret_a_la_fermeture():
    enfant = subprocess.Popen(
        [sys.executable, "-c", ENFANT],
        cwd=RACINE,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    garde = threading.Timer(60, enfant.kill)  # si le sous-processus se fige, le test échoue au lieu de bloquer
    garde.start()
    try:
        # Avant la correction, cette ligne n'arrivait jamais sous Windows : le sous-processus restait figé.
        assert enfant.stdout.readline().strip() == "sous-processus lancé"
        enfant.stdin.close()  # ce que fait Electron en quittant
        assert enfant.wait(timeout=15) == 0
    finally:
        garde.cancel()
        if enfant.poll() is None:
            enfant.kill()


def test_nettoyage_a_la_fermeture_du_tube(tmp_path):
    """Si Electron s'arrête, le tunnel public doit être coupé avant la sortie : le lien ne doit pas rester ouvert."""
    marque = tmp_path / "nettoye"
    code = (
        "import threading\n"
        "from pathlib import Path\n"
        "from backend.__main__ import _detacher_stdin, _surveiller_parent\n"
        f"threading.Thread(target=_surveiller_parent, args=(_detacher_stdin(), lambda: Path({str(marque)!r}).write_text('ok')), daemon=True).start()\n"
        "threading.Event().wait()\n"
    )
    enfant = subprocess.Popen([sys.executable, "-c", code], cwd=RACINE, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        enfant.stdin.close()
        assert enfant.wait(timeout=30) == 0
    finally:
        enfant.kill()
    assert marque.read_text() == "ok"
