# INJARA

Application de recrutement installée sur l'ordinateur du recruteur. Toutes les données restent en local : aucun
serveur distant. Une installation correspond à une entreprise et à un compte.

- **Interface** : Electron + React (Vite) + Tailwind CSS, en JavaScript (`desktop/`)
- **Moteur** : Python, FastAPI, SQLAlchemy, SQLite (`backend/`), lancé et arrêté par Electron
- **Agent mail** : récupère les candidatures depuis Gmail ou IMAP (`backend/agent/`, voir son README)

## Prérequis

- Python 3.11 ou plus récent
- Node.js 20 ou plus récent

## Installation (développement)

À la racine du dépôt :

```bash
# 1. Moteur Python
python -m venv .venv
# Windows (PowerShell) :
.venv\Scripts\python -m pip install -r requirements-dev.txt
# Linux :
.venv/bin/python -m pip install -r requirements-dev.txt

# 2. Interface
cd desktop
npm install
```

`requirements.txt` contient le socle et s'installe en quelques secondes. Les bibliothèques d'IA (plusieurs Go) sont
dans `requirements-ia.txt` et ne servent que pour travailler sur `backend/ia/`.

## Lancer

```bash
cd desktop
npm run dev     # interface avec rechargement à chaud ; Electron lance lui-même le backend
npm start       # compile l'interface puis lance Electron sur la version compilée
```

Electron utilise le Python de `.venv` à la racine du dépôt. Pour en utiliser un autre, définir `INJARA_PYTHON`
(chemin de l'exécutable).

Les données (base `injara.db`) sont rangées dans le dossier utilisateur d'Electron, sous-dossier `donnees` :

- Windows : `%APPDATA%\injara-desktop\donnees`
- Linux : `~/.config/injara-desktop/donnees`

Pour repartir de zéro (écran de création du compte), fermer l'application et supprimer ce dossier, ou lancer
avec un autre dossier : `INJARA_DATA_DIR=/chemin/vers/dossier npm run dev`.

## Tests

```bash
# Windows
.venv\Scripts\python -m pytest
# Linux
.venv/bin/python -m pytest
```

Les tests couvrent l'authentification (`backend/tests/test_auth.py`), les postes et le tableau de bord
(`test_postes.py`), le profil entreprise (`test_entreprise.py`) et l'agent mail (`backend/tests/agent/`).

## Organisation

```
desktop/                Electron
  main/                 fenêtre, lancement et arrêt du backend, pont API (IPC)
  preload/              pont sécurisé exposé à l'interface (window.injara)
  renderer/             écrans React
backend/                Python
  __main__.py           point d'entrée lancé par Electron (python -m backend)
  api/                  routes FastAPI, sans logique : elles appellent services/
  services/             logique métier : compte et clés, entreprise, postes, tableau de bord
  database/             modèles SQLAlchemy ; seul paquet qui accède à la base
  agent/                agent mail (Gmail OAuth, IMAP, import manuel)
  ia/                   NLP et scoring (vide pour l'instant)
  tests/
docs/                   documents de cadrage et décisions (docs/README.md), sécurité (docs/securite.md)
```

## Lancer le backend seul

Utile pour déboguer l'API sans Electron. Le jeton doit faire au moins 32 caractères.

```bash
# Linux
INJARA_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))") .venv/bin/python -m backend
# Windows (PowerShell)
$env:INJARA_TOKEN = .venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(32))"
.venv\Scripts\python -m backend
```

Le port choisi s'affiche (`INJARA_PORT=…`). Chaque requête doit porter l'en-tête `X-Injara-Token`. Le backend
s'arrête quand son entrée standard se ferme (Ctrl+Z puis Entrée sous Windows, Ctrl+D sous Linux).
