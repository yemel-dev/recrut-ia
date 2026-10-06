from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.config import KdfParams, Settings

JETON = "jeton-de-test-" + "x" * 32
EMAIL = "rh@entreprise.cm"
MOT_DE_PASSE = "motdepasse-solide-2026"

# argon2 allégé : les tests restent rapides, la logique est identique
KDF_RAPIDE = KdfParams(time_cost=1, memory_cost_kib=8 * 1024, parallelism=1)


@pytest.fixture
def settings(tmp_path) -> Settings:
    # Dossier de modèles vide : les tests ne chargent jamais le vrai modèle Sentence-BERT.
    return Settings(data_dir=tmp_path / "data", token=JETON, kdf=KDF_RAPIDE, mode_agent="fake", dossier_modeles=tmp_path / "modeles")


@pytest.fixture
def app(settings):
    app = create_app(settings)
    yield app
    app.state.services.traitement.arreter()
    app.state.services.agent_mail.arreter()
    app.state.db.close()


@pytest.fixture
def client(app) -> TestClient:
    """Client qui envoie le jeton de lancement, comme Electron, mais sans session."""
    return TestClient(app, headers={"X-Injara-Token": JETON})


@pytest.fixture
def cle_recuperation(client) -> str:
    reponse = client.post("/auth/compte", json={"email": EMAIL, "mot_de_passe": MOT_DE_PASSE})
    assert reponse.status_code == 201, reponse.text
    return reponse.json()["cle_de_recuperation"]


@pytest.fixture
def connecte(client, cle_recuperation) -> TestClient:
    """Client avec compte créé et session ouverte."""
    reponse = client.post("/auth/connexion", json={"email": EMAIL, "mot_de_passe": MOT_DE_PASSE})
    assert reponse.status_code == 200, reponse.text
    client.headers["X-Injara-Session"] = reponse.json()["jeton_session"]
    return client
