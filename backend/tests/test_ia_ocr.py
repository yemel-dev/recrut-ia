"""CV scannés : reconnaissance de caractères (RapidOCR), et repli « illisible » quand elle manque."""
from __future__ import annotations

from datetime import date

import pytest

from backend.ia import lecture
from backend.ia.extraction import extraire
from backend.ia.ocr import MoteurOCR

from .fixtures import fabrique
from .test_traitement import POSTE_COMPTABLE, boite, candidature_de, creer_poste, recevoir, services  # noqa: F401

pytest.importorskip("rapidocr")
pytest.importorskip("pypdfium2")
pytestmark = pytest.mark.skipif(fabrique.police_avec_accents() is None, reason="aucune police avec accents pour fabriquer le scan")

AUJOURDHUI = date(2026, 10, 1)


@pytest.fixture(scope="module")
def ocr():
    moteur = MoteurOCR()
    assert moteur.disponible, moteur.motif_indisponible
    return moteur


@pytest.fixture(scope="module")
def scan_comptable() -> bytes:
    return fabrique.pdf_scanne_texte(fabrique.texte_cv("comptable"))


class _OCRIndisponible:
    disponible = False
    motif_indisponible = "essai"


def test_cv_scanne_lu_par_ocr(ocr, scan_comptable):
    lu = lecture.lire("CV_scanne.pdf", scan_comptable, ocr=ocr)
    assert lu.par_ocr is True
    assert "Présent" in lu.texte and "SYSCOHADA" in lu.texte  # accents compris

    depuis_scan = extraire(lu.texte, AUJOURDHUI)
    original = extraire(fabrique.texte_cv("comptable"), AUJOURDHUI)
    assert (depuis_scan.nom, depuis_scan.email, depuis_scan.telephone) == (original.nom, original.email, original.telephone)
    assert depuis_scan.experience_mois == original.experience_mois
    assert depuis_scan.diplome["niveau"] == original.diplome["niveau"] == "Master"


def test_pdf_texte_ne_passe_pas_par_l_ocr(ocr):
    lu = lecture.lire("cv.pdf", fabrique.pdf_texte(fabrique.texte_cv("comptable")), ocr=ocr)
    assert lu.par_ocr is False


def test_scan_sans_ocr_reste_illisible(scan_comptable):
    with pytest.raises(lecture.FichierIllisible) as exc:
        lecture.lire("cv.pdf", scan_comptable)
    assert exc.value.motif.startswith(lecture.MOTIF_SCAN_SANS_OCR)

    with pytest.raises(lecture.FichierIllisible) as exc:
        lecture.lire("cv.pdf", scan_comptable, ocr=_OCRIndisponible())
    assert exc.value.motif.startswith(lecture.MOTIF_SCAN_SANS_OCR) and "indisponible (essai)" in exc.value.motif


def test_image_sans_texte_illisible_meme_avec_ocr(ocr):
    with pytest.raises(lecture.FichierIllisible) as exc:
        lecture.lire("cv.pdf", fabrique.pdf_scanne(), ocr=ocr)
    assert "presque rien pu lire" in exc.value.motif


def test_pdf_endommage_ne_casse_pas_l_ocr(ocr):
    assert ocr.lire_pdf(b"%PDF-1.4 tronque", "abime.pdf") == ""


# --- Dans le pipeline ---------------------------------------------------------------------------------------


def test_scan_classe_et_signale_au_recruteur(connecte, services, boite, tmp_path, ocr, scan_comptable):  # noqa: F811
    services.traitement.ocr = ocr
    compta = creer_poste(connecte, POSTE_COMPTABLE)
    recevoir(boite, tmp_path, "Candidature", [("CV_Nadege.pdf", scan_comptable)])
    services.traitement.traiter()
    c = candidature_de(services, "CV_Nadege.pdf")
    assert c["statut_lecture"] == "lue"
    assert c["poste_id"] == compta and c["score"] is not None
    fiche = connecte.get(f"/candidatures/{c['id']}").json()
    assert fiche["motif_lecture"] == lecture.MOTIF_LU_PAR_OCR


def test_scans_illisibles_relus_quand_l_ocr_arrive(connecte, services, boite, tmp_path, ocr, scan_comptable):  # noqa: F811
    services.traitement.ocr = _OCRIndisponible()
    recevoir(boite, tmp_path, "Candidature", [("CV_Nadege.pdf", scan_comptable)])
    services.traitement.traiter()
    assert candidature_de(services, "CV_Nadege.pdf")["statut_lecture"] == "illisible"

    services.traitement.ocr = ocr
    services.traitement.traiter()
    c = candidature_de(services, "CV_Nadege.pdf")
    assert c["statut_lecture"] == "lue" and c["nom"] == "Nadège Tchinda"
