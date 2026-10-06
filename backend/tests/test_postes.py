from __future__ import annotations

import pytest

POSTE = {
    "intitule": "Développeur Python",
    "description": "Développer et maintenir les services internes.",
    "competences_requises": ["Python", "SQL", "FastAPI"],
    "experience_min_annees": 2,
    "niveau_formation": "Licence",
}


def creer(client, **changements):
    reponse = client.post("/postes", json={**POSTE, **changements})
    assert reponse.status_code == 201, reponse.text
    return reponse.json()


# --- Accès ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("methode", "chemin"),
    [
        ("get", "/postes"),
        ("post", "/postes"),
        ("get", "/postes/1"),
        ("put", "/postes/1"),
        ("put", "/postes/1/statut"),
        ("delete", "/postes/1"),
        ("get", "/entreprise"),
        ("put", "/entreprise"),
        ("get", "/tableau-de-bord"),
    ],
)
def test_routes_inaccessibles_sans_session(client, cle_recuperation, methode, chemin):
    reponse = getattr(client, methode)(chemin)
    assert reponse.status_code == 401
    assert reponse.json()["detail"] == "Vous devez être connecté."


def test_routes_inaccessibles_apres_deconnexion(connecte):
    creer(connecte)
    connecte.post("/auth/deconnexion")
    assert connecte.get("/postes").status_code == 401


# --- CRUD ---------------------------------------------------------------------------


def test_liste_vide_au_depart(connecte):
    assert connecte.get("/postes").json() == []


def test_creer_puis_consulter(connecte):
    poste = creer(connecte)
    assert poste["statut"] == "brouillon"  # statut par défaut
    assert poste["competences_requises"] == ["Python", "SQL", "FastAPI"]
    assert poste["type_contrat"] is None
    assert connecte.get(f"/postes/{poste['id']}").json() == poste


def test_creer_avec_tous_les_champs_facultatifs(connecte):
    poste = creer(
        connecte,
        reference_interne="DEV-2026-04",
        departement="Informatique",
        lieu="Douala",
        teletravail="hybride",
        type_contrat="CDD",
        duree="12 mois",
        date_limite="2026-12-31",
        competences_comportementales=["Rigueur", "Esprit d'équipe"],
        langues=["Français", "Anglais"],
        remuneration="Selon profil",
        processus_selection="Tri des CV, entretien technique, entretien RH.",
        documents_demandes=["CV", "Lettre de motivation"],
        statut="actif",
    )
    assert poste["date_limite"] == "2026-12-31"
    assert poste["teletravail"] == "hybride"
    assert poste["langues"] == ["Français", "Anglais"]
    assert poste["statut"] == "actif"


def test_listes_nettoyees(connecte):
    poste = creer(connecte, competences_requises=[" Python ", "", "python", "SQL"])
    assert poste["competences_requises"] == ["Python", "SQL"]


def test_modifier(connecte):
    poste = creer(connecte)
    reponse = connecte.put(f"/postes/{poste['id']}", json={**POSTE, "intitule": "Développeur Python senior", "experience_min_annees": 5})
    assert reponse.status_code == 200
    assert reponse.json()["intitule"] == "Développeur Python senior"
    assert connecte.get(f"/postes/{poste['id']}").json()["experience_min_annees"] == 5


def test_modifier_conserve_le_statut_si_fourni(connecte):
    poste = creer(connecte, statut="actif")
    reponse = connecte.put(f"/postes/{poste['id']}", json={**POSTE, "statut": "actif", "lieu": "Yaoundé"})
    assert reponse.json()["statut"] == "actif"


def test_supprimer(connecte):
    poste = creer(connecte)
    assert connecte.delete(f"/postes/{poste['id']}").status_code == 204
    assert connecte.get(f"/postes/{poste['id']}").status_code == 404
    assert connecte.delete(f"/postes/{poste['id']}").status_code == 404


def test_poste_inexistant(connecte):
    assert connecte.get("/postes/999").status_code == 404
    assert connecte.put("/postes/999", json=POSTE).status_code == 404
    assert connecte.put("/postes/999/statut", json={"statut": "actif"}).status_code == 404


# --- Statuts ------------------------------------------------------------------------


def test_changer_statut_et_filtrer(connecte):
    a = creer(connecte, intitule="A")
    b = creer(connecte, intitule="B")
    creer(connecte, intitule="C")
    connecte.put(f"/postes/{a['id']}/statut", json={"statut": "actif"})
    connecte.put(f"/postes/{b['id']}/statut", json={"statut": "cloture"})

    assert [p["intitule"] for p in connecte.get("/postes?statut=actif").json()] == ["A"]
    assert [p["intitule"] for p in connecte.get("/postes?statut=cloture").json()] == ["B"]
    assert [p["intitule"] for p in connecte.get("/postes?statut=brouillon").json()] == ["C"]
    assert len(connecte.get("/postes").json()) == 3


def test_statut_inconnu(connecte):
    poste = creer(connecte)
    assert connecte.put(f"/postes/{poste['id']}/statut", json={"statut": "archive"}).status_code == 422
    assert connecte.get("/postes?statut=archive").status_code == 422
    assert connecte.post("/postes", json={**POSTE, "statut": "publie"}).status_code == 422


# --- Validation ---------------------------------------------------------------------


@pytest.mark.parametrize("champ", ["intitule", "description", "competences_requises", "experience_min_annees", "niveau_formation"])
def test_champs_obligatoires(connecte, champ):
    donnees = {k: v for k, v in POSTE.items() if k != champ}
    reponse = connecte.post("/postes", json=donnees)
    assert reponse.status_code == 422
    assert champ in reponse.json()["champs"]


@pytest.mark.parametrize(
    ("changements", "champ"),
    [
        ({"intitule": "   "}, "intitule"),
        ({"competences_requises": ["", "  "]}, "competences_requises"),
        ({"experience_min_annees": -1}, "experience_min_annees"),
        ({"experience_min_annees": 51}, "experience_min_annees"),
        ({"experience_min_annees": "deux"}, "experience_min_annees"),
        ({"niveau_formation": "Bac"}, "niveau_formation"),
        ({"type_contrat": "interim"}, "type_contrat"),
        ({"teletravail": "parfois"}, "teletravail"),
        ({"date_limite": "31/12/2026"}, "date_limite"),
        ({"intitule": "x" * 256}, "intitule"),
        ({"langues": ["x" * 101]}, "langues"),
    ],
)
def test_valeurs_invalides(connecte, changements, champ):
    reponse = connecte.post("/postes", json={**POSTE, **changements})
    assert reponse.status_code == 422
    assert champ in reponse.json()["champs"]
    assert connecte.get("/postes").json() == []


def test_experience_zero_acceptee(connecte):
    assert creer(connecte, experience_min_annees=0)["experience_min_annees"] == 0


@pytest.mark.parametrize("niveau", ["BTS", "Licence", "Master", "Doctorat"])
def test_niveaux_de_formation(connecte, niveau):
    assert creer(connecte, niveau_formation=niveau)["niveau_formation"] == niveau


@pytest.mark.parametrize("contrat", ["CDI", "CDD", "stage", "mission", "freelance"])
def test_types_de_contrat(connecte, contrat):
    assert creer(connecte, type_contrat=contrat)["type_contrat"] == contrat


def test_toutes_les_erreurs_renvoyees_ensemble(connecte):
    reponse = connecte.post("/postes", json={})
    assert set(reponse.json()["champs"]) == {"intitule", "description", "competences_requises", "experience_min_annees", "niveau_formation"}


# --- Tableau de bord -----------------------------------------------------------------


def test_tableau_de_bord(connecte):
    assert connecte.get("/tableau-de-bord").json() == {
        "entreprise_nom": "",
        "profil_renseigne": False,
        "postes": {"brouillon": 0, "actif": 0, "cloture": 0, "total": 0},
    }
    creer(connecte)
    creer(connecte, statut="actif")
    creer(connecte, statut="actif")
    creer(connecte, statut="cloture")
    connecte.put("/entreprise", json={"nom": "CCA Bank"})
    assert connecte.get("/tableau-de-bord").json() == {
        "entreprise_nom": "CCA Bank",
        "profil_renseigne": True,
        "postes": {"brouillon": 1, "actif": 2, "cloture": 1, "total": 4},
    }
