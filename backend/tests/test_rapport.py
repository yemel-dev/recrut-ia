"""Données du rapport PDF : une seule route, tout y est, y compris ce qui n'a pas été calculé."""
from __future__ import annotations

from backend.ia import potentiel
from backend.services.rapport import MENTION

from .fixtures import fabrique
from .test_traitement import POSTE_COMPTABLE, POSTE_DEV, boite, candidature_de, creer_poste, cv_pdf, recevoir, services  # noqa: F401

CLES = {
    "genere_le", "entreprise", "poste", "candidat", "lecture", "assignation", "score", "competences", "experience",
    "diplome", "potentiel", "decision", "entretien", "entretien_prevu", "mails", "mention",
}


def _une_candidature(connecte, services, boite, tmp_path, cv="dev_python", objet="Candidature DEV-2026-04"):  # noqa: F811
    recevoir(boite, tmp_path, objet, [("CV_Awa.pdf", cv_pdf(cv))])
    services.traitement.traiter()
    return candidature_de(services, "CV_Awa.pdf")["id"]


def test_rapport_complet(connecte, services, boite, tmp_path):  # noqa: F811
    connecte.put("/entreprise", json={"nom": "Cabinet Ndong & Associés", "secteur": "Conseil", "ville": "Douala"})
    dev = creer_poste(connecte, POSTE_DEV)
    cid = _une_candidature(connecte, services, boite, tmp_path)
    connecte.put(f"/candidatures/{cid}/decision", json={"decision": "retenu", "note": "Profil solide"})

    r = connecte.get(f"/candidatures/{cid}/rapport")
    assert r.status_code == 200
    rapport = r.json()
    assert set(rapport) == CLES
    assert rapport["entreprise"]["nom"] == "Cabinet Ndong & Associés"
    assert rapport["poste"]["id"] == dev and rapport["poste"]["intitule"] == "Développeur Python" and rapport["poste"]["mention"] is None
    assert rapport["candidat"] == {**rapport["candidat"], "nom": "Awa Ndong", "email": "awa.ndong@example.cm"}
    assert rapport["candidat"]["telephone"]
    assert rapport["assignation"]["mode_libelle"] == "Poste cité dans le mail"

    score = rapport["score"]
    assert score["valeur"] == 100
    assert [c["cle"] for c in score["criteres"]] == ["competences", "experience", "formation", "adequation"]
    assert all(c["message"] for c in score["criteres"])
    assert sum(c["poids"] for c in score["criteres"]) == 100  # les poids réellement utilisés
    assert rapport["competences"]["trouvees"] == POSTE_DEV["competences_requises"] and rapport["competences"]["manquantes"] == []
    assert rapport["experience"]["total_mois"] > 0 and rapport["experience"]["periodes"]
    assert rapport["diplome"]["niveau"] == "Master" and "Génie Logiciel" in rapport["diplome"]["ligne"]
    assert rapport["potentiel"]["calcule"] and rapport["potentiel"]["niveau"] == potentiel.ELEVE
    assert len(rapport["potentiel"]["justification"]) == 5
    assert rapport["decision"]["libelle"] == "Retenu" and rapport["decision"]["note"] == "Profil solide" and rapport["decision"]["le"]
    assert rapport["entretien"] is None
    assert rapport["mention"] == MENTION


def test_adequation_non_calculee_indiquee(connecte, services, boite, tmp_path):  # noqa: F811
    creer_poste(connecte, POSTE_DEV)  # les tests n'ont pas le modèle Sentence-BERT
    rapport = connecte.get(f"/candidatures/{_une_candidature(connecte, services, boite, tmp_path)}/rapport").json()
    assert rapport["score"]["adequation_calculee"] is False
    assert "non calculée" in rapport["score"]["mention_adequation"]
    adequation = next(c for c in rapport["score"]["criteres"] if c["cle"] == "adequation")
    assert adequation["score"] is None and adequation["poids"] == 0 and adequation["poids_demande"] == 15


def test_potentiel_non_calcule(connecte, services, boite, tmp_path, monkeypatch):  # noqa: F811
    def en_panne(*args, **kwargs):
        raise RuntimeError("panne simulée")

    monkeypatch.setattr(potentiel, "evaluer", en_panne)
    creer_poste(connecte, POSTE_DEV)
    rapport = connecte.get(f"/candidatures/{_une_candidature(connecte, services, boite, tmp_path)}/rapport").json()
    assert rapport["potentiel"] == {"calcule": False, "niveau": None, "justification": [], "recommandation": None}
    assert rapport["score"]["valeur"] == 100


def test_potentiel_non_evaluable(connecte, services, boite, tmp_path):  # noqa: F811
    creer_poste(connecte, POSTE_DEV)
    texte = "Jean DUPONT\njean.dupont@example.cm\n" + "Motivé et disponible pour un poste de développeur Python. " * 4
    recevoir(boite, tmp_path, "Candidature DEV-2026-04", [("CV_Jean.pdf", fabrique.pdf_texte(texte))])
    services.traitement.traiter()
    rapport = connecte.get(f"/candidatures/{candidature_de(services, 'CV_Jean.pdf')['id']}/rapport").json()
    assert rapport["potentiel"]["calcule"] and rapport["potentiel"]["niveau"] == potentiel.NON_EVALUABLE


def test_sans_poste_assigne_meilleur_score(connecte, services, boite, tmp_path):  # noqa: F811
    creer_poste(connecte, POSTE_DEV)
    compta = creer_poste(connecte, POSTE_COMPTABLE)
    cid = _une_candidature(connecte, services, boite, tmp_path, cv="comptable", objet="CV")
    connecte.put(f"/candidatures/{cid}/poste", json={"poste_id": None})  # « aucun poste », choix du recruteur
    rapport = connecte.get(f"/candidatures/{cid}/rapport").json()
    assert rapport["poste"]["id"] == compta
    assert "meilleur score" in rapport["poste"]["mention"]
    assert rapport["score"]["valeur"] is not None


def test_cv_illisible_sans_score(connecte, services, boite, tmp_path):  # noqa: F811
    creer_poste(connecte, POSTE_DEV)
    recevoir(boite, tmp_path, "Candidature", [("CV_scan.pdf", fabrique.pdf_scanne())])
    services.traitement.ocr = type("SansOCR", (), {"disponible": False, "motif_indisponible": "essai", "statut": lambda self: {}})()
    services.traitement.traiter()
    c = candidature_de(services, "CV_scan.pdf")
    rapport = connecte.get(f"/candidatures/{c['id']}/rapport").json()
    assert set(rapport) == CLES
    assert rapport["lecture"]["statut"] == "illisible" and rapport["lecture"]["motif"]
    assert rapport["score"] is None and rapport["competences"] is None
    assert rapport["potentiel"]["calcule"] is False
    assert rapport["poste"] is not None and "aucun score" in rapport["poste"]["mention"].lower()
    assert rapport["decision"]["libelle"] == "À examiner"


def test_rapport_avec_entretien_prevu_et_mails(connecte, services, boite, tmp_path):  # noqa: F811
    from datetime import datetime, timedelta, timezone

    connecte.put("/entreprise", json={"nom": "Cabinet Ndong"})
    creer_poste(connecte, POSTE_DEV)
    cid = _une_candidature(connecte, services, boite, tmp_path)
    connecte.put(f"/candidatures/{cid}/decision", json={"decision": "retenu"})
    debut = (datetime.now(timezone.utc) + timedelta(days=3)).replace(hour=9, minute=0, second=0, microsecond=0)
    r = connecte.post(f"/candidatures/{cid}/entretiens", json={"date_entretien": debut.isoformat(), "duree_minutes": 90, "mode": "sur_site", "adresse": "Bonapriso, Douala"})
    assert r.status_code == 201, r.text
    assert connecte.post(f"/candidatures/{cid}/mails/invitation", json={}).json()["statut"] == "envoye"

    rapport = connecte.get(f"/candidatures/{cid}/rapport").json()
    prevu = rapport["entretien_prevu"]
    assert prevu["duree"] == "1 h 30" and prevu["lieu"] == "Bonapriso, Douala" and prevu["confirme"] is False
    assert rapport["entretien"] is None  # aucun entretien vidéo terminé
    mails = {m["type"]: m for m in rapport["mails"]}
    assert mails["invitation"]["statut"] == "envoye" and mails["invitation"]["le"]
    assert mails["refus"]["statut"] == "non_envoye"


def test_rapport_sans_entretien_ni_mail(connecte, services, boite, tmp_path):  # noqa: F811
    creer_poste(connecte, POSTE_DEV)
    rapport = connecte.get(f"/candidatures/{_une_candidature(connecte, services, boite, tmp_path)}/rapport").json()
    assert rapport["entretien_prevu"] is None
    assert {m["statut"] for m in rapport["mails"]} == {"non_envoye"}


def test_rapport_introuvable(connecte):
    assert connecte.get("/candidatures/999/rapport").status_code == 404


def test_rapport_exige_la_session(connecte):
    connecte.headers.pop("X-Injara-Session")
    assert connecte.get("/candidatures/1/rapport").status_code == 401
