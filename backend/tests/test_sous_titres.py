"""Sous-titres : transcription Whisper en différé, service, routes et diffusion vers le candidat."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from backend.ia.transcription import Segment, Transcripteur, niveau
from backend.services.erreurs import Indisponible

from .test_entretien_visio import _demarrer, _recevoir, anonyme, entretien  # noqa: F401
from .test_traitement import boite, services  # noqa: F401

SECONDE = 16000


def _audio(secondes: float = 3.0, amplitude: float = 0.1) -> bytes:
    t = np.arange(int(secondes * SECONDE)) / SECONDE
    return (amplitude * np.sin(2 * np.pi * 220 * t)).astype("<f4").tobytes()


class TranscripteurFactice:
    nom = "factice"

    def __init__(self, *segments: Segment) -> None:
        self.segments = list(segments)
        self.appels = 0

    def disponible(self) -> bool:
        return True

    def transcrire(self, pcm):
        self.appels += 1
        return self.segments


def _envoyer(connecte, entretien, audio: bytes, locuteur="candidat", debut=0.0):
    return connecte.put(
        f"/entretiens/{entretien['id']}/sous-titres", params={"locuteur": locuteur, "debut": debut}, content=audio,
        headers={"Content-Type": "application/octet-stream"},
    )


# --- Transcripteur -----------------------------------------------------------------------------------------


def test_silence_et_bruit_faible_ne_sont_pas_transcrits(tmp_path):
    transcripteur = Transcripteur(tmp_path, "inexistant")  # le modèle n'est même pas chargé
    assert transcripteur.transcrire(np.zeros(SECONDE * 3, np.float32)) == []
    assert transcripteur.transcrire((np.random.default_rng(0).normal(0, 0.001, SECONDE * 3)).astype(np.float32)) == []
    assert niveau(np.zeros(0, np.float32)) == 0.0


def test_modele_absent(tmp_path):
    transcripteur = Transcripteur(tmp_path, "small")
    assert not transcripteur.disponible()
    with pytest.raises(Indisponible, match="small"):
        transcripteur.transcrire(np.frombuffer(_audio(), "<f4"))


CACHE_WHISPER = Path.home() / ".cache" / "whisper"


@pytest.mark.skipif(not (CACHE_WHISPER / "tiny.pt").is_file() or shutil.which("ffmpeg") is None, reason="modèle Whisper « tiny » ou ffmpeg absent")
def test_whisper_reconnait_de_la_vraie_parole(tmp_path, monkeypatch):
    sortie = tmp_path / "parole.f32"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "flite=text='hello, this is a test of the interview subtitles':voice=slt",
         "-ar", "16000", "-ac", "1", "-f", "f32le", str(sortie)],
        check=True,
    )
    monkeypatch.setenv("INJARA_WHISPER_LANGUE", "en")
    segments = Transcripteur(CACHE_WHISPER, "tiny").transcrire(np.fromfile(sortie, "<f4"))
    texte = " ".join(s.texte for s in segments).lower()
    assert "interview" in texte or "subtitles" in texte, texte
    assert all(0 <= s.debut <= s.fin <= 6 for s in segments)


# --- Routes ------------------------------------------------------------------------------------------------


def test_sous_titres_refuses_hors_entretien_sans_consentement_ou_extrait_invalide(connecte, app, entretien):
    app.state.services.sous_titres.transcripteur = TranscripteurFactice(Segment(0, 1, "Bonjour"))
    assert _envoyer(connecte, entretien, _audio()).status_code == 409  # encore « planifie »
    _demarrer(connecte, entretien, consentement=False)
    reponse = _envoyer(connecte, entretien, _audio())
    assert reponse.status_code == 409 and "consenti" in reponse.json()["detail"]
    connecte.put(f"/entretiens/{entretien['id']}/consentement", json={"accepte": True})
    assert _envoyer(connecte, entretien, _audio(), locuteur="inconnu").status_code == 422
    assert _envoyer(connecte, entretien, _audio(), debut=-1).status_code == 422
    assert _envoyer(connecte, entretien, b"\x00" * 7).status_code == 422  # pas un multiple de 4 octets
    assert _envoyer(connecte, entretien, b"").status_code == 422
    assert _envoyer(connecte, entretien, _audio(0.1)).status_code == 422  # trop court
    assert _envoyer(connecte, entretien, _audio(31)).status_code == 422  # trop long
    assert _envoyer(connecte, entretien, np.full(SECONDE, np.nan, "<f4").tobytes()).status_code == 422
    assert app.state.services.sous_titres.transcripteur.appels == 0  # rien n'est parti à Whisper


def test_sous_titres_modele_indisponible(connecte, app, entretien, tmp_path):
    app.state.services.sous_titres.transcripteur = Transcripteur(tmp_path)
    assert connecte.get("/sous-titres").json() == {"disponible": False, "modele": "small"}
    _demarrer(connecte, entretien)
    assert _envoyer(connecte, entretien, _audio()).status_code == 503


def test_sous_titres_exigent_une_session(app, entretien):
    from fastapi.testclient import TestClient

    from .conftest import JETON

    sans_session = TestClient(app, headers={"X-Injara-Token": JETON})
    assert sans_session.put(f"/entretiens/{entretien['id']}/sous-titres", params={"locuteur": "candidat", "debut": 0}, content=_audio()).status_code in (401, 403)


def test_transcription_chiffree_en_base_et_relue_a_la_fin(connecte, app, entretien):
    app.state.services.sous_titres.transcripteur = TranscripteurFactice(Segment(1.0, 3.0, "Bonjour, ravi d'être là."))
    _demarrer(connecte, entretien)
    reponse = _envoyer(connecte, entretien, _audio(), locuteur="candidat", debut=62.0)
    assert reponse.json()["segments"] == [{"locuteur": "candidat", "debut": 63.0, "fin": 65.0, "texte": "Bonjour, ravi d'être là."}]
    app.state.services.sous_titres.transcripteur = TranscripteurFactice(Segment(0.0, 2.0, "Merci de votre présence."))
    _envoyer(connecte, entretien, _audio(), locuteur="recruteur", debut=70.0)

    brut = app.state.services.entretiens.entretiens.get(entretien["id"])["transcription"]
    assert "Bonjour" not in brut and "Merci" not in brut  # chiffrée en base
    assert connecte.get(f"/entretiens/{entretien['id']}").json()["transcription"] == (
        "[01:03] Candidat : Bonjour, ravi d'être là.\n[01:10] Recruteur : Merci de votre présence."
    )


def test_extrait_sans_parole_n_ajoute_rien(connecte, app, entretien):
    app.state.services.sous_titres.transcripteur = TranscripteurFactice()
    _demarrer(connecte, entretien)
    assert _envoyer(connecte, entretien, _audio()).json() == {"segments": []}
    assert connecte.get(f"/entretiens/{entretien['id']}").json()["transcription"] is None


def test_sous_titres_diffuses_au_candidat(anonyme, connecte, app, entretien):  # noqa: F811
    app.state.services.sous_titres.transcripteur = TranscripteurFactice(Segment(0.0, 2.0, "Parlez-moi de votre parcours."))
    _demarrer(connecte, entretien)
    with anonyme.websocket_connect(f"/public/ws/candidat/{entretien['code_invitation']}") as ws:
        assert _recevoir(ws)["type"] == "presence"
        assert _envoyer(connecte, entretien, _audio(), locuteur="recruteur", debut=5.0).status_code == 200
        message = _recevoir(ws)
    assert message == {"type": "soustitre", "locuteur": "recruteur", "debut": 5.0, "fin": 7.0, "texte": "Parlez-moi de votre parcours."}
