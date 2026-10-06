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


def test_prechargement_en_arriere_plan(monkeypatch, tmp_path):
    """Pendant le chargement, statut() et pret répondent sans attendre ; le rappel arrive à la fin."""
    import threading

    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "model.safetensors").write_bytes(b"x")
    libere, fini = threading.Event(), threading.Event()

    def sonde_lente():
        libere.wait(5)
        return "Moteur d'analyse impossible à charger : essai"

    monkeypatch.setattr(semantique, "sonder_import", sonde_lente)
    modele = semantique.ModeleSemantique(tmp_path)
    modele.precharger(fini.set)
    assert modele.pret is False
    assert modele.statut() == {"disponible": False, "en_chargement": True, "modele": semantique.NOM_MODELE, "motif": None}
    modele.precharger(lambda: None)  # déjà lancé : sans effet
    libere.set()
    assert fini.wait(5)
    statut = modele.statut()
    assert statut["en_chargement"] is False and statut["disponible"] is False
    assert "essai" in statut["motif"]


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


def test_sonde_dans_l_application_installee(monkeypatch):
    """Exécutable PyInstaller : pas d'interpréteur, l'exécutable du backend fait l'essai lui-même."""
    import subprocess
    import sys

    commandes = []
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(subprocess, "run", lambda commande, **k: commandes.append(commande) or _Resultat(0))
    assert semantique.sonder_import() is None
    assert commandes == [[sys.executable, semantique.ARGUMENT_SONDE]]


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
