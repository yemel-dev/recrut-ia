"""Étapes 3 et 4 : compétences, score sur 100 et décision de classement (fonctions pures)."""
from __future__ import annotations

from datetime import date

import pytest

from backend.ia import classement, competences, scoring
from backend.ia.classement import PosteActif, SourceMail
from backend.ia.extraction import extraire
from backend.ia.scoring import DonneesCV, DonneesPoste

from .fixtures import fabrique

AUJOURDHUI = date(2026, 10, 1)

POSTE_DEV = DonneesPoste(
    competences=["Python", "Django REST Framework", "PostgreSQL", "Docker", "JavaScript", "Kubernetes"],
    experience_min_annees=3,
    niveau_formation="Master",
)
POSTE_COMPTABLE = DonneesPoste(
    competences=["Comptabilité générale", "SYSCOHADA", "Sage 100", "Excel", "Fiscalité"],
    experience_min_annees=5,
    niveau_formation="Licence",
)


def cv(nom: str) -> DonneesCV:
    texte = fabrique.texte_cv(nom)
    e = extraire(texte, AUJOURDHUI)
    return DonneesCV(texte=texte, experience_mois=e.experience_mois, diplome_niveau=e.diplome["niveau"], diplome_ligne=e.diplome["ligne"])


# --- Compétences ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("competence", "texte", "trouvee"),
    [
        ("Django REST Framework", "API avec django rest framework", True),
        ("Django REST Framework", "API avec Django et une couche REST", False),  # l'expression entière est exigée
        ("Django REST Framework", "API DRF", True),  # synonyme
        ("JavaScript", "React, JS, HTML", True),
        ("PostgreSQL", "bases Postgres", True),
        ("Node.js", "backend nodejs", True),
        ("Node.js", "backend node js", True),
        ("Java", "développeur JavaScript", False),
        ("C", "langages C++ et C#", False),
        ("C++", "langages C++ et C#", True),
        ("C#", "langages C++ et C#", True),
        (".NET", "salaire net mensuel", False),
        (".NET", "ASP.NET Core", True),
        ("Comptabilité générale", "COMPTABILITE GENERALE", True),
        ("Gestion de projet", "Project management (PMP)", True),
        ("Anglais", "Langues : English (courant)", True),
        ("Excel", "Microsoft Excel avancé", True),
    ],
)
def test_recherche_des_competences(competence, texte, trouvee):
    assert (competences.chercher(competence, competences.normaliser(texte)) is not None) is trouvee


def test_score_competences_part_des_requises():
    score, detail = scoring.score_competences("Python, Docker et JS", ["Python", "Docker", "JavaScript", "Go"])
    assert score == 0.75
    assert detail["manquantes"] == ["Go"]
    assert {t["competence"]: t["trouvee_sous"] for t in detail["trouvees"]}["JavaScript"] == "js"


# --- Expérience et formation -------------------------------------------------------------------------


@pytest.mark.parametrize(("mois", "requises", "attendu"), [(39, 3, 1.0), (18, 3, 0.5), (0, 2, 0.0), (0, 0, 1.0), (120, 2, 1.0)])
def test_score_experience_plafonne(mois, requises, attendu):
    assert scoring.score_experience(mois, requises)[0] == attendu


@pytest.mark.parametrize(
    ("niveau_cv", "requis", "attendu"),
    [("Master", "Master", 1.0), ("Doctorat", "Master", 1.0), ("Licence", "Master", 0.6), ("BTS", "Master", 0.2), ("Bac", "Master", 0.0), (None, "BTS", 0.0)],
)
def test_score_formation_degressif(niveau_cv, requis, attendu):
    assert scoring.score_formation(niveau_cv, None, requis)[0] == pytest.approx(attendu)


def test_diplome_non_trouve_est_explique():
    _, detail = scoring.score_formation(None, None, "Licence")
    assert "Aucun diplôme obtenu" in detail["message"]


# --- Score global -------------------------------------------------------------------------------------


def test_score_dev_python_sans_adequation():
    r = scoring.scorer(cv("dev_python"), POSTE_DEV)
    assert r.adequation_ignoree is True
    # compétences 5/6, expérience 39/36 mois → 100 %, Master = Master ; poids ramenés à 40/25/20 sur 85
    assert r.criteres["competences"]["score"] == pytest.approx(83.3, abs=0.1)
    assert r.criteres["experience"]["score"] == 100
    assert r.criteres["formation"]["score"] == 100
    assert r.criteres["adequation"]["score"] is None
    assert r.criteres["competences"]["poids"] == pytest.approx(40 * 100 / 85, abs=0.01)
    assert r.score == pytest.approx((5 / 6 * 40 + 25 + 20) * 100 / 85, abs=0.1)
    assert r.criteres["competences"]["detail"]["manquantes"] == ["Kubernetes"]


def test_score_avec_adequation():
    donnees = DonneesCV(texte="Python", experience_mois=0, diplome_niveau="Master", vecteur=[1.0, 0.0])
    poste = DonneesPoste(competences=["Python"], experience_min_annees=0, niveau_formation="Master", vecteur=[1.0, 0.0])
    r = scoring.scorer(donnees, poste)
    assert r.adequation_ignoree is False
    assert r.score == 100
    assert r.criteres["adequation"]["poids"] == 15


def test_adequation_ramenee_entre_plancher_et_plafond():
    assert scoring.score_adequation([1.0, 0.0], [0.0, 1.0])[0] == 0.0
    milieu = (scoring.SIMILARITE_PLANCHER + scoring.SIMILARITE_PLAFOND) / 2
    a, b = [1.0, 0.0], [milieu, (1 - milieu**2) ** 0.5]
    assert scoring.score_adequation(a, b)[0] == pytest.approx(0.5, abs=0.01)


def test_poids_personnalises():
    poste = DonneesPoste(POSTE_DEV.competences, 3, "Master", poids={"competences": 100, "experience": 0, "formation": 0, "adequation": 0})
    r = scoring.scorer(cv("dev_python"), poste)
    assert r.score == pytest.approx(83.3, abs=0.1)


def test_comptable_peu_pertinent_pour_un_poste_de_developpeur():
    r = scoring.scorer(cv("comptable"), POSTE_DEV)
    assert r.pertinence < classement.SEUIL_NON_CLASSE
    assert r.score > 30  # l'expérience et le diplôme gonflent le score : d'où le classement sur la pertinence


def test_scoring_ne_touche_ni_fichiers_ni_base(monkeypatch):
    import builtins

    def interdit(*args, **kwargs):
        raise AssertionError("le scoring ne doit pas ouvrir de fichier")

    monkeypatch.setattr(builtins, "open", interdit)
    scoring.scorer(DonneesCV("Python", 12, "Licence"), POSTE_DEV)


# --- Classement -----------------------------------------------------------------------------------------

DEV = PosteActif(1, "Développeur Python", "DEV-2026-04")
COMPTA = PosteActif(2, "Comptable", "FIN-07")
CHEF = PosteActif(3, "Chef de projet informatique")


def test_reference_dans_l_objet():
    d = classement.decider(SourceMail(objet="Candidature DEV-2026-04"), [DEV, COMPTA], {1: 0.0, 2: 90.0})
    assert (d.poste_id, d.statut, d.mode) == (1, "classe", "reference")
    assert "objet" in d.motif


def test_intitule_dans_le_corps():
    d = classement.decider(SourceMail(objet="CV", corps="Je postule au poste de comptable."), [DEV, COMPTA], {1: 80.0, 2: 10.0})
    assert (d.poste_id, d.mode) == (2, "reference")


def test_intitule_dans_la_lettre():
    d = classement.decider(SourceMail(lettre="Objet : candidature au poste de Chef de projet informatique"), [DEV, CHEF], {})
    assert d.poste_id == 3


def test_mail_sans_reference_assignation_automatique():
    d = classement.decider(SourceMail(objet="Candidature spontanée", corps="Bonjour, veuillez trouver mon CV."), [DEV, COMPTA], {1: 75.0, 2: 5.0})
    assert (d.poste_id, d.statut, d.mode) == (1, "classe", "automatique")


def test_pertinence_faible_a_verifier():
    d = classement.decider(SourceMail(), [DEV, COMPTA], {1: 30.0, 2: 5.0})
    assert (d.poste_id, d.statut) == (1, "a_verifier")


def test_postes_trop_proches_a_verifier():
    d = classement.decider(SourceMail(), [DEV, CHEF], {1: 62.0, 3: 58.0})
    assert (d.poste_id, d.statut) == (1, "a_verifier")
    assert "deux postes" in d.motif


def test_rien_ne_correspond_non_classe():
    d = classement.decider(SourceMail(), [DEV], {1: 5.0})
    assert (d.poste_id, d.statut) == (None, "non_classe")


def test_aucun_poste_actif():
    assert classement.decider(SourceMail(objet="DEV-2026-04"), [], {}).statut == "non_classe"


def test_reference_trop_courte_ignoree():
    poste = PosteActif(9, "Assistant administratif", "A1")
    d = classement.decider(SourceMail(objet="Candidature A1 B2"), [poste], {9: 0.0})
    assert d.mode != "reference"


def test_intitule_le_plus_long_l_emporte():
    junior = PosteActif(4, "Comptable")
    senior = PosteActif(5, "Comptable senior")
    d = classement.decider(SourceMail(objet="Candidature comptable senior"), [junior, senior], {})
    assert (d.poste_id, d.statut) == (5, "classe")


def test_comptable_non_classe_parmi_des_postes_techniques():
    resultat = scoring.scorer(cv("comptable"), POSTE_DEV)
    d = classement.decider(SourceMail(objet="Candidature"), [DEV], {DEV.id: resultat.pertinence})
    assert d.statut == "non_classe"


def test_comptable_classe_sur_le_poste_comptable():
    pertinences = {DEV.id: scoring.scorer(cv("comptable"), POSTE_DEV).pertinence, COMPTA.id: scoring.scorer(cv("comptable"), POSTE_COMPTABLE).pertinence}
    d = classement.decider(SourceMail(objet="Candidature spontanée"), [DEV, COMPTA], pertinences)
    assert (d.poste_id, d.statut) == (COMPTA.id, "classe")
