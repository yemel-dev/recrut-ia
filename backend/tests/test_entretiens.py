"""Entretiens vidéo côté recruteur : planification, cycle de vie, consentement, alertes, résultats."""
from __future__ import annotations

from backend.services import coffre

from .test_decision import _trois_candidats
from .test_traitement import boite, services  # noqa: F401


def _candidature(connecte, services, boite, tmp_path):  # noqa: F811
    _, (premier, *_) = _trois_candidats(connecte, services, boite, tmp_path)
    return premier


def _planifier(connecte, candidature_id, **corps):
    reponse = connecte.post(f"/candidatures/{candidature_id}/entretiens", json=corps)
    assert reponse.status_code == 201, reponse.text
    return reponse.json()


def test_session_requise(client):
    assert client.get("/entretiens").status_code == 401
    assert client.post("/candidatures/1/entretiens", json={}).status_code == 401


def test_planification(connecte, services, boite, tmp_path):  # noqa: F811
    cid = _candidature(connecte, services, boite, tmp_path)
    e = _planifier(connecte, cid, date_entretien="2026-11-03T09:30:00")
    assert e["statut"] == "planifie" and e["candidature_id"] == cid and len(e["code_invitation"]) >= 12
    assert e["consentement_enregistrement"] is False and e["score_entretien"] is None
    assert e["date_entretien"].startswith("2026-11-03T09:30")
    assert [x["id"] for x in connecte.get(f"/candidatures/{cid}/entretiens").json()] == [e["id"]]
    assert connecte.get("/entretiens?statut=planifie").json()[0]["id"] == e["id"]
    assert connecte.get("/entretiens?statut=inconnu").status_code == 422


def test_un_seul_entretien_actif_par_candidature(connecte, services, boite, tmp_path):  # noqa: F811
    cid = _candidature(connecte, services, boite, tmp_path)
    e = _planifier(connecte, cid)
    assert connecte.post(f"/candidatures/{cid}/entretiens", json={}).status_code == 409
    connecte.put(f"/entretiens/{e['id']}/statut", json={"statut": "annule"})
    assert _planifier(connecte, cid)["id"] != e["id"]


def test_candidature_inconnue(connecte):
    assert connecte.post("/candidatures/999/entretiens", json={}).status_code == 404
    assert connecte.get("/entretiens/999").status_code == 404


def test_cycle_de_vie(connecte, services, boite, tmp_path):  # noqa: F811
    cid = _candidature(connecte, services, boite, tmp_path)
    e = _planifier(connecte, cid)
    url = f"/entretiens/{e['id']}/statut"
    assert connecte.put(url, json={"statut": "termine"}).status_code == 409  # il faut d'abord démarrer
    en_cours = connecte.put(url, json={"statut": "en_cours"}).json()
    assert en_cours["statut"] == "en_cours" and en_cours["debut_le"]
    assert connecte.put(url, json={"statut": "en_cours"}).status_code == 409
    termine = connecte.put(url, json={"statut": "termine"}).json()
    assert termine["fin_le"]
    assert connecte.put(url, json={"statut": "annule"}).status_code == 409  # un entretien terminé ne s'annule pas
    assert connecte.put(url, json={"statut": "planifie"}).status_code == 422


def test_consentement(connecte, services, boite, tmp_path):  # noqa: F811
    cid = _candidature(connecte, services, boite, tmp_path)
    e = _planifier(connecte, cid)
    url = f"/entretiens/{e['id']}/consentement"
    assert connecte.put(url, json={"accepte": True}).json()["consentement_enregistrement"] is True
    assert connecte.put(url, json={"accepte": False}).json()["consentement_enregistrement"] is False
    connecte.put(f"/entretiens/{e['id']}/statut", json={"statut": "annule"})
    assert connecte.put(url, json={"accepte": True}).status_code == 409


def test_alertes_seulement_en_cours(connecte, services, boite, tmp_path):  # noqa: F811
    cid = _candidature(connecte, services, boite, tmp_path)
    e = _planifier(connecte, cid)
    url = f"/entretiens/{e['id']}/alertes"
    assert connecte.post(url, json={"type": "perte_focus"}).status_code == 409
    connecte.put(f"/entretiens/{e['id']}/statut", json={"statut": "en_cours"})
    assert connecte.post(url, json={"type": "triche_inconnue"}).status_code == 422
    assert connecte.post(url, json={"type": "application_suspecte", "details": {"application": "chatgpt"}}).status_code == 201
    assert connecte.post(url, json={"type": "perte_focus", "details": {"duree_s": 5}}).status_code == 201
    alertes = connecte.get(f"/entretiens/{e['id']}").json()["alertes"]
    assert [a["type"] for a in alertes] == ["application_suspecte", "perte_focus"]
    assert alertes[0]["details"] == {"application": "chatgpt"}


def test_resultats_et_score_pondere(connecte, services, boite, tmp_path):  # noqa: F811
    cid = _candidature(connecte, services, boite, tmp_path)
    e = _planifier(connecte, cid)
    url = f"/entretiens/{e['id']}/resultats"
    fiche = connecte.put(url, json={"score_regard": 50, "score_contenu": 80, "score_confiance": 60, "resume": " Bon profil. "}).json()
    assert fiche["score_entretien"] == 65.0  # 50*0,3 + 80*0,4 + 60*0,3
    assert fiche["resume"] == "Bon profil."
    # un champ omis garde sa valeur précédente
    assert connecte.put(url, json={"score_contenu": 90}).json()["score_entretien"] == 69.0  # 50*0,3 + 90*0,4 + 60*0,3
    assert connecte.put(url, json={"score_regard": 101}).status_code == 422

    # une composante jamais renseignée : les poids des autres sont ramenés à 100 %
    connecte.put(f"/entretiens/{e['id']}/statut", json={"statut": "annule"})
    autre = _planifier(connecte, cid)
    assert connecte.put(f"/entretiens/{autre['id']}/resultats", json={"score_contenu": 80}).json()["score_entretien"] == 80.0
    assert connecte.put(url, json={"resume": "x" * 4001}).status_code == 422


def test_transcription_chiffree_en_base(connecte, services, boite, tmp_path):  # noqa: F811
    cid = _candidature(connecte, services, boite, tmp_path)
    e = _planifier(connecte, cid)
    connecte.put(f"/entretiens/{e['id']}/resultats", json={"transcription": "Je maîtrise Django depuis cinq ans."})
    brute = services.entretiens.entretiens.get(e["id"])
    assert brute["transcription"].startswith(coffre.PREFIXE_TEXTE) and "Django" not in brute["transcription"]
    assert connecte.get(f"/entretiens/{e['id']}").json()["transcription"] == "Je maîtrise Django depuis cinq ans."
    assert "transcription" not in connecte.get("/entretiens").json()[0]


def test_ne_touche_pas_a_la_decision(connecte, services, boite, tmp_path):  # noqa: F811
    cid = _candidature(connecte, services, boite, tmp_path)
    avant = connecte.get(f"/candidatures/{cid}").json()
    e = _planifier(connecte, cid)
    connecte.put(f"/entretiens/{e['id']}/resultats", json={"score_regard": 10, "score_contenu": 10, "score_confiance": 10})
    apres = connecte.get(f"/candidatures/{cid}").json()
    assert apres["decision"] == avant["decision"] and apres["scores"] == avant["scores"]
