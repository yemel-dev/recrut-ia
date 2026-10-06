# INJARA

Application de recrutement installée sur l'ordinateur du recruteur. Toutes les données restent en local : aucun
serveur distant. Une installation correspond à une entreprise et à un compte.

- **Interface** : Electron + React (Vite) + Tailwind CSS, en JavaScript (`desktop/`)
- **Moteur** : Python, FastAPI, SQLAlchemy, SQLite (`backend/`), lancé et arrêté par Electron
- **Agent mail** : récupère les CV reçus dans la boîte de recrutement, Gmail ou autre messagerie (`backend/agent/`,
  intégration décrite dans [docs/agent-mail.md](docs/agent-mail.md))

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

`requirements.txt` contient le socle, y compris la lecture des CV (pypdf, python-docx), et s'installe en quelques
secondes. Le critère « adéquation globale » du score utilise Sentence-BERT, plus lourd (environ 700 Mo avec le
modèle). Sans lui, INJARA fonctionne et note les CV sur les trois autres critères. Pour l'activer :

```bash
# Windows : .venv\Scripts\python ; Linux : .venv/bin/python
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-ia.txt
python -m backend.ia.telecharger_modele   # une seule fois, puis tout fonctionne hors ligne
```

## Lancer

```bash
cd desktop
npm run dev     # interface avec rechargement à chaud ; Electron lance lui-même le backend
npm start       # compile l'interface puis lance Electron sur la version compilée
```

Pour développer sans vraie boîte mail, lancer en **mode démo** (boîte simulée avec 5 CV d'exemple, bandeau
« MODE DÉMO » dans l'application). Cette commande fonctionne dans tous les terminaux (PowerShell, cmd, bash) :

```bash
npm run dev:demo
```

Avec `npm run dev`, l'agent est en mode réel. Pour lier un compte Gmail, l'application demande le fichier
`credentials.json` de l'entreprise (ID client OAuth de type « Application de bureau », voir
`backend/agent/README.md`) ; une autre messagerie se lie avec son adresse et son mot de passe.

Electron utilise le Python de `.venv` à la racine du dépôt. Pour en utiliser un autre, définir `INJARA_PYTHON`
(chemin de l'exécutable).

Les données (base `injara.db`, CV reçus dans `cvs/`, registre de l'agent, compte mail dans `secrets/`) sont rangées
dans le dossier utilisateur d'Electron, sous-dossier `donnees` :

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
(`test_postes.py`), le profil entreprise (`test_entreprise.py`), l'intégration de l'agent mail
(`test_agent_mail.py`, en mode démo), le traitement des candidatures (`test_ia_extraction.py`,
`test_ia_scoring.py`, `test_traitement.py`, avec des CV fictifs dans `backend/tests/fixtures/`) et l'agent lui-même
(`backend/tests/agent/`).

## Dépannage

**`npm install` échoue sous Windows avec « Electron failed to install correctly » ou « Cannot find native binding ».**
L'extracteur d'Electron a besoin du runtime Visual C++. Installer
[Microsoft Visual C++ Redistributable 2015-2022 (x64)](https://aka.ms/vs/17/release/vc_redist.x64.exe), puis
supprimer `desktop/node_modules/electron` et relancer `npm install`.

**« INJARA ne peut pas démarrer » au lancement.** Le message indique le Python utilisé et l'erreur du backend.
Vérifier que `.venv` existe à la racine et que `requirements.txt` y est installé.

## Organisation

```
desktop/                Electron
  main/                 fenêtre, lancement et arrêt du backend, pont API (IPC)
  preload/              pont sécurisé exposé à l'interface (window.injara)
  renderer/             écrans React
backend/                Python
  __main__.py           point d'entrée lancé par Electron (python -m backend)
  api/                  routes FastAPI, sans logique : elles appellent services/
  services/             logique métier : compte et clés, entreprise, postes, tableau de bord, agent mail
  database/             modèles SQLAlchemy ; seul paquet qui accède à la base
  agent/                agent mail (Gmail OAuth, IMAP, import manuel), monté sous /gmail
  ia/                   lecture et analyse des CV, score, classement (voir docs/traitement.md)
  tests/
docs/                   cadrage (README.md), sécurité, agent mail, traitement des candidatures
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
