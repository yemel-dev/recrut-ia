"""Vigilance pendant l'entretien : consignes, signaux envoyés par la page du candidat."""
from __future__ import annotations

import pytest

from .test_entretien_visio import _demarrer, anonyme, entretien  # noqa: F401
from .test_traitement import boite, services  # noqa: F401


def _signal(client, code, type_="perte_focus", **details):
    return client.post(f"/public/api/{code}/signal", json={"type": type_, **details})


def _alertes(connecte, entretien):
    return connecte.get(f"/entretiens/{entretien['id']}").json()["alertes"]


def test_engagement_aux_consignes_enregistre(anonyme, connecte, entretien):  # noqa: F811
    code = entretien["code_invitation"]
    assert connecte.get(f"/entretiens/{entretien['id']}").json()["consignes_acceptees_le"] is None
    assert anonyme.post(f"/public/api/{code}/consentement", json={"accepte": False, "consignes": True}).status_code == 200
    assert connecte.get(f"/entretiens/{entretien['id']}").json()["consignes_acceptees_le"] is not None


def test_signaux_du_candidat_deviennent_des_alertes(anonyme, connecte, entretien):  # noqa: F811
    _demarrer(connecte, entretien)
    code = entretien["code_invitation"]
    assert _signal(anonyme, code, duree_s=12.5, raison="onglet_masque").status_code == 204
    assert _signal(anonyme, code, "sortie_plein_ecran").status_code == 204
    assert _signal(anonyme, code, "plusieurs_ecrans").status_code == 204
    alertes = _alertes(connecte, entretien)
    assert [a["type"] for a in alertes] == ["perte_focus", "sortie_plein_ecran", "plusieurs_ecrans"]
    assert alertes[0]["details"] == {"duree_s": 12.5, "raison": "onglet_masque"}


def test_la_page_ne_peut_pas_se_faire_passer_pour_un_programme_compagnon(anonyme, connecte, entretien):  # noqa: F811
    _demarrer(connecte, entretien)
    code = entretien["code_invitation"]
    for type_ in ("application_suspecte", "surveillance_interrompue", "regard_detourne", "inconnu"):
        assert _signal(anonyme, code, type_).status_code == 422
    assert _alertes(connecte, entretien) == []


def test_signal_ignore_hors_entretien_ou_sans_consentement(anonyme, connecte, entretien):  # noqa: F811
    code = entretien["code_invitation"]
    connecte.put(f"/entretiens/{entretien['id']}/consentement", json={"accepte": True})
    assert _signal(anonyme, code).status_code == 204  # encore « planifie » : accepté mais ignoré
    assert _alertes(connecte, entretien) == []
    _demarrer(connecte, entretien, consentement=False)
    connecte.put(f"/entretiens/{entretien['id']}/consentement", json={"accepte": False})
    assert _signal(anonyme, code).status_code == 204
    assert _alertes(connecte, entretien) == []


def test_signal_refuse_pour_un_lien_invalide_ou_un_entretien_clos(anonyme, connecte, entretien):  # noqa: F811
    assert _signal(anonyme, "inconnu").status_code == 404
    _demarrer(connecte, entretien)
    connecte.put(f"/entretiens/{entretien['id']}/statut", json={"statut": "termine"})
    assert _signal(anonyme, entretien["code_invitation"]).status_code == 404


@pytest.mark.parametrize("corps", [{"type": "perte_focus", "duree_s": -1}, {"type": "perte_focus", "duree_s": 1e9}, {"type": "perte_focus", "raison": "x" * 41}, {}])
def test_signal_aux_valeurs_invalides(anonyme, connecte, entretien, corps):  # noqa: F811
    _demarrer(connecte, entretien)
    assert anonyme.post(f"/public/api/{entretien['code_invitation']}/signal", json=corps).status_code == 422


def test_le_nombre_de_signaux_est_plafonne(anonyme, connecte, entretien, monkeypatch):  # noqa: F811
    monkeypatch.setattr("backend.services.entretiens.MAX_SIGNAUX_CANDIDAT", 3)
    _demarrer(connecte, entretien)
    for _ in range(10):
        _signal(anonyme, entretien["code_invitation"])
    assert len(_alertes(connecte, entretien)) == 3
