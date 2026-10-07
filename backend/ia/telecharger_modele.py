"""Télécharge une fois les modèles dans le dossier des modèles (accès Internet requis) : Sentence-BERT et Face Landmarker.

    python -m backend.ia.telecharger_modele

Ensuite, INJARA les charge depuis le disque, hors ligne. Sans Sentence-BERT, le critère « adéquation » est ignoré ;
sans Face Landmarker (4 Mo), l'analyse du regard en entretien est indisponible.
"""
from __future__ import annotations

import sys

from .regard import telecharger_modele_visage
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
    print("Téléchargement du modèle d'analyse du regard (environ 4 Mo)…")
    telecharger_modele_visage(dossier_modeles())
    print("Modèles prêts. INJARA les utilisera au prochain lancement.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
