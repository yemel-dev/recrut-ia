from __future__ import annotations

import pytest

PROFIL = {
    "nom": "Entreprise Exemple SA",
    "secteur": "Banque et finance",
    "ville": "Douala",
    "email_pro": "RH@Exemple.cm",
    "telephone": "+237 6 99 00 00 00",
    "description": "Établissement financier.",
}


def test_profil_vide_au_depart(connecte):
    assert connecte.get("/entreprise").json() == {
        "nom": "", "secteur": None, "ville": None, "email_pro": None, "telephone": None, "description": None,
    }


def test_enregistrer_puis_consulter(connecte):
    reponse = connecte.put("/entreprise", json=PROFIL)
    assert reponse.status_code == 200
    attendu = {**PROFIL, "email_pro": "rh@exemple.cm"}
    assert reponse.json() == attendu
    assert connecte.get("/entreprise").json() == attendu


def test_modifier_et_vider_un_champ(connecte):
    connecte.put("/entreprise", json=PROFIL)
    reponse = connecte.put("/entreprise", json={**PROFIL, "ville": "Yaoundé", "description": "  "})
    assert reponse.json()["ville"] == "Yaoundé"
    assert reponse.json()["description"] is None


@pytest.mark.parametrize(
    ("changements", "champ"),
    [({"nom": ""}, "nom"), ({"email_pro": "rh@"}, "email_pro"), ({"telephone": "appelez-moi"}, "telephone")],
)
def test_validation(connecte, changements, champ):
    reponse = connecte.put("/entreprise", json={**PROFIL, **changements})
    assert reponse.status_code == 422
    assert champ in reponse.json()["champs"]
