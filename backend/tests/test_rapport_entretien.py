"""Section « entretien » du rapport : regard, vigilance et transcription du dernier entretien terminé."""
from __future__ import annotations

from backend.ia.regard import Mesure
from backend.ia.transcription import Segment

from .test_entretien_visio import _demarrer, anonyme, entretien  # noqa: F401
from .test_regard import FACE, AnalyseurFactice, _image
from .test_sous_titres import TranscripteurFactice, _audio, _envoyer
from .test_traitement import boite, services  # noqa: F401


def _rapport(connecte, entretien):
    return connecte.get(f"/candidatures/{entretien['candidature_id']}/rapport").json()


def test_pas_d_entretien_pas_de_section(connecte, entretien):
    assert _rapport(connecte, entretien)["entretien"] is None  # planifié seulement
    _demarrer(connecte, entretien)
    assert _rapport(connecte, entretien)["entretien"] is None  # en cours : pas de bilan encore


def test_rapport_d_un_entretien_complet(connecte, app, anonyme, entretien, monkeypatch):  # noqa: F811
    services = app.state.services
    horloge = iter(i * 0.25 for i in range(10_000))
    monkeypatch.setattr("backend.services.regard.time.monotonic", lambda: next(horloge))
    code = entretien["code_invitation"]
    anonyme.post(f"/public/api/{code}/consentement", json={"accepte": True, "consignes": True})
    connecte.put(f"/entretiens/{entretien['id']}/statut", json={"statut": "en_cours"})

    services.regard.analyseur = AnalyseurFactice(FACE)
    for _ in range(16):
        _image(connecte, entretien)
    services.regard.analyseur = AnalyseurFactice(Mesure(1, 0.0, 0.0, 0.7, 0.0))
    for _ in range(16):
        _image(connecte, entretien)
    anonyme.post(f"/public/api/{code}/signal", json={"type": "perte_focus", "duree_s": 12.5, "raison": "onglet_masque"})
    services.sous_titres.transcripteur = TranscripteurFactice(Segment(0.0, 2.0, "Bonjour <b>Awa</b> & bienvenue."))
    _envoyer(connecte, entretien, _audio(), locuteur="recruteur", debut=5.0)
    connecte.put(f"/entretiens/{entretien['id']}/resultats", json={"score_contenu": 70, "resume": "Candidate claire et posée."})
    connecte.put(f"/entretiens/{entretien['id']}/statut", json={"statut": "termine"})

    e = _rapport(connecte, entretien)["entretien"]
    assert e["id"] == entretien["id"] and e["debut_le"] and e["fin_le"] and e["enregistre"] is False
    assert e["scores"]["regard"] is not None and e["scores"]["contenu"] == 70 and e["scores"]["confiance"] is None
    assert e["scores"]["entretien"] is not None
    assert e["regard"]["calcule"] and e["regard"]["part_regard_detourne"] > 0
    assert e["vigilance"]["consentement"] is True and e["vigilance"]["consignes_acceptees_le"]
    types = {s["type"]: s for s in e["signaux"]}
    assert types["regard_detourne"]["regard"] is True and types["regard_detourne"]["libelle"] == "Regard détourné de l'écran"
    focus = types["perte_focus"]
    assert focus["regard"] is False and focus["duree_s"] == 12.5 and focus["raison"] == "autre onglet ou fenêtre réduite"
    assert focus["a"] and focus["a"].count(":") == 2
    assert e["transcription"] == "[00:05] Recruteur : Bonjour <b>Awa</b> & bienvenue."
    assert e["resume"] == "Candidate claire et posée." and "ne prouvent rien" in e["mention"]


def test_dernier_entretien_termine_seulement(connecte, entretien):
    connecte.put(f"/entretiens/{entretien['id']}/statut", json={"statut": "annule"})
    assert _rapport(connecte, entretien)["entretien"] is None


def test_entretien_sans_analyse(connecte, entretien):
    _demarrer(connecte, entretien, consentement=False)
    connecte.put(f"/entretiens/{entretien['id']}/statut", json={"statut": "termine"})
    e = _rapport(connecte, entretien)["entretien"]
    assert e["regard"] == {"calcule": False} and e["signaux"] == [] and e["transcription"] is None
    assert e["vigilance"] == {"consentement": False, "consignes_acceptees_le": None}
    assert set(e["scores"].values()) == {None}
