"""Point d'entrée de l'exécutable autonome du backend (PyInstaller), lancé par l'application installée.

Avec l'argument de sonde, essaie seulement d'importer le moteur d'analyse (voir backend/ia/semantique.py).
"""
import sys

from backend.ia.semantique import ARGUMENT_SONDE

if __name__ == "__main__":
    if sys.argv[1:2] == [ARGUMENT_SONDE]:
        import sentence_transformers  # noqa: F401  (un échec sort avec un code non nul et la trace sur stderr)

        raise SystemExit(0)
    from backend.__main__ import main

    raise SystemExit(main())
