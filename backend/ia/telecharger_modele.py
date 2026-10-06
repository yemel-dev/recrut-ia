"""Télécharge une fois le modèle Sentence-BERT dans le dossier des modèles (accès Internet requis).

    python -m backend.ia.telecharger_modele

Ensuite, INJARA le charge depuis le disque, hors ligne. Sans ce modèle, le critère « adéquation » est ignoré.
"""
from __future__ import annotations

import sys

from .semantique import DEPOT_MODELE, NOM_MODELE, dossier_modeles


def main() -> int:
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("Installez d'abord les bibliothèques d'IA : pip install -r requirements-ia.txt", file=sys.stderr)
        return 1
    cible = dossier_modeles() / NOM_MODELE
    print(f"Téléchargement de {DEPOT_MODELE} dans {cible} (environ 470 Mo)…")
    snapshot_download(
        repo_id=DEPOT_MODELE,
        local_dir=str(cible),
        allow_patterns=["*.json", "*.txt", "*.model", "model.safetensors", "1_Pooling/*"],
        ignore_patterns=["onnx/*", "openvino/*"],
    )
    print("Modèle prêt. INJARA l'utilisera au prochain lancement.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
