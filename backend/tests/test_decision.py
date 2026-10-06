"""Décision du recruteur : enregistrement, modification, filtre ; le score et le classement ne bougent pas."""
from __future__ import annotations

import sqlite3

from sqlalchemy import create_engine

from backend.database.migrations import ajouter_colonnes_manquantes
from backend.database.models import Base
from backend.services import coffre

from .test_traitement import POSTE_DEV, boite, candidature_de, creer_poste, cv_pdf, recevoir, services  # noqa: F401


def _trois_candidats(connecte, services, boite, tmp_path):  # noqa: F811
    """Trois candidatures sur le poste de développeur, de scores différents. Renvoie (poste, ids par ordre de score)."""
    dev = creer_poste(connecte, POSTE_DEV)
    for fichier, cv in [("CV_Awa.pdf", "dev_python"), ("CV_Brice.pdf", "jeune_diplome"), ("CV_JP.pdf", "scrum_master")]:
        recevoir(boite, tmp_path, "Candidature DEV-2026-04", [(fichier, cv_pdf(cv))], expediteur=f"{fichier} <{fichier}@x.cm>")
    services.traitement.traiter()
    classement = connecte.get(f"/postes/{dev}/classement").json()
    assert len(classement["elements"]) == 3
    return dev, [e["id"] for e in classement["elements"]]


def test_decision_par_defaut_puis_enregistree_et_modifiee(connecte, services, boite, tmp_path):  # noqa: F811
    _, (premier, *_) = _trois_candidats(connecte, services, boite, tmp_path)
    fiche = connecte.get(f"/candidatures/{premier}").json()
    assert fiche["decision"] == {"etat": "a_examiner", "note": None, "le": None}

    fiche = connecte.put(f"/candidatures/{premier}/decision", json={"decision": "en_attente", "note": "  Rappeler lundi.  "}).json()
    assert fiche["decision"]["etat"] == "en_attente" and fiche["decision"]["note"] == "Rappeler lundi."
    premiere_date = fiche["decision"]["le"]
    assert premiere_date

    fiche = connecte.put(f"/candidatures/{premier}/decision", json={"decision": "retenu", "note": ""}).json()
    assert fiche["decision"]["etat"] == "retenu" and fiche["decision"]["note"] is None
    assert fiche["decision"]["le"] >= premiere_date


def test_note_chiffree_en_base(connecte, services, boite, tmp_path):  # noqa: F811
    _, (premier, *_) = _trois_candidats(connecte, services, boite, tmp_path)
    connecte.put(f"/candidatures/{premier}/decision", json={"decision": "retenu", "note": "Très bon entretien téléphonique"})
    brute = services.candidatures.candidatures.get(premier)
    assert brute["decision_note"].startswith(coffre.PREFIXE_TEXTE) and "entretien" not in brute["decision_note"]


def test_decision_invalide_ou_note_trop_longue(connecte, services, boite, tmp_path):  # noqa: F811
    _, (premier, *_) = _trois_candidats(connecte, services, boite, tmp_path)
    reponse = connecte.put(f"/candidatures/{premier}/decision", json={"decision": "embauche"})
    assert reponse.status_code == 422 and "decision" in reponse.json()["champs"]
    reponse = connecte.put(f"/candidatures/{premier}/decision", json={"decision": "retenu", "note": "x" * 2001})
    assert reponse.status_code == 422 and "note" in reponse.json()["champs"]
    assert connecte.get(f"/candidatures/{premier}").json()["decision"]["etat"] == "a_examiner"


def test_score_et_classement_inchanges(connecte, services, boite, tmp_path):  # noqa: F811
    dev, ids = _trois_candidats(connecte, services, boite, tmp_path)
    avant = connecte.get(f"/postes/{dev}/classement").json()["elements"]
    connecte.put(f"/candidatures/{ids[0]}/decision", json={"decision": "ecarte"})
    connecte.put(f"/candidatures/{ids[2]}/decision", json={"decision": "retenu"})
    services.traitement.traiter()  # même après un passage complet du traitement
    apres = connecte.get(f"/postes/{dev}/classement").json()["elements"]
    assert [(e["id"], e["rang"], e["score"]) for e in apres] == [(e["id"], e["rang"], e["score"]) for e in avant]
    assert [e["decision"] for e in apres] == ["ecarte", "a_examiner", "retenu"]


def test_ecarte_reste_visible_partout(connecte, services, boite, tmp_path):  # noqa: F811
    dev, ids = _trois_candidats(connecte, services, boite, tmp_path)
    connecte.put(f"/candidatures/{ids[0]}/decision", json={"decision": "ecarte"})
    assert ids[0] in [e["id"] for e in connecte.get(f"/postes/{dev}/classement").json()["elements"]]
    assert ids[0] in [e["id"] for e in connecte.get("/candidatures").json()["elements"]]
    assert connecte.get(f"/candidatures/{ids[0]}").status_code == 200


def test_filtre_par_decision_garde_le_rang(connecte, services, boite, tmp_path):  # noqa: F811
    dev, ids = _trois_candidats(connecte, services, boite, tmp_path)
    connecte.put(f"/candidatures/{ids[2]}/decision", json={"decision": "retenu"})
    connecte.put(f"/candidatures/{ids[1]}/decision", json={"decision": "ecarte"})

    retenus = connecte.get(f"/postes/{dev}/classement?decision=retenu").json()
    assert [(e["id"], e["rang"]) for e in retenus["elements"]] == [(ids[2], 3)]
    assert retenus["par_decision"] == {"a_examiner": 1, "retenu": 1, "en_attente": 0, "ecarte": 1}
    assert connecte.get(f"/postes/{dev}/classement?decision=en_attente").json()["elements"] == []
    assert connecte.get(f"/postes/{dev}/classement?decision=inconnue").status_code == 422


# --- Le texte des sections du CV n'est plus enregistré en clair ------------------------------------------


def test_extraction_sans_texte_de_section(connecte, services, boite, tmp_path):  # noqa: F811
    _, (premier, *_) = _trois_candidats(connecte, services, boite, tmp_path)
    extraction = services.candidatures.candidatures.get(premier)["extraction"]
    assert isinstance(extraction["sections"], list) and "experience" in extraction["sections"]
    assert "Django" not in str(extraction["sections"])
    assert "experience" in connecte.get(f"/candidatures/{premier}").json()["extraction"]["sections"]


def test_sections_en_clair_d_avant_nettoyees(connecte, services, boite, tmp_path):  # noqa: F811
    _, (premier, *_) = _trois_candidats(connecte, services, boite, tmp_path)
    depot = services.candidatures.candidatures
    ancienne = {**depot.get(premier)["extraction"], "sections": {"experience": "Développeuse Python chez Orange"}}
    depot.maj(premier, extraction=ancienne)
    services.traitement.traiter()
    assert depot.get(premier)["extraction"]["sections"] == ["experience"]


# --- Base existante ----------------------------------------------------------------------------------------


def test_migration_ajoute_la_decision_aux_candidatures_existantes(tmp_path):
    chemin = tmp_path / "ancienne.db"
    with sqlite3.connect(chemin) as base:
        colonnes = [c for c in Base.metadata.tables["candidatures"].columns if not c.name.startswith("decision")]
        base.execute("CREATE TABLE candidatures (" + ", ".join(f'"{c.name}"' for c in colonnes) + ")")
        base.execute('INSERT INTO candidatures ("id", "cle") VALUES (1, \'m1\')')
    moteur = create_engine(f"sqlite:///{chemin.as_posix()}")
    ajoutees = ajouter_colonnes_manquantes(moteur)
    assert {"candidatures.decision", "candidatures.decision_note", "candidatures.decision_le"} <= set(ajoutees)
    with moteur.connect() as connexion:
        assert connexion.exec_driver_sql("SELECT decision FROM candidatures").scalar() == "a_examiner"
    moteur.dispose()
