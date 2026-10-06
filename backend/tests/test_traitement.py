"""Pipeline complet : mails reçus par l'agent → lecture → extraction → score → classement → top 10."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.ia import semantique

from .conftest import EMAIL, JETON, MOT_DE_PASSE
from .fixtures import fabrique

POSTE_DEV = {
    "intitule": "Développeur Python",
    "reference_interne": "DEV-2026-04",
    "description": "Développement d'API web en Python pour nos clients bancaires.",
    "competences_requises": ["Python", "Django REST Framework", "PostgreSQL", "Docker", "JavaScript"],
    "experience_min_annees": 3,
    "niveau_formation": "Master",
    "statut": "actif",
}
POSTE_COMPTABLE = {
    "intitule": "Comptable principal",
    "description": "Tenue de la comptabilité générale et déclarations fiscales.",
    "competences_requises": ["Comptabilité générale", "SYSCOHADA", "Sage 100", "Excel", "Fiscalité"],
    "experience_min_annees": 5,
    "niveau_formation": "Licence",
    "statut": "actif",
}


@pytest.fixture
def services(app):
    return app.state.services


@pytest.fixture
def boite(services, connecte):
    """La boîte de démonstration de l'agent, vidée de ses CV d'exemple."""
    agent = services.agent_mail.agent()
    agent.client._messages.clear()
    services.traitement.aujourdhui = lambda: date(2026, 10, 1)
    return agent


def recevoir(agent, tmp_path, objet: str, pieces: list[tuple[str, bytes]], corps: str = "", expediteur: str = "Candidat <c@example.cm>"):
    agent.client.add_message(expediteur, objet, pieces, body=corps)
    agent.sync_once()


def cv_pdf(nom: str) -> bytes:
    return fabrique.pdf_texte(fabrique.texte_cv(nom))


def candidature_de(services, nom_fichier: str) -> dict:
    elements = services.candidatures.lister(limite=200)["elements"]
    return next(e for e in elements if e["nom_fichier_cv"] == nom_fichier)


def creer_poste(client, donnees) -> int:
    reponse = client.post("/postes", json=donnees)
    assert reponse.status_code == 201, reponse.text
    return reponse.json()["id"]


# --- Classement ----------------------------------------------------------------------------------


def test_reference_dans_l_objet_assignation_directe(connecte, services, boite, tmp_path):
    dev = creer_poste(connecte, POSTE_DEV)
    creer_poste(connecte, POSTE_COMPTABLE)
    recevoir(boite, tmp_path, "Candidature DEV-2026-04", [("CV_Awa.pdf", cv_pdf("dev_python"))])
    services.traitement.traiter()

    c = candidature_de(services, "CV_Awa.pdf")
    assert (c["poste_id"], c["statut_classement"], c["mode_assignation"]) == (dev, "classe", "reference")
    assert "objet du mail" in c["motif_classement"]
    assert c["nom"] == "Awa Ndong" and c["experience_mois"] == 39 and c["diplome_niveau"] == "Master"


def test_mail_sans_reference_classe_automatiquement(connecte, services, boite, tmp_path):
    creer_poste(connecte, POSTE_DEV)
    compta = creer_poste(connecte, POSTE_COMPTABLE)
    recevoir(boite, tmp_path, "Candidature spontanée", [("CV_Nadege.pdf", cv_pdf("comptable"))], corps="Bonjour, voici mon CV.")
    services.traitement.traiter()
    c = candidature_de(services, "CV_Nadege.pdf")
    assert (c["poste_id"], c["statut_classement"], c["mode_assignation"]) == (compta, "classe", "automatique")


def test_cv_sans_rapport_non_classe(connecte, services, boite, tmp_path):
    creer_poste(connecte, POSTE_DEV)
    recevoir(boite, tmp_path, "CV", [("CV_Nadege.pdf", cv_pdf("comptable"))])
    services.traitement.traiter()
    c = candidature_de(services, "CV_Nadege.pdf")
    assert (c["poste_id"], c["statut_classement"]) == (None, "non_classe")
    assert c["statut_lecture"] == "lue"  # elle reste visible : rien n'est masqué


def test_intitule_dans_le_corps_du_mail(connecte, services, boite, tmp_path):
    compta = creer_poste(connecte, POSTE_COMPTABLE)
    creer_poste(connecte, POSTE_DEV)
    recevoir(boite, tmp_path, "Candidature", [("cv.pdf", cv_pdf("dev_python"))], corps="Je postule au poste de Comptable principal.")
    services.traitement.traiter()
    c = candidature_de(services, "cv.pdf")
    assert (c["poste_id"], c["mode_assignation"]) == (compta, "reference")


def test_lettre_de_motivation_jointe(connecte, services, boite, tmp_path):
    """Le CV principal est choisi d'après le nom ; la lettre sert à repérer le poste."""
    compta = creer_poste(connecte, POSTE_COMPTABLE)
    lettre = fabrique.pdf_texte("Lettre de motivation\n" + "Je souhaite rejoindre votre équipe au poste de Comptable principal. " * 5)
    recevoir(boite, tmp_path, "Candidature", [("Lettre_motivation.pdf", lettre), ("CV_Nadege.pdf", cv_pdf("comptable"))])
    services.traitement.traiter()
    elements = services.candidatures.lister()["elements"]
    assert len(elements) == 1  # une candidature par mail
    assert elements[0]["nom_fichier_cv"] == "CV_Nadege.pdf"
    assert (elements[0]["poste_id"], elements[0]["mode_assignation"]) == (compta, "reference")
    assert "lettre de motivation" in elements[0]["motif_classement"]


def test_aucun_poste_actif(connecte, services, boite, tmp_path):
    recevoir(boite, tmp_path, "CV", [("cv.pdf", cv_pdf("dev_python"))])
    services.traitement.traiter()
    c = candidature_de(services, "cv.pdf")
    assert c["statut_classement"] == "non_classe" and "Aucun poste actif" in c["motif_classement"]


def test_poste_brouillon_ignore(connecte, services, boite, tmp_path):
    creer_poste(connecte, {**POSTE_DEV, "statut": "brouillon"})
    recevoir(boite, tmp_path, "DEV-2026-04", [("cv.pdf", cv_pdf("dev_python"))])
    services.traitement.traiter()
    assert candidature_de(services, "cv.pdf")["poste_id"] is None


# --- Lecture ----------------------------------------------------------------------------------------


def test_pdf_scanne_signale(connecte, services, boite, tmp_path):
    creer_poste(connecte, POSTE_DEV)
    recevoir(boite, tmp_path, "CV", [("CV_scan.pdf", fabrique.pdf_scanne())])
    services.traitement.traiter()
    c = candidature_de(services, "CV_scan.pdf")
    assert c["statut_lecture"] == "illisible"
    assert "scanné" in c["motif_lecture"]
    assert c["score"] is None  # jamais 0 en silence
    reponse = connecte.get("/candidatures?lecture=illisible").json()
    assert reponse["total"] == 1 and reponse["compteurs"]["illisibles"] == 1


# --- Score et détail ------------------------------------------------------------------------------------


def test_score_et_detail_enregistres(connecte, services, boite, tmp_path):
    dev = creer_poste(connecte, POSTE_DEV)
    recevoir(boite, tmp_path, "DEV-2026-04", [("cv.pdf", cv_pdf("dev_python"))])
    services.traitement.traiter()
    c = candidature_de(services, "cv.pdf")
    fiche = connecte.get(f"/candidatures/{c['id']}").json()
    assert fiche["poste_intitule"] == "Développeur Python"
    score = next(s for s in fiche["scores"] if s["poste_id"] == dev)
    criteres = score["detail"]["criteres"]
    assert criteres["competences"]["score"] == 100
    assert [t["competence"] for t in criteres["competences"]["detail"]["trouvees"]] == POSTE_DEV["competences_requises"]
    assert criteres["experience"]["detail"]["experience_retenue_mois"] == 39
    assert criteres["formation"]["detail"]["diplome_retenu"] == "Master"
    assert score["adequation_ignoree"] is True
    assert fiche["score"] == score["score"] == 100


def test_adequation_avec_un_modele(settings, tmp_path):
    """Avec un modèle (ici factice), l'adéquation compte dans le score."""

    class ModeleFactice(semantique.ModeleSemantique):
        disponible = True
        nom = "factice"

        def encoder(self, texte):
            mots = texte.lower()
            return semantique.normaliser_vecteur([mots.count("python") + 0.1, mots.count("comptab") + 0.1])

    app = create_app(settings, modele=ModeleFactice())
    try:
        client = TestClient(app, headers={"X-Injara-Token": JETON})
        client.post("/auth/compte", json={"email": EMAIL, "mot_de_passe": MOT_DE_PASSE})
        client.headers["X-Injara-Session"] = client.post("/auth/connexion", json={"email": EMAIL, "mot_de_passe": MOT_DE_PASSE}).json()["jeton_session"]
        services = app.state.services
        agent = services.agent_mail.agent()
        agent.client._messages.clear()
        dev = creer_poste(client, POSTE_DEV)
        recevoir(agent, tmp_path, "DEV-2026-04", [("cv.pdf", cv_pdf("dev_python"))])
        services.traitement.traiter()
        c = candidature_de(services, "cv.pdf")
        score = next(s for s in client.get(f"/candidatures/{c['id']}").json()["scores"] if s["poste_id"] == dev)
        assert score["adequation_ignoree"] is False
        assert score["detail"]["criteres"]["adequation"]["poids"] == 15
        assert client.get("/traitement/etat").json()["adequation"]["disponible"] is True
    finally:
        app.state.services.traitement.arreter()
        app.state.db.close()


def test_modele_absent_signale(connecte):
    etat = connecte.get("/traitement/etat").json()
    assert etat["adequation"]["disponible"] is False
    assert "absent" in etat["adequation"]["motif"]


# --- Choix manuel et renotation ---------------------------------------------------------------------------


def test_choix_manuel_jamais_ecrase(connecte, services, boite, tmp_path):
    dev = creer_poste(connecte, POSTE_DEV)
    compta = creer_poste(connecte, {**POSTE_COMPTABLE, "statut": "cloture"})
    recevoir(boite, tmp_path, "DEV-2026-04", [("cv.pdf", cv_pdf("dev_python"))])
    services.traitement.traiter()
    c = candidature_de(services, "cv.pdf")

    fiche = connecte.put(f"/candidatures/{c['id']}/poste", json={"poste_id": compta}).json()
    assert (fiche["poste_id"], fiche["mode_assignation"], fiche["statut_classement"]) == (compta, "manuel", "classe")
    assert fiche["score"] is not None  # noté pour ce poste, même clôturé

    connecte.put(f"/postes/{dev}", json={**POSTE_DEV, "description": "Nouvelle description"})
    services.traitement.traiter()
    assert candidature_de(services, "cv.pdf")["poste_id"] == compta

    fiche = connecte.post(f"/candidatures/{c['id']}/automatique").json()
    assert (fiche["poste_id"], fiche["mode_assignation"]) == (dev, "reference")


def test_retirer_de_tout_poste(connecte, services, boite, tmp_path):
    creer_poste(connecte, POSTE_DEV)
    recevoir(boite, tmp_path, "DEV-2026-04", [("cv.pdf", cv_pdf("dev_python"))])
    services.traitement.traiter()
    c = candidature_de(services, "cv.pdf")
    fiche = connecte.put(f"/candidatures/{c['id']}/poste", json={"poste_id": None}).json()
    assert (fiche["poste_id"], fiche["statut_classement"], fiche["mode_assignation"]) == (None, "non_classe", "manuel")


def test_poste_modifie_renote_sans_relire_les_cv(connecte, services, boite, tmp_path):
    dev = creer_poste(connecte, POSTE_DEV)
    recevoir(boite, tmp_path, "DEV-2026-04", [("cv.pdf", cv_pdf("dev_python"))])
    services.traitement.traiter()
    c = candidature_de(services, "cv.pdf")
    assert c["score"] == 100

    Path(services.candidatures.candidatures.get(c["id"])["fichier_cv"]).unlink()  # le fichier n'est plus là
    connecte.put(f"/postes/{dev}", json={**POSTE_DEV, "competences_requises": ["Python", "Kubernetes"]})
    services.traitement.traiter()
    c = candidature_de(services, "cv.pdf")
    assert c["statut_lecture"] == "lue"
    assert c["score"] < 100  # renoté : Kubernetes manque


def test_poste_supprime_libere_ses_candidatures(connecte, services, boite, tmp_path):
    dev = creer_poste(connecte, POSTE_DEV)
    recevoir(boite, tmp_path, "DEV-2026-04", [("cv.pdf", cv_pdf("dev_python"))])
    services.traitement.traiter()
    c = candidature_de(services, "cv.pdf")
    connecte.put(f"/candidatures/{c['id']}/poste", json={"poste_id": dev})
    connecte.delete(f"/postes/{dev}")
    services.traitement.traiter()
    c = candidature_de(services, "cv.pdf")
    assert (c["poste_id"], c["statut_classement"]) == (None, "non_classe")


# --- Top 10 ---------------------------------------------------------------------------------------------


def test_top_10_trie_par_score(connecte, services, boite, tmp_path):
    dev = creer_poste(connecte, POSTE_DEV)
    texte = fabrique.texte_cv("dev_python")
    competences = ["Django REST Framework", "Postgres", "Docker", "JS"]
    for i in range(12):
        # CV de plus en plus pauvres : on retire des compétences
        variante = texte
        for competence in competences[: i % 5]:
            variante = variante.replace(competence, "")
        variante = variante.replace("Awa NDONG", f"Candidat Numero{chr(65 + i)}")
        recevoir(boite, tmp_path, "DEV-2026-04", [(f"cv{i:02d}.pdf", fabrique.pdf_texte(variante))], expediteur=f"C{i} <c{i}@example.cm>")
    services.traitement.traiter()

    top = connecte.get(f"/postes/{dev}/classement").json()
    assert top["total_rattachees"] == 12
    assert len(top["elements"]) == 10
    scores = [e["score"] for e in top["elements"]]
    assert scores == sorted(scores, reverse=True)
    premier = top["elements"][0]
    assert premier["detail"]["criteres"]["competences"]["score"] == 100
    assert {"competences", "experience", "formation", "adequation"} == set(premier["detail"]["criteres"])


def test_poids_du_poste_valides(connecte):
    reponse = connecte.post("/postes", json={**POSTE_DEV, "poids_competences": 50})
    assert reponse.status_code == 422
    assert "100" in reponse.json()["champs"]["poids"]
    poste = connecte.post("/postes", json={**POSTE_DEV, "poids_competences": 55, "poids_adequation": 0}).json()
    assert (poste["poids_competences"], poste["poids_adequation"]) == (55, 0)


def test_routes_exigent_une_session(client, cle_recuperation):
    for chemin in ("/candidatures", "/candidatures/1", "/postes/1/classement", "/traitement/etat"):
        assert client.get(chemin).status_code == 401
