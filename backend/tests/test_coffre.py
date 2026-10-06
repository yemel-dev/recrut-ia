"""Chiffrement des CV au repos : fichiers et texte extrait, avec la clé de données de la session."""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.services import coffre

from .conftest import EMAIL, MOT_DE_PASSE
from .test_traitement import POSTE_DEV, boite, candidature_de, creer_poste, cv_pdf, recevoir, services  # noqa: F401

CLE = bytes(range(32))
AUTRE_CLE = bytes(32)


# --- Module coffre ----------------------------------------------------------------------------------------


def test_fichier_chiffre_puis_relu(tmp_path):
    clair = tmp_path / "cv.pdf"
    clair.write_bytes(b"%PDF-1.4 contenu du CV")
    assert coffre.chiffrer_fichier(clair, CLE) is True
    assert not clair.exists()
    chiffre = coffre.chemin_chiffre(clair)
    assert chiffre.name == "cv.pdf.injara" and b"contenu du CV" not in chiffre.read_bytes()
    assert coffre.lire_fichier(clair, CLE) == b"%PDF-1.4 contenu du CV"
    assert coffre.chiffrer_fichier(clair, CLE) is False  # déjà fait


def test_fichier_en_clair_d_avant_le_chiffrement_reste_lisible(tmp_path):
    clair = tmp_path / "ancien.pdf"
    clair.write_bytes(b"ancien")
    assert coffre.lire_fichier(clair, CLE) == b"ancien"


def test_mauvaise_cle_ou_fichier_altere(tmp_path):
    clair = tmp_path / "cv.pdf"
    clair.write_bytes(b"secret")
    coffre.chiffrer_fichier(clair, CLE)
    with pytest.raises(coffre.Indechiffrable):
        coffre.lire_fichier(clair, AUTRE_CLE)
    chiffre = coffre.chemin_chiffre(clair)
    donnees = bytearray(chiffre.read_bytes())
    donnees[-1] ^= 1
    chiffre.write_bytes(bytes(donnees))
    with pytest.raises(coffre.Indechiffrable):
        coffre.lire_fichier(clair, CLE)


def test_fichier_absent(tmp_path):
    with pytest.raises(FileNotFoundError):
        coffre.lire_fichier(tmp_path / "absent.pdf", CLE)


def test_texte_chiffre_en_base():
    chiffre = coffre.chiffrer_texte("Awa Ndong, développeuse Python", CLE)
    assert chiffre.startswith(coffre.PREFIXE_TEXTE) and "Awa" not in chiffre
    assert coffre.chiffrer_texte(chiffre, CLE) == chiffre  # pas de double chiffrement
    assert coffre.dechiffrer_texte(chiffre, CLE) == "Awa Ndong, développeuse Python"
    assert coffre.dechiffrer_texte("texte d'avant", CLE) == "texte d'avant"
    assert coffre.chiffrer_texte(None, CLE) is None and coffre.dechiffrer_texte(None, CLE) is None


# --- Dans le pipeline ---------------------------------------------------------------------------------------


def test_le_pipeline_ne_laisse_aucun_cv_en_clair(connecte, services, boite, tmp_path):  # noqa: F811
    creer_poste(connecte, POSTE_DEV)
    pdf = cv_pdf("dev_python")
    recevoir(boite, tmp_path, "DEV-2026-04", [("CV_Awa.pdf", pdf), ("Lettre_motivation.pdf", cv_pdf("comptable"))])
    services.traitement.traiter()

    c = candidature_de(services, "CV_Awa.pdf")
    assert c["statut_lecture"] == "lue" and c["score"] == 100
    brute = services.candidatures.candidatures.get(c["id"])
    fichiers = [Path(brute["fichier_cv"]), *(Path(p["chemin"]) for p in brute["pieces_jointes"])]
    for fichier in fichiers:
        assert not fichier.exists(), f"{fichier.name} est resté en clair"
        assert coffre.chemin_chiffre(fichier).exists()
    assert brute["texte"].startswith(coffre.PREFIXE_TEXTE) and "Python" not in brute["texte"]
    assert brute["texte_lettre"].startswith(coffre.PREFIXE_TEXTE)

    reponse = connecte.get(f"/candidatures/{c['id']}/cv")
    assert reponse.status_code == 200
    assert reponse.content == pdf
    assert reponse.headers["x-injara-nom-fichier"] == "CV_Awa.pdf"


def test_donnees_d_avant_le_chiffrement_chiffrees_au_passage_suivant(connecte, services, boite, tmp_path):  # noqa: F811
    creer_poste(connecte, POSTE_DEV)
    recevoir(boite, tmp_path, "DEV-2026-04", [("CV_Awa.pdf", cv_pdf("dev_python"))])
    services.traitement.traiter()
    c = candidature_de(services, "CV_Awa.pdf")
    depot = services.candidatures.candidatures
    brute = depot.get(c["id"])
    cle = services.auth.cle_session()
    # Simule une base et un dossier remplis avant l'arrivée du chiffrement
    Path(brute["fichier_cv"]).write_bytes(coffre.lire_fichier(brute["fichier_cv"], cle))
    coffre.chemin_chiffre(brute["fichier_cv"]).unlink()
    depot.maj(c["id"], texte=coffre.dechiffrer_texte(brute["texte"], cle))

    services.traitement.traiter()
    brute = depot.get(c["id"])
    assert not Path(brute["fichier_cv"]).exists() and coffre.chemin_chiffre(brute["fichier_cv"]).exists()
    assert brute["texte"].startswith(coffre.PREFIXE_TEXTE)
    assert candidature_de(services, "CV_Awa.pdf")["score"] == 100


def test_cv_chiffre_endommage_signale_illisible(connecte, services, boite, tmp_path):  # noqa: F811
    recevoir(boite, tmp_path, "Candidature", [("CV_Awa.pdf", cv_pdf("dev_python"))])
    services.traitement.traiter()
    c = candidature_de(services, "CV_Awa.pdf")
    coffre.chemin_chiffre(services.candidatures.candidatures.get(c["id"])["fichier_cv"]).write_bytes(b"x" * 64)
    assert connecte.post(f"/candidatures/{c['id']}/relire").status_code == 200
    services.traitement.traiter()
    c = candidature_de(services, "CV_Awa.pdf")
    assert c["statut_lecture"] == "illisible"
    assert connecte.get(f"/candidatures/{c['id']}/cv").status_code == 400


def test_sans_session_rien_n_est_traite(connecte, services, boite, tmp_path):  # noqa: F811
    recevoir(boite, tmp_path, "Candidature", [("CV_Awa.pdf", cv_pdf("dev_python"))])
    connecte.post("/auth/deconnexion")
    assert services.traitement.traiter() == {}
    connecte.headers.pop("X-Injara-Session")
    jeton = connecte.post("/auth/connexion", json={"email": EMAIL, "mot_de_passe": MOT_DE_PASSE}).json()["jeton_session"]
    connecte.headers["X-Injara-Session"] = jeton
    services.traitement.traiter()
    assert candidature_de(services, "CV_Awa.pdf")["statut_lecture"] == "lue"


def test_fin_de_session_pendant_un_passage(connecte, services, boite, tmp_path):  # noqa: F811
    recevoir(boite, tmp_path, "Candidature", [("CV_Awa.pdf", cv_pdf("dev_python"))])
    traitement = services.traitement
    cle = traitement.cle
    appels = iter([cle(), None])  # la clé disparaît juste après le début du passage
    traitement.cle = lambda: next(appels, None)
    assert traitement.traiter() == {}
    assert traitement.derniere_erreur is None
