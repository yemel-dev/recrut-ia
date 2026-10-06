"""Étapes 1 et 2 : lecture et extraction des CV (sans poste)."""
from __future__ import annotations

from datetime import date

import pytest

from backend.ia import diplomes
from backend.ia.extraction import extraire
from backend.ia.lecture import FichierIllisible, lire_texte
from backend.ia.texte import normaliser

from .fixtures import fabrique

AUJOURDHUI = date(2026, 10, 1)


def extraction(nom: str, tmp_path, format_: str = "pdf"):
    texte = fabrique.texte_cv(nom)
    contenu = fabrique.pdf_texte(texte) if format_ == "pdf" else fabrique.docx(texte, dans_un_tableau=format_ == "docx-tableau")
    chemin = fabrique.ecrire(tmp_path, f"{nom}.{'pdf' if format_ == 'pdf' else 'docx'}", contenu)
    return extraire(lire_texte(chemin), AUJOURDHUI)


# --- Étape 1 : lecture ---------------------------------------------------------------------


def test_pdf_scanne_illisible(tmp_path):
    chemin = fabrique.ecrire(tmp_path, "scan.pdf", fabrique.pdf_scanne())
    with pytest.raises(FichierIllisible, match="scanné"):
        lire_texte(chemin)


@pytest.mark.parametrize(
    ("nom", "contenu", "extrait"),
    [
        ("vide.pdf", b"", "endommagé"),
        ("faux.pdf", b"%PDF-1.4 pas vraiment un pdf", "endommagé"),
        ("faux.docx", b"PK pas un docx", "endommagé"),
        ("cv.odt", b"x", "Format non pris en charge"),
    ],
)
def test_fichiers_illisibles(tmp_path, nom, contenu, extrait):
    with pytest.raises(FichierIllisible, match=extrait):
        lire_texte(fabrique.ecrire(tmp_path, nom, contenu))


def test_fichier_absent(tmp_path):
    with pytest.raises(FichierIllisible, match="introuvable"):
        lire_texte(tmp_path / "absent.pdf")


def test_docx_presque_vide(tmp_path):
    with pytest.raises(FichierIllisible, match="presque pas de texte"):
        lire_texte(fabrique.ecrire(tmp_path, "court.docx", fabrique.docx("Awa Ndong\nCV")))


@pytest.mark.parametrize("format_", ["pdf", "docx", "docx-tableau"])
def test_meme_resultat_quel_que_soit_le_format(tmp_path, format_):
    e = extraction("dev_python", tmp_path, format_)
    assert e.experience_mois == 39
    assert e.diplome["niveau"] == "Master"


# --- Contact ------------------------------------------------------------------------------------


def test_contact(tmp_path):
    e = extraction("dev_python", tmp_path)
    assert (e.nom, e.email, e.telephone) == ("Awa Ndong", "awa.ndong@example.cm", "+237 6 99 12 34 56")
    e = extraction("scrum_master", tmp_path)
    assert e.nom == "Jean-Paul Fotso"
    assert extraction("comptable", tmp_path).telephone == "+237 655 44 33 22"


def test_sections(tmp_path):
    e = extraction("dev_python", tmp_path)
    assert {"experience", "formation", "competences", "langues"} <= set(e.sections)
    assert "Master en Génie Logiciel" in e.sections["formation"]
    assert "Orange Digital Center" in e.sections["experience"]


# --- Périodes d'expérience ------------------------------------------------------------------------


def test_periodes_present_et_mois(tmp_path):
    """« Février 2025 – Présent » (21 mois au 1er octobre 2026) + « Septembre 2021 – Février 2023 » (18 mois)."""
    e = extraction("dev_python", tmp_path)
    emplois = [(p["debut"], p["fin"], p["mois"], p["en_cours"]) for p in e.periodes if not p["stage"]]
    assert emplois == [("2025-02", "2026-10", 21, True), ("2021-09", "2023-02", 18, False)]
    assert e.experience_mois == 39


def test_dates_d_etudes_non_comptees(tmp_path):
    """Les années de formation (2016 – 2021) ne sont jamais de l'expérience."""
    e = extraction("dev_python", tmp_path)
    assert all(not p["debut"].startswith(("2016", "2019")) for p in e.periodes)


def test_stages_comptes_a_part(tmp_path):
    e = extraction("dev_python", tmp_path)
    assert e.stages_mois == 3
    jeune = extraction("jeune_diplome", tmp_path)
    assert (jeune.experience_mois, jeune.stages_mois) == (0, 6)  # titre de section « Stages »


def test_a_ce_jour_et_format_numerique(tmp_path):
    e = extraction("scrum_master", tmp_path)
    assert e.experience_mois == 36 + 46  # 01/2020-12/2022 et 01/2023 - à ce jour


@pytest.mark.parametrize(
    ("ligne", "attendu"),
    [
        ("Sept. 2021 à février 2023", 18),
        ("de mars 2019 au 31 décembre", None),  # fin illisible : rien n'est inventé
        ("depuis janvier 2026", 10),
        ("2019 - 2021", 25),  # années seules : de juin à juin
        ("Janvier 2024 - Décembre 2030", 34),  # fin future : arrêtée à aujourd'hui
        ("Since June 2025", 17),
    ],
)
def test_formats_de_periode(ligne, attendu):
    e = extraire(f"EXPÉRIENCE\nPoste de test\n{ligne}\n", AUJOURDHUI)
    assert (e.experience_mois or None) == attendu


def test_periodes_qui_se_chevauchent_fusionnees():
    texte = "EXPÉRIENCE\nComptable — A\nJanvier 2020 - Décembre 2021\nConsultante — B\nJuin 2021 - Juin 2022\n"
    assert extraire(texte, AUJOURDHUI).experience_mois == 30  # janvier 2020 → juin 2022


def test_alternance_compte_comme_experience():
    texte = "EXPÉRIENCE\nComptable en alternance — Cabinet X\nSeptembre 2023 - Août 2024\n"
    e = extraire(texte, AUJOURDHUI)
    assert (e.experience_mois, e.stages_mois) == (12, 0)


def test_cv_sans_sections_ecarte_les_dates_d_etudes():
    texte = "Awa Ndong\nUniversité de Douala, Master informatique, 2019 - 2021\nDéveloppeuse chez Orange, Mars 2022 - Février 2023\n"
    e = extraire(texte, AUJOURDHUI)
    assert e.experience_mois == 12
    assert e.section_experience_trouvee is False


# --- Diplôme ---------------------------------------------------------------------------------------


def test_bac_plus_5_est_un_master(tmp_path):
    e = extraction("comptable", tmp_path)
    assert e.diplome["niveau"] == "Master"
    assert "Bac+5" in e.diplome["ligne"]


def test_scrum_master_et_master_en_cours_ignores(tmp_path):
    e = extraction("scrum_master", tmp_path)
    assert e.diplome["niveau"] == "Licence"
    assert e.diplome["ignores"][0]["raison"] == "en cours"


def test_diplome_lu_dans_la_section_formation_uniquement():
    texte = "EXPÉRIENCE\nEnseignante de Master — Université X\nJanvier 2020 - Janvier 2021\nFORMATION\nBTS Comptabilité, 2018\n"
    assert extraire(texte, AUJOURDHUI).diplome["niveau"] == "BTS"


def test_ingenieur_de_conception(tmp_path):
    assert extraction("jeune_diplome", tmp_path).diplome["niveau"] == "Master"


@pytest.mark.parametrize(
    ("ligne", "niveau"),
    [
        ("Bac+5 en finance", 3),
        ("Bac + 3 en gestion", 2),
        ("Bachelor in Computer Science", 2),
        ("Diplôme d'ingénieur des travaux", 2),  # Bac+3 au Cameroun
        ("DUT Génie électrique", 1),
        ("HND in Accounting", 1),
        ("Doctorat en économie", 4),
        ("Baccalauréat série C", 0),
        ("Certification Professional Scrum Master", None),
        ("Masterclass Excel", None),
        ("MBA", 3),
    ],
)
def test_correspondance_des_diplomes(ligne, niveau):
    assert diplomes.niveau_dans_ligne(normaliser(ligne)) == niveau


def test_diplome_dont_la_fin_est_future_non_obtenu():
    texte = "FORMATION\nMaster en Data Science — Université X\nSeptembre 2025 - Juillet 2027\nLicence en mathématiques, 2024\n"
    assert extraire(texte, AUJOURDHUI).diplome["niveau"] == "Licence"


def test_aucun_diplome():
    e = extraire("EXPÉRIENCE\nVendeur\nJanvier 2020 - Janvier 2021\n", AUJOURDHUI)
    assert e.diplome["niveau"] is None
