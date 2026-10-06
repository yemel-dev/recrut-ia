"""Indicateur de potentiel : règles explicites, seuils nommés, signaux non évaluables exclus du calcul."""
from __future__ import annotations

from datetime import date

import pytest

from backend.ia import potentiel
from backend.ia.extraction import extraire
from backend.ia.potentiel import ELEVE, EXCEPTIONNEL, FAIBLE, MOYEN, NON_EVALUABLE, ProfilCV, Signal

from .fixtures import fabrique
from .test_traitement import POSTE_DEV, boite, candidature_de, creer_poste, recevoir, services  # noqa: F401

AUJOURDHUI = date(2026, 10, 1)

CV_PROGRESSION = """Mariam OUMAROU
mariam.oumarou@example.cm | +237 6 90 00 00 01

EXPÉRIENCE PROFESSIONNELLE
Responsable des systèmes d'information — Camtel, Yaoundé
Janvier 2023 - Présent
Encadrement d'une équipe de 8 développeurs, pilotage du programme de migration vers le cloud.
Développeuse senior — Afriland First Bank
Mars 2020 - Décembre 2022
Création de l'application mobile de la banque.
Développeuse junior — Kribi Tech
Septembre 2017 - Février 2020
Développement d'API en Java.
Stagiaire développeuse — MTN Cameroon
Février 2017 - Août 2017
Tests automatisés.

FORMATION
Master en Informatique — Université de Yaoundé I, 2017

COMPÉTENCES
Java, Python, Kubernetes, Docker, AWS, Terraform, PostgreSQL, Kafka, Angular, Scrum, Communication, Leadership

LANGUES
Français, Anglais

CERTIFICATIONS
AWS Certified Solutions Architect, 2022
"""

CV_STABLE = """Paul ESSOMBA
paul.essomba@example.cm

EXPÉRIENCE PROFESSIONNELLE
Comptable — Brasseries du Cameroun
Janvier 2016 - Présent
Saisie et contrôle des écritures comptables.
Comptable — Cabinet Ngono
Septembre 2009 - Décembre 2015
Tenue des comptes de PME.

FORMATION
Licence en Comptabilité — Université de Douala, 2009

COMPÉTENCES
Comptabilité générale, Sage 100, Excel, Fiscalité, Paie
"""

CV_PRESQUE_VIDE = """Jean DUPONT
jean.dupont@example.cm
Je suis motivé et disponible immédiatement pour tout poste dans votre entreprise.
Merci de considérer ma candidature, je reste à votre disposition pour un entretien.
"""


def evaluer(texte: str, niveau_requis: str | None = "Licence"):
    extraction = extraire(texte, AUJOURDHUI)
    profil = potentiel.profil_depuis_texte(texte, extraction.diplome.get("niveau"), AUJOURDHUI)
    return potentiel.evaluer(profil, niveau_requis)


def signaux(resultat) -> dict:
    return {s.cle: s for s in resultat.signaux}


# --- Les quatre profils ------------------------------------------------------------------------------------


def test_progression_nette():
    resultat = evaluer(CV_PROGRESSION, "Master")
    s = signaux(resultat)
    assert s["progression"].note == 2
    assert "Stagiaire développeuse" in s["progression"].phrase and "Responsable des systèmes d'information" in s["progression"].phrase
    assert s["progression"].faits["gain_niveaux"] == 4
    assert s["diversite"].note == 2  # 14 éléments en 3 familles
    assert s["stabilite"].note == 2
    assert s["formation"].note == 2
    assert s["leadership"].note == 2
    assert set(s["leadership"].faits["familles"]) >= {"encadrement", "responsabilité de projet", "création", "certification"}
    assert resultat.niveau == EXCEPTIONNEL
    assert resultat.recommandation == potentiel.RECOMMANDATION_ENCADREMENT


def test_profil_stable_sans_progression():
    resultat = evaluer(CV_STABLE, "Licence")
    s = signaux(resultat)
    assert s["progression"].note == 0 and "pas d'évolution" in s["progression"].phrase
    assert s["stabilite"].note == 2 and s["stabilite"].faits["moyenne_mois"] >= potentiel.STABILITE_BONNE_MOIS
    assert s["diversite"].note == 1
    assert s["leadership"].note == 0
    assert resultat.niveau == MOYEN  # 0 + 1 + 2 + 2 + 0 = 5 sur 10
    assert resultat.recommandation is None


def test_jeune_diplome_peu_de_donnees():
    resultat = evaluer(fabrique.texte_cv("jeune_diplome"), "Master")
    s = signaux(resultat)
    assert s["progression"].note is None and "non évaluable" in s["progression"].phrase  # un seul stage
    assert s["stabilite"].note is None  # aucun emploi hors stage
    assert [x.cle for x in resultat.signaux if x.evaluable] == ["diversite", "formation", "leadership"]
    assert resultat.ratio == pytest.approx(0.5)  # (1 + 2 + 0) / 6 : les signaux non évaluables ne comptent pas
    assert resultat.niveau == MOYEN


def test_cv_presque_vide():
    resultat = evaluer(CV_PRESQUE_VIDE)
    assert resultat.niveau == NON_EVALUABLE and resultat.ratio is None
    assert len(resultat.justification) == 5  # une phrase par signal, même non évaluable
    assert sum(1 for x in resultat.signaux if x.evaluable) < potentiel.SIGNAUX_MIN


# --- Règles ----------------------------------------------------------------------------------------------------


def _signaux(*notes) -> list[Signal]:
    return [Signal(f"s{i}", f"s{i}", note, "") for i, note in enumerate(notes)]


@pytest.mark.parametrize(
    ("notes", "niveau"),
    [
        ((0, 0, 0, 1, 1), FAIBLE),  # 0,2
        ((1, 1, 0, 0, 1), FAIBLE),  # 0,3 : sous le seuil Moyen (0,35)
        ((1, 1, 1, 0, 1), MOYEN),  # 0,4
        ((2, 1, 1, 1, 1), ELEVE),  # 0,6
        ((2, 2, 2, 2, 1), EXCEPTIONNEL),  # 0,9
        ((2, 2, 2, None, None), ELEVE),  # 1,0 mais seulement 3 signaux évaluables
        ((2, 2, None, None, None), NON_EVALUABLE),
    ],
)
def test_correspondance_notes_niveaux(notes, niveau):
    assert potentiel.niveau_depuis(_signaux(*notes))[0] == niveau


def test_non_evaluable_n_est_pas_une_mauvaise_note():
    avec_trou = potentiel.niveau_depuis(_signaux(2, 2, 2, 2, None))
    assert avec_trou == (EXCEPTIONNEL, 1.0)


@pytest.mark.parametrize(
    ("intitule", "stage", "niveau"),
    [
        ("Stagiaire comptable", False, 0),
        ("Développeur Java", True, 0),
        ("Assistant chef de projet", False, 1),
        ("Aide-comptable", False, 1),
        ("Développeuse web", False, 2),
        ("Comptable principale", False, 3),
        ("Ingénieur senior", False, 3),
        ("Chef de projet informatique", False, 4),
        ("Directrice financière", False, 4),
    ],
)
def test_niveau_des_intitules(intitule, stage, niveau):
    assert potentiel.niveau_intitule(intitule, stage) == niveau


def test_intitule_sur_la_ligne_de_dates():
    texte = "Awa NDONG\n\nEXPÉRIENCE\nDéveloppeuse web — Kribi Tech, 2019 - 2021\nAnalyste chez Orange 2021 - 2024\n"
    profil = potentiel.profil_depuis_texte(texte, None, AUJOURDHUI)
    assert [p.intitule for p in profil.periodes] == ["Développeuse web", "Analyste"]


def test_formation_sous_qualifiee_et_sans_diplome():
    profil = ProfilCV(diplome_niveau="BTS")
    assert potentiel.signal_formation(profil, "Master").note == 0
    assert potentiel.signal_formation(ProfilCV(diplome_niveau="Licence"), "Master").note == 1
    assert potentiel.signal_formation(ProfilCV(), "Master").note is None


def test_familles_de_competences():
    profil = ProfilCV(competences=("Python", "Anglais", "Travail en équipe"), langues=())
    assert potentiel.signal_diversite(profil).faits["familles"] == ["langues", "savoir-être", "techniques"]


# --- Dans le pipeline ---------------------------------------------------------------------------------------------


def test_potentiel_enregistre_et_recalcule_quand_le_poste_change(connecte, services, boite, tmp_path):  # noqa: F811
    dev = creer_poste(connecte, POSTE_DEV)
    recevoir(boite, tmp_path, "Candidature DEV-2026-04", [("CV_Brice.pdf", fabrique.pdf_texte(fabrique.texte_cv("jeune_diplome")))])
    services.traitement.traiter()
    c = candidature_de(services, "CV_Brice.pdf")
    fiche = connecte.get(f"/candidatures/{c['id']}").json()
    score_avant = next(s for s in fiche["scores"] if s["poste_id"] == dev)
    assert score_avant["potentiel"]["niveau"] == MOYEN
    assert {s["cle"]: s["note"] for s in score_avant["potentiel"]["signaux"]}["formation"] == 2
    classement = connecte.get(f"/postes/{dev}/classement").json()["elements"]
    assert classement[0]["potentiel_niveau"] == MOYEN

    # Le poste exige maintenant un doctorat : le signal formation baisse, le score aussi (critère formation), et le
    # potentiel est recalculé sans relire le CV.
    connecte.put(f"/postes/{dev}", json={**POSTE_DEV, "niveau_formation": "Doctorat"})
    services.traitement.traiter()
    score_apres = next(s for s in connecte.get(f"/candidatures/{c['id']}").json()["scores"] if s["poste_id"] == dev)
    assert {s["cle"]: s["note"] for s in score_apres["potentiel"]["signaux"]}["formation"] == 1


def test_le_potentiel_ne_change_pas_le_score(connecte, services, boite, tmp_path, monkeypatch):  # noqa: F811
    dev = creer_poste(connecte, POSTE_DEV)
    recevoir(boite, tmp_path, "Candidature DEV-2026-04", [("CV_Awa.pdf", fabrique.pdf_texte(fabrique.texte_cv("dev_python")))])
    services.traitement.traiter()
    avec = candidature_de(services, "CV_Awa.pdf")["score"]

    def en_panne(*args, **kwargs):
        raise RuntimeError("panne simulée")

    monkeypatch.setattr(potentiel, "evaluer", en_panne)
    connecte.put(f"/postes/{dev}", json={**POSTE_DEV, "description": POSTE_DEV["description"] + " "})
    services.traitement.traiter()
    c = candidature_de(services, "CV_Awa.pdf")
    assert c["score"] == avec  # même score, avec ou sans indicateur
    fiche = connecte.get(f"/candidatures/{c['id']}").json()
    assert next(s for s in fiche["scores"] if s["poste_id"] == dev)["potentiel"] is None
