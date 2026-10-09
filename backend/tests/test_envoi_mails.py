"""Envoi des mails aux candidats, avec le faux expéditeur (jamais la vraie API Gmail)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.services import coffre

from .fixtures import fabrique
from .test_traitement import POSTE_DEV, boite, candidature_de, creer_poste, cv_pdf, recevoir, services  # noqa: F401

def _demain(heure: int = 10) -> str:
    jour = datetime.now(timezone.utc) + timedelta(days=2)
    return jour.replace(hour=heure, minute=0, second=0, microsecond=0).isoformat()


@pytest.fixture
def faux(services):  # noqa: F811
    return services.envoi_mails.expediteur()


@pytest.fixture
def poste(connecte, services, boite, tmp_path):  # noqa: F811
    """Un poste et trois candidatures lisibles (adresses c0, c1, c2)."""
    connecte.put("/entreprise", json={"nom": "Cabinet Ndong"})
    dev = creer_poste(connecte, POSTE_DEV)
    for i, cv in enumerate(["dev_python", "jeune_diplome", "scrum_master"]):
        recevoir(boite, tmp_path, f"Candidature DEV-2026-04 ({i})", [(f"CV_{i}.pdf", cv_pdf(cv))], expediteur=f"Candidat {i} <c{i}@x.cm>")
    services.traitement.traiter()
    return dev


def ids(services, n=3):  # noqa: F811
    return [candidature_de(services, f"CV_{i}.pdf")["id"] for i in range(n)]


def decider(connecte, cid, decision):
    assert connecte.put(f"/candidatures/{cid}/decision", json={"decision": decision}).status_code == 200


def planifier(connecte, cid, heure=10, **champs):
    """Planifie l'entretien (module des entretiens), ou le replanifie s'il existe déjà."""
    corps = {"date_entretien": _demain(heure), "duree_minutes": 60, "mode": "sur_site", "adresse": "Bonapriso, Douala", **champs}
    planifies = [e for e in connecte.get(f"/candidatures/{cid}/entretiens").json() if e["statut"] == "planifie"]
    if planifies:
        r = connecte.put(f"/entretiens/{planifies[0]['id']}", json=corps)
    else:
        r = connecte.post(f"/candidatures/{cid}/entretiens", json=corps)
    assert r.status_code in (200, 201), r.text
    return r.json()


def envoyer(connecte, poste_id, type_, candidatures):
    r = connecte.post(f"/postes/{poste_id}/envois/{type_}", json={"candidatures": candidatures})
    assert r.status_code == 200, r.text
    return r.json()


# --- Invitations ---------------------------------------------------------------------------------------------


def test_aucun_mail_ne_part_sur_un_changement_de_decision(connecte, services, poste, faux):  # noqa: F811
    a, b, c = ids(services)
    decider(connecte, a, "retenu")
    planifier(connecte, a)
    decider(connecte, b, "ecarte")
    connecte.post(f"/postes/{poste}/cloture")
    assert faux.envoyes == []


def test_retenu_sans_date_pas_d_invitation(connecte, services, poste, faux):  # noqa: F811
    a, b, _ = ids(services)
    decider(connecte, a, "retenu")
    decider(connecte, b, "retenu")
    planifier(connecte, a)
    preparation = connecte.get(f"/postes/{poste}/envois/invitation").json()
    assert [d["candidature_id"] for d in preparation["destinataires"]] == [a]
    assert [(e["candidature_id"], "Aucun entretien planifié" in e["raison"]) for e in preparation["exclus"]] == [(b, True)]

    resultat = envoyer(connecte, poste, "invitation", [a, b])
    assert resultat["envoyes"] == 1 and resultat["ignores"] == 1
    assert [m.destinataire for m in faux.envoyes] == ["c0@x.cm"]


def test_contenu_de_l_invitation_dans_le_fil(connecte, services, poste, faux):  # noqa: F811
    a, _, _ = ids(services)
    decider(connecte, a, "retenu")
    planifier(connecte, a)
    apercu = connecte.get(f"/postes/{poste}/envois/invitation").json()["destinataires"][0]
    assert apercu["objet"] == "Re: Candidature DEV-2026-04 (0)" and apercu["dans_le_fil"] is True
    assert apercu["corps"].startswith("Bonjour Awa Ndong,")
    assert "Développeur Python" in apercu["corps"] and "Bonapriso, Douala" in apercu["corps"] and "Cabinet Ndong" in apercu["corps"]
    assert "{" not in apercu["corps"]
    score = candidature_de(services, "CV_0.pdf")["score"]
    assert "score" not in apercu["corps"].lower() and "classement" not in apercu["corps"].lower() and str(round(score)) not in apercu["corps"]

    envoyer(connecte, poste, "invitation", [a])
    mail = faux.envoyes[0]
    assert mail.fil is not None and mail.objet == "Re: Candidature DEV-2026-04 (0)"
    ligne = services.envoi_mails.mails.pour_candidature(a)[0]
    assert ligne["statut"] == "envoye" and ligne["dans_le_fil"] is True
    assert ligne["corps"].startswith(coffre.PREFIXE_TEXTE)  # corps chiffré dans l'historique


def test_double_envoi_bloque_sauf_renvoi_explicite(connecte, services, poste, faux):  # noqa: F811
    a, _, _ = ids(services)
    decider(connecte, a, "retenu")
    planifier(connecte, a)
    envoyer(connecte, poste, "invitation", [a])
    deuxieme = envoyer(connecte, poste, "invitation", [a])
    assert deuxieme["envoyes"] == 0 and "déjà envoyée" in deuxieme["resultats"][0]["raison"]
    assert "déjà envoyée" in connecte.get(f"/postes/{poste}/envois/invitation").json()["exclus"][0]["raison"]
    assert connecte.post(f"/candidatures/{a}/mails/invitation", json={}).status_code == 409
    assert len(faux.envoyes) == 1

    renvoi = connecte.post(f"/candidatures/{a}/mails/invitation", json={"forcer": True})
    assert renvoi.status_code == 200 and renvoi.json()["statut"] == "envoye"
    assert len(faux.envoyes) == 2


def test_echec_au_milieu_d_un_lot_puis_relance(connecte, services, poste, faux):  # noqa: F811
    a, b, c = ids(services)
    for i, cid in enumerate((a, b, c)):
        decider(connecte, cid, "retenu")
        planifier(connecte, cid, 9 + i)
    faux.echecs.add("c1@x.cm")
    resultat = envoyer(connecte, poste, "invitation", [a, b, c])
    assert [r["statut"] for r in resultat["resultats"]] == ["envoye", "echec", "envoye"]
    assert "refusée" in resultat["resultats"][1]["erreur"]
    assert sorted(m.destinataire for m in faux.envoyes) == ["c0@x.cm", "c2@x.cm"]
    etat = connecte.get(f"/candidatures/{b}/mails").json()["etats"]["invitation"]
    assert etat["statut"] == "echec" and "refusée" in etat["erreur"]

    faux.echecs.clear()
    relance = connecte.post(f"/postes/{poste}/envois/invitation", json={"candidatures": [a, b, c], "echecs_seulement": True}).json()
    assert [(r["candidature_id"], r["statut"]) for r in relance["resultats"]] == [(b, "envoye")]
    assert connecte.get(f"/candidatures/{b}/mails").json()["etats"]["invitation"]["statut"] == "envoye"


def test_modification_proposee_quand_la_date_change(connecte, services, poste, faux):  # noqa: F811
    a, _, _ = ids(services)
    decider(connecte, a, "retenu")
    planifier(connecte, a, 10)
    assert connecte.post(f"/candidatures/{a}/mails/modification", json={}).status_code == 409  # pas encore invité
    envoyer(connecte, poste, "invitation", [a])
    assert connecte.get(f"/candidatures/{a}/mails").json()["modification_proposee"] is False
    planifier(connecte, a, 15)
    assert connecte.get(f"/candidatures/{a}/mails").json()["modification_proposee"] is True
    apercu = connecte.get(f"/candidatures/{a}/mails/modification").json()["destinataires"][0]
    assert "La date de votre entretien a changé" in apercu["corps"]
    assert connecte.post(f"/candidatures/{a}/mails/modification", json={}).json()["statut"] == "envoye"
    assert connecte.get(f"/candidatures/{a}/mails").json()["modification_proposee"] is False


def test_entretien_en_ligne_avec_le_lien_de_la_visio(connecte, services, poste, faux, monkeypatch):  # noqa: F811
    a, _, _ = ids(services)
    decider(connecte, a, "retenu")
    entretien = planifier(connecte, a, mode="en_ligne", adresse=None)
    monkeypatch.delenv("INJARA_URL_PUBLIQUE", raising=False)
    exclus = connecte.get(f"/postes/{poste}/envois/invitation").json()["exclus"]
    assert "accès à distance" in exclus[0]["raison"]  # sans lien, pas d'invitation à une visio

    monkeypatch.setenv("INJARA_URL_PUBLIQUE", "https://entretiens.cabinet.cm")
    corps = connecte.get(f"/postes/{poste}/envois/invitation").json()["destinataires"][0]["corps"]
    assert f"en ligne, par visioconférence : https://entretiens.cabinet.cm/public/entretien/{entretien['code_invitation']}" in corps


def test_entretien_sans_date_pas_d_invitation(connecte, services, poste, faux):  # noqa: F811
    a, _, _ = ids(services)
    decider(connecte, a, "retenu")
    assert connecte.post(f"/candidatures/{a}/entretiens", json={"mode": "sur_site", "adresse": "Douala"}).status_code == 201
    assert "pas de date" in connecte.get(f"/postes/{poste}/envois/invitation").json()["exclus"][0]["raison"]


# --- Clôture et réponses négatives ------------------------------------------------------------------------------


def test_cloture_ne_touche_que_les_a_examiner(connecte, services, poste, faux):  # noqa: F811
    a, b, c = ids(services)
    decider(connecte, b, "en_attente")
    decider(connecte, c, "retenu")
    assert connecte.get(f"/postes/{poste}/cloture").json() == {"a_ecarter": 1, "en_attente": 1, "retenus": 1}
    assert connecte.post(f"/postes/{poste}/cloture").json() == {"ecartes": 1, "en_attente": 1}
    decisions = {cid: connecte.get(f"/candidatures/{cid}").json()["decision"]["etat"] for cid in (a, b, c)}
    assert decisions == {a: "ecarte", b: "en_attente", c: "retenu"}
    assert faux.envoyes == []


def test_reponses_negatives_aux_seuls_ecartes(connecte, services, poste, faux):  # noqa: F811
    a, b, c = ids(services)
    decider(connecte, a, "ecarte")
    decider(connecte, b, "retenu")
    preparation = connecte.get(f"/postes/{poste}/envois/refus").json()
    assert [d["candidature_id"] for d in preparation["destinataires"]] == [a]
    corps = preparation["destinataires"][0]["corps"]
    assert "ne donnons pas suite" in corps and "score" not in corps.lower()
    envoyer(connecte, poste, "refus", [a, b, c])
    assert [m.destinataire for m in faux.envoyes] == ["c0@x.cm"]
    assert envoyer(connecte, poste, "refus", [a])["envoyes"] == 0  # déjà envoyé


def test_cv_illisible_et_non_classe_aucun_mail(connecte, services, poste, boite, tmp_path, faux):  # noqa: F811
    recevoir(boite, tmp_path, "Candidature", [("CV_scan.pdf", fabrique.pdf_scanne())], expediteur="Scan <scan@x.cm>")
    services.traitement.ocr = type("SansOCR", (), {"disponible": False, "motif_indisponible": "essai", "statut": lambda self: {}})()
    services.traitement.traiter()
    illisible = candidature_de(services, "CV_scan.pdf")["id"]
    connecte.put(f"/candidatures/{illisible}/poste", json={"poste_id": poste})  # rattaché à la main
    decider(connecte, illisible, "ecarte")
    preparation = connecte.get(f"/postes/{poste}/envois/refus").json()
    assert preparation["destinataires"] == []
    assert preparation["exclus"][0]["raison"].startswith("CV illisible")

    a, _, _ = ids(services)
    connecte.put(f"/candidatures/{a}/poste", json={"poste_id": None})  # non classé
    decider(connecte, a, "ecarte")
    r = connecte.post(f"/candidatures/{a}/mails/refus", json={})
    assert r.status_code == 409
    envoyer(connecte, poste, "refus", [illisible, a])
    assert faux.envoyes == []


# --- Vrais destinataires, civilité, blocages --------------------------------------------------------------------


def test_les_mails_partent_toujours_aux_vrais_candidats(connecte, services, poste, faux):  # noqa: F811
    """Pas de mode test : même un ancien réglage « mode test » enregistré en base est sans effet."""
    a, b, _ = ids(services)
    services.reglages_mails.parametres.set("mails.mode_test", '{"actif": true, "adresse": "rh.test@exemple.cm"}')
    decider(connecte, a, "ecarte")
    decider(connecte, b, "ecarte")
    preparation = connecte.get(f"/postes/{poste}/envois/refus").json()
    assert "mode_test" not in preparation and preparation["blocages"] == []
    assert [d["destinataire"] for d in preparation["destinataires"]] == ["c0@x.cm", "c1@x.cm"]
    envoyer(connecte, poste, "refus", [a, b])
    assert [m.destinataire for m in faux.envoyes] == ["c0@x.cm", "c1@x.cm"]
    assert not faux.envoyes[0].objet.startswith("[TEST")
    assert connecte.get(f"/candidatures/{a}/mails").json()["etats"]["refus"]["statut"] == "envoye"
    assert connecte.put("/parametres/mails/mode-test", json={"actif": True, "adresse": "x@y.cm"}).status_code in (404, 405)


def test_nom_non_fiable_madame_monsieur(connecte, services, poste, boite, tmp_path, faux):  # noqa: F811
    texte = "curriculum vitae\njd@x.cm\n" + fabrique.texte_cv("dev_python").split("\n", 2)[2]
    recevoir(boite, tmp_path, "CV", [("CV_anonyme.pdf", fabrique.pdf_texte(texte))], expediteur="jd@x.cm")
    services.traitement.traiter()
    cid = candidature_de(services, "CV_anonyme.pdf")["id"]
    connecte.put(f"/candidatures/{cid}/poste", json={"poste_id": poste})
    decider(connecte, cid, "ecarte")
    apercu = connecte.get(f"/candidatures/{cid}/mails/refus").json()["destinataires"][0]
    assert apercu["corps"].startswith("Bonjour Madame, Monsieur,")


def test_sans_nom_d_entreprise_bloque(connecte, services, poste, faux):  # noqa: F811
    a, _, _ = ids(services)
    services.envoi_mails.entreprise.save(nom="")  # le profil refuse un nom vide : base vidée directement
    decider(connecte, a, "ecarte")
    assert connecte.get(f"/postes/{poste}/envois/refus").json()["blocages"]
    assert connecte.post(f"/postes/{poste}/envois/refus", json={"candidatures": [a]}).status_code == 409


def test_etat_des_mails_dans_le_classement(connecte, services, poste, faux):  # noqa: F811
    a, _, _ = ids(services)
    decider(connecte, a, "ecarte")
    envoyer(connecte, poste, "refus", [a])
    ligne = next(e for e in connecte.get(f"/postes/{poste}/classement").json()["elements"] if e["id"] == a)
    assert ligne["mails"] == {"invitation": "non_envoye", "modification": "non_envoye", "refus": "envoye"}
