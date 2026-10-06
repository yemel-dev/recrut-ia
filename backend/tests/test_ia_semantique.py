"""Chargement du modèle d'adéquation : toute panne désactive le critère sans casser le traitement."""
from __future__ import annotations

import builtins

import pytest

from backend.ia import semantique


@pytest.fixture
def faux_modele(tmp_path, monkeypatch):
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "model.safetensors").write_bytes(b"x")
    monkeypatch.setattr(semantique, "sonder_import", lambda: None)  # la sonde passe : on teste l'import dans le processus
    return tmp_path


def _import_qui_echoue(monkeypatch, exception):
    original = builtins.__import__

    def faux_import(nom, *args, **kwargs):
        if nom.startswith("sentence_transformers"):
            raise exception
        return original(nom, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", faux_import)


def test_modele_absent(tmp_path):
    modele = semantique.ModeleSemantique(tmp_path / "absent")
    assert modele.disponible is False
    assert "absent" in modele.motif_indisponible
    assert modele.encoder("Python") is None


def test_modele_incomplet_considere_absent(tmp_path):
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")  # poids encore en téléchargement
    assert semantique.ModeleSemantique(tmp_path).disponible is False


def test_dll_manquante_sous_windows(monkeypatch, faux_modele):
    _import_qui_echoue(monkeypatch, OSError("[WinError 126] Le module spécifié est introuvable (c10.dll)"))
    modele = semantique.ModeleSemantique(faux_modele)
    assert modele.disponible is False
    assert "Visual C++" in modele.motif_indisponible


def test_bibliotheque_absente(monkeypatch, faux_modele):
    _import_qui_echoue(monkeypatch, ImportError("No module named sentence_transformers"))
    modele = semantique.ModeleSemantique(faux_modele)
    assert modele.disponible is False
    assert "requirements-ia.txt" in modele.motif_indisponible


def test_vecteurs_en_octets_aller_retour():
    vecteur = semantique.normaliser_vecteur([3.0, 4.0])
    assert semantique.depuis_octets(semantique.en_octets(vecteur)) == pytest.approx([0.6, 0.8])
    assert semantique.similarite(vecteur, vecteur) == pytest.approx(1.0)


# --- Sonde : l'import est d'abord essayé dans un processus séparé ------------------------------------


class _Resultat:
    def __init__(self, code, stderr=""):
        self.returncode, self.stderr = code, stderr


@pytest.mark.parametrize(
    ("resultat", "extrait"),
    [
        (_Resultat(0), None),
        (_Resultat(1, "Traceback\nModuleNotFoundError: No module named 'sentence_transformers'"), "requirements-ia.txt"),
        (_Resultat(1, "OSError: [WinError 126] Error loading c10.dll"), "WinError 126"),
        (_Resultat(1, "RuntimeError: incompatible"), "incompatible"),
    ],
)
def test_sonde(monkeypatch, resultat, extrait):
    import subprocess

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: resultat)
    motif = semantique.sonder_import()
    assert motif is None if extrait is None else extrait in motif


def test_sonde_delai_depasse(monkeypatch):
    import subprocess

    def bloque(*args, **kwargs):
        raise subprocess.TimeoutExpired("python", kwargs.get("timeout"))

    monkeypatch.setattr(subprocess, "run", bloque)
    assert "délai" in semantique.sonder_import()


def test_echec_de_la_sonde_desactive_sans_importer(monkeypatch, tmp_path):
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "model.safetensors").write_bytes(b"x")
    monkeypatch.setattr(semantique, "sonder_import", lambda: "Le moteur d'analyse ne se charge pas (délai de 120 s dépassé).")
    _import_qui_echoue(monkeypatch, AssertionError("l'import ne doit pas être tenté dans le processus"))
    modele = semantique.ModeleSemantique(tmp_path)
    assert modele.disponible is False
    assert "délai" in modele.motif_indisponible
