"""Planification annoncée au candidat : durée, mode, adresse, message, confirmation, chevauchements."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.services import coffre

from .test_traitement import POSTE_DEV, boite, candidature_de, creer_poste, cv_pdf, recevoir, services  # noqa: F401


def _date(heure: int = 10, jours: int = 2) -> str:
    jour = datetime.now(timezone.utc) + timedelta(days=jours)
    return jour.replace(hour=heure, minute=0, second=0, microsecond=0).isoformat()


def _candidats(connecte, services, boite, tmp_path, n=2):  # noqa: F811
    creer_poste(connecte, POSTE_DEV)
    for i, cv in enumerate(["dev_python", "jeune_diplome"][:n]):
        recevoir(boite, tmp_path, "Candidature DEV-2026-04", [(f"CV_{i}.pdf", cv_pdf(cv))], expediteur=f"C{i} <c{i}@x.cm>")
    services.traitement.traiter()
    return [candidature_de(services, f"CV_{i}.pdf")["id"] for i in range(n)]


SUR_SITE = {"duree_minutes": 60, "mode": "sur_site", "adresse": "Bonapriso, Douala", "message": "Apportez une pièce d'identité."}


def test_planifier_sur_site_puis_confirmer(connecte, services, boite, tmp_path):  # noqa: F811
    (cid, _) = _candidats(connecte, services, boite, tmp_path)
    r = connecte.post(f"/candidatures/{cid}/entretiens", json={**SUR_SITE, "date_entretien": _date()})
    assert r.status_code == 201, r.text
    e = r.json()
    assert (e["mode"], e["adresse"], e["duree_minutes"], e["message"]) == ("sur_site", "Bonapriso, Douala", 60, "Apportez une pièce d'identité.")
    assert e["confirme_le"] is None and e["chevauchements"] == [] and e["code_invitation"]
    assert services.entretiens.entretiens.get(e["id"])["message"].startswith(coffre.PREFIXE_TEXTE)  # chiffré en base

    confirme = connecte.put(f"/entretiens/{e['id']}/confirmation", json={"confirme": True}).json()
    assert confirme["confirme_le"] is not None
    # Même date : la confirmation reste ; nouvelle date : à reconfirmer par le candidat
    meme = connecte.put(f"/entretiens/{e['id']}", json={**SUR_SITE, "date_entretien": _date(), "message": ""}).json()
    assert meme["confirme_le"] is not None and meme["message"] is None
    nouvelle = connecte.put(f"/entretiens/{e['id']}", json={**SUR_SITE, "date_entretien": _date(15)}).json()
    assert nouvelle["confirme_le"] is None
    assert nouvelle["expire_le"] > nouvelle["date_entretien"]  # le lien reste valable après la nouvelle date


def test_par_defaut_en_ligne(connecte, services, boite, tmp_path):  # noqa: F811
    (cid, _) = _candidats(connecte, services, boite, tmp_path)
    e = connecte.post(f"/candidatures/{cid}/entretiens", json={"date_entretien": _date(), "adresse": "ignorée"}).json()
    assert (e["mode"], e["adresse"], e["duree_minutes"]) == ("en_ligne", None, 60)


def test_regles_de_saisie(connecte, services, boite, tmp_path):  # noqa: F811
    (cid, _) = _candidats(connecte, services, boite, tmp_path)
    passe = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    r = connecte.post(f"/candidatures/{cid}/entretiens", json={**SUR_SITE, "date_entretien": passe})
    assert r.status_code == 422 and "passée" in r.json()["champs"]["date_entretien"]
    r = connecte.post(f"/candidatures/{cid}/entretiens", json={"date_entretien": _date(), "duree_minutes": 5, "mode": "sur_site", "adresse": ""})
    assert r.status_code == 422 and {"duree_minutes", "adresse"} <= set(r.json()["champs"])
    assert connecte.post(f"/candidatures/{cid}/entretiens", json={"date_entretien": _date(), "mode": "telephone"}).status_code == 422


def test_chevauchement_signale_sans_bloquer(connecte, services, boite, tmp_path):  # noqa: F811
    a, b = _candidats(connecte, services, boite, tmp_path)
    connecte.post(f"/candidatures/{a}/entretiens", json={**SUR_SITE, "date_entretien": _date(10)})
    r = connecte.post(f"/candidatures/{b}/entretiens", json={**SUR_SITE, "date_entretien": _date(10).replace("T10:00", "T10:30")})
    assert r.status_code == 201 and len(r.json()["chevauchements"]) == 1
    juste_apres = connecte.put(f"/entretiens/{r.json()['id']}", json={**SUR_SITE, "date_entretien": _date(11)})
    assert juste_apres.json()["chevauchements"] == []  # 10 h - 11 h puis 11 h : pas de chevauchement


def test_seul_un_entretien_planifie_se_modifie(connecte, services, boite, tmp_path):  # noqa: F811
    (cid, _) = _candidats(connecte, services, boite, tmp_path)
    e = connecte.post(f"/candidatures/{cid}/entretiens", json={**SUR_SITE, "date_entretien": _date()}).json()
    connecte.put(f"/entretiens/{e['id']}/statut", json={"statut": "annule"})
    assert connecte.put(f"/entretiens/{e['id']}", json={**SUR_SITE, "date_entretien": _date(15)}).status_code == 409
    assert connecte.put(f"/entretiens/{e['id']}/confirmation", json={"confirme": True}).status_code == 409
