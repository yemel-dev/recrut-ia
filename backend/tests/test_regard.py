"""Analyse du regard : calculs du suivi (sans caméra), analyseur MediaPipe, service et routes."""
from __future__ import annotations

import math

import numpy as np
import pytest

from backend.config import ROOT_DIR
from backend.ia.regard import (
    NOM_MODELE_VISAGE, AnalyseurVisage, Mesure, SuiviRegard, angles_tete, direction_regard,
)
from backend.services.erreurs import Indisponible

from .test_entretien_visio import _demarrer, entretien  # noqa: F401
from .test_traitement import boite, services  # noqa: F401

FACE = Mesure(1, 0.0, 0.0, 0.0, 0.0)


def _suivre(suivi: SuiviRegard, mesure: Mesure, debut: float, fin: float, pas: float = 0.25):
    evenements = []
    t = debut
    while t < fin:
        evenements += suivi.ajouter(mesure, t)
        t += pas
    return evenements


def _calibre() -> SuiviRegard:
    suivi = SuiviRegard()
    _suivre(suivi, FACE, 0, 4)  # 16 mesures : posture habituelle fixée
    return suivi


# --- Calculs -----------------------------------------------------------------------------------------------


def test_angles_de_la_tete_depuis_la_matrice_de_pose():
    def rotation(lacet, tangage):
        ly, lx = math.radians(lacet), math.radians(tangage)
        ry = np.array([[math.cos(ly), 0, math.sin(ly)], [0, 1, 0], [-math.sin(ly), 0, math.cos(ly)]])
        rx = np.array([[1, 0, 0], [0, math.cos(lx), -math.sin(lx)], [0, math.sin(lx), math.cos(lx)]])
        m = np.eye(4)
        m[:3, :3] = ry @ rx
        return m

    lacet, tangage = angles_tete(rotation(30, -10))
    assert lacet == pytest.approx(30, abs=1e-6) and tangage == pytest.approx(-10, abs=1e-6)
    assert angles_tete(np.eye(4)) == (0.0, 0.0)


def test_direction_du_regard_depuis_les_blendshapes():
    droite = direction_regard({"eyeLookOutRight": 0.8, "eyeLookInLeft": 0.6})
    assert droite[0] == pytest.approx(0.7) and droite[1] == 0
    gauche = direction_regard({"eyeLookInRight": 0.8, "eyeLookOutLeft": 0.6})
    assert gauche[0] == pytest.approx(-0.7)
    assert direction_regard({"eyeLookUpLeft": 0.4, "eyeLookUpRight": 0.4})[1] == pytest.approx(0.4)
    assert direction_regard({}) == (0.0, 0.0)


# --- Suivi d'un entretien ----------------------------------------------------------------------------------


def test_candidat_attentif_tout_le_long():
    suivi = _calibre()
    assert _suivre(suivi, Mesure(1, 4.0, -3.0, 0.1, 0.05), 4, 30) == []  # petits mouvements : rien à signaler
    assert suivi.etat == "attentif" and suivi.score() == 100.0
    assert suivi.bilan()["calibre"] is True


def test_regard_detourne_un_seul_evenement_par_episode():
    suivi = _calibre()
    detourne = Mesure(1, 0.0, 0.0, 0.6, 0.0)  # yeux à droite
    assert _suivre(suivi, detourne, 4, 6.5) == []  # moins de 3 s : un coup d'œil
    evenements = _suivre(suivi, detourne, 6.5, 12)
    assert [e.type for e in evenements] == ["regard_detourne"]  # une seule fois malgré la durée
    assert evenements[0].details["ecarts"]["regard_x"] == pytest.approx(0.6)
    _suivre(suivi, FACE, 12, 14)
    assert [e.type for e in _suivre(suivi, detourne, 14, 18)] == ["regard_detourne"]  # nouvel épisode, nouvel événement
    assert 0 < suivi.score() < 100


def test_tete_tournee_est_un_regard_detourne():
    suivi = _calibre()
    assert [e.type for e in _suivre(suivi, Mesure(1, 40.0, 0.0, 0.0, 0.0), 4, 9)] == ["regard_detourne"]


def test_l_ecart_se_mesure_a_la_posture_habituelle():
    suivi = SuiviRegard()
    penche = Mesure(1, 30.0, 15.0, 0.0, -0.2)  # candidat qui regarde toujours son écran de côté
    _suivre(suivi, penche, 0, 4)
    assert _suivre(suivi, penche, 4, 20) == [] and suivi.score() == 100.0


def test_pas_d_accusation_avant_l_etalonnage():
    suivi = SuiviRegard()
    assert _suivre(suivi, Mesure(1, 80.0, 0.0, 0.9, 0.0), 0, 2) == []
    assert suivi.etat == "attentif" and suivi.bilan()["calibre"] is False


def test_visage_absent_et_plusieurs_visages():
    suivi = _calibre()
    assert [e.type for e in _suivre(suivi, Mesure(0), 4, 9)] == ["visage_absent"]
    evenements = _suivre(suivi, Mesure(2, 0, 0, 0, 0), 9, 13)
    assert [e.type for e in evenements] == ["plusieurs_visages"] and evenements[0].details["visages"] == 2
    bilan = suivi.bilan()
    assert bilan["part_visage_absent"] > 0 and bilan["part_plusieurs_visages"] > 0 and bilan["evenements"] == 2


def test_une_coupure_de_connexion_n_est_pas_comptee_comme_du_temps_observe():
    suivi = _calibre()
    avant = suivi.duree
    suivi.ajouter(FACE, 4.0)
    suivi.ajouter(FACE, 600.0)  # dix minutes sans image
    assert suivi.duree - avant <= 0.25 + 1.0 + 1e-9  # l'intervalle normal puis la pause plafonnée


def test_agitation_de_la_tete():
    calme, agite = _calibre(), _calibre()
    _suivre(calme, Mesure(1, 1.0, 0.0, 0, 0), 4, 20)
    for i in range(64):
        agite.ajouter(Mesure(1, 10.0 if i % 2 else -10.0, 0.0, 0, 0), 4 + i * 0.25)
    assert agite.bilan()["agitation_tete_deg_par_min"] > calme.bilan()["agitation_tete_deg_par_min"] + 100


def test_sans_observation_pas_de_score():
    assert SuiviRegard().score() is None


# --- Analyseur (MediaPipe) ---------------------------------------------------------------------------------


def _jpeg(valeur: int = 128) -> bytes:
    cv2 = pytest.importorskip("cv2")
    return cv2.imencode(".jpg", np.full((240, 320, 3), valeur, np.uint8))[1].tobytes()


def test_analyseur_sans_modele(tmp_path):
    analyseur = AnalyseurVisage(tmp_path / "absent.task")
    assert not analyseur.disponible()
    with pytest.raises(Indisponible):
        analyseur.analyser(_jpeg())


@pytest.mark.skipif(not (ROOT_DIR / "modeles" / NOM_MODELE_VISAGE).is_file(), reason="modèle Face Landmarker non téléchargé")
def test_analyseur_image_sans_visage_et_image_illisible():
    analyseur = AnalyseurVisage(ROOT_DIR / "modeles" / NOM_MODELE_VISAGE)
    assert analyseur.analyser(_jpeg()) == Mesure(0)
    with pytest.raises(ValueError):
        analyseur.analyser(b"pas une image")
    analyseur.fermer()


# --- Service et routes -------------------------------------------------------------------------------------


class AnalyseurFactice:
    def __init__(self, *mesures: Mesure) -> None:
        self.mesures = list(mesures)

    def disponible(self) -> bool:
        return True

    def analyser(self, jpeg: bytes) -> Mesure:
        return self.mesures.pop(0) if len(self.mesures) > 1 else self.mesures[0]


def _image(connecte, entretien):
    return connecte.put(f"/entretiens/{entretien['id']}/regard", content=b"jpeg", headers={"Content-Type": "image/jpeg"})


def test_regard_refuse_hors_entretien_sans_consentement_ou_image_vide(connecte, app, entretien):
    app.state.services.regard.analyseur = AnalyseurFactice(FACE)
    assert _image(connecte, entretien).status_code == 409  # encore « planifie »
    _demarrer(connecte, entretien, consentement=False)
    reponse = _image(connecte, entretien)
    assert reponse.status_code == 409 and "consenti" in reponse.json()["detail"]
    connecte.put(f"/entretiens/{entretien['id']}/consentement", json={"accepte": True})
    assert connecte.put(f"/entretiens/{entretien['id']}/regard", content=b"").status_code == 422


def test_regard_modele_indisponible(connecte, app, entretien, tmp_path):
    app.state.services.regard.analyseur = AnalyseurVisage(tmp_path / "absent.task")
    assert connecte.get("/regard").json() == {"disponible": False}
    _demarrer(connecte, entretien)
    assert _image(connecte, entretien).status_code == 503


def test_regard_alertes_et_bilan_a_la_fin(connecte, app, entretien, monkeypatch):
    service = app.state.services.regard
    horloge = iter(i * 0.25 for i in range(10_000))
    monkeypatch.setattr("backend.services.regard.time.monotonic", lambda: next(horloge))
    service.analyseur = AnalyseurFactice(FACE)
    _demarrer(connecte, entretien)
    for _ in range(16):
        assert _image(connecte, entretien).json()["etat"] == "attentif"
    service.analyseur = AnalyseurFactice(Mesure(1, 0.0, 0.0, 0.7, 0.0))
    reponses = [_image(connecte, entretien).json() for _ in range(16)]
    assert reponses[-1]["etat"] == "regard_detourne"
    assert sum(len(r["evenements"]) for r in reponses) == 1

    detail = connecte.get(f"/entretiens/{entretien['id']}").json()
    assert [a["type"] for a in detail["alertes"]] == ["regard_detourne"]
    assert detail["score_regard"] is None  # calculé à la fin de l'entretien

    termine = connecte.put(f"/entretiens/{entretien['id']}/statut", json={"statut": "termine"}).json()
    assert 0 < termine["score_regard"] < 100 and termine["score_entretien"] == termine["score_regard"]
    assert termine["bilan_regard"]["part_regard_detourne"] > 0 and termine["bilan_regard"]["calibre"] is True
    assert _image(connecte, entretien).status_code == 409  # l'entretien est clos


def test_fin_d_entretien_sans_image_n_invente_pas_de_score(connecte, entretien):
    _demarrer(connecte, entretien)
    termine = connecte.put(f"/entretiens/{entretien['id']}/statut", json={"statut": "termine"}).json()
    assert termine["score_regard"] is None and termine["bilan_regard"] is None


def test_regard_exige_une_session(sans_session_regard, entretien):
    assert sans_session_regard.put(f"/entretiens/{entretien['id']}/regard", content=b"x").status_code in (401, 403)


@pytest.fixture
def sans_session_regard(app):
    from fastapi.testclient import TestClient

    from .conftest import JETON

    return TestClient(app, headers={"X-Injara-Token": JETON})
