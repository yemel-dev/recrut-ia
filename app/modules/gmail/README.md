# Module 1 — Connexion mail & récupération des CV

Agent Python autonome : il ne dépend ni du frontend, ni des autres modules.

## Les trois façons de lier une boîte mail

| Cas | Technique | Ce que fait le recruteur |
|---|---|---|
| Entreprise sous **Google Workspace** | API Gmail + OAuth2 | Clique sur « Lier mon compte Gmail », se connecte dans la fenêtre Google |
| **Autre hébergeur** (OVH, o2switch, serveur pro…) | IMAP | Saisit son adresse, le serveur IMAP et un mot de passe d'application |
| **Adresse simple** (Gmail perso, Yahoo…) | IMAP | Saisit son adresse et un mot de passe d'application (le serveur est détecté tout seul) |

Le mot de passe d'application est rangé dans le coffre du système (Windows Credential Manager…) via `keyring`,
jamais dans un fichier du projet. Sans coffre disponible, il est gardé en mémoire pour la session seulement.

## Lancer sans frontend (mode simulé par défaut)

```bash
# Serveur de dev + interface Swagger (remplace le frontend)
uvicorn app.modules.gmail.dev_server:app --reload --port 8765
# Import de CV (glisser-déposer) : http://127.0.0.1:8765/import
# Autres routes (Swagger)   : http://127.0.0.1:8765/docs

# Ou en ligne de commande
python -m app.modules.gmail.cli sync
python -m app.modules.gmail.cli list
python -m app.modules.gmail.cli import --path C:\\mes_cv    # dossier, fichier ou .zip
python -m app.modules.gmail.cli watch --minutes 1
```

`GMAIL_MODE=fake` (défaut) : une boîte mail simulée avec 5 CV de démo. Aucun compte requis. Le formulaire IMAP est simulé aussi : n'importe quel mot de passe est accepté, sauf `mauvais` (qui renvoie une erreur 401), pour développer l'écran d'erreur.
`GMAIL_MODE=real` : vraie boîte Gmail (voir « Brancher le vrai Gmail » plus bas).

## Contrat API (ce que le frontend appellera)

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/gmail/status` | état : connecté ? type de compte (`gmail_oauth`/`imap`), adresse, surveillance, nb de CV |
| POST | `/gmail/connect` | Google Workspace / Gmail : autorisation OAuth2 (ouvre le navigateur) |
| GET | `/gmail/imap/detect?email=...` | pré-remplit le serveur IMAP d'après l'adresse (+ aide mot de passe d'application) |
| POST | `/gmail/connect/imap` | IMAP : `{email, password, host?, port?, folder?}` (401 mauvais identifiants, 502 serveur injoignable, 422 serveur à préciser) |
| POST | `/gmail/disconnect` | oublie le compte (jeton OAuth ou mot de passe IMAP) |
| POST | `/gmail/sync` | vérifie la boîte maintenant |
| POST | `/gmail/watch/start?poll_minutes=5` | surveillance en arrière-plan |
| POST | `/gmail/watch/stop` | arrête la surveillance |
| POST | `/gmail/cvs/upload` | bouton « Importer des CV » : fichiers PDF/DOCX et/ou ZIP (multipart, champ `files`). Marche sans boîte mail connectée |
| GET | `/gmail/profiles` | profils prédéfinis (libellé, description, réglages) |
| PUT | `/gmail/config/profile/{nom}` | applique un profil |
| POST | `/gmail/preview` | aperçu avant import (corps facultatif = réglages à évaluer) |
| GET | `/gmail/ignored` | liste « Ignorés » avec la raison |
| POST | `/gmail/ignored/{id}/recover` | « Récupérer quand même » |
| GET | `/gmail/cvs?limit=50&offset=0` | CV récupérés (chemin local, expéditeur, objet, date) |
| GET | `/gmail/events?after_id=0` | notifications (« 3 nouveaux CV récupérés ») |
| POST | `/gmail/dev/simulate-email` | DEV : fait arriver un faux email (mode fake) |

Chaque CV porte un champ `source` : `email` (récupéré par l'agent) ou `upload` (importé à la main).
Un CV importé puis reçu plus tard par email est reconnu comme doublon.

NB : Swagger (/docs) affiche mal les champs « liste de fichiers » (zone de texte au lieu d'un sélecteur). Pour importer, utiliser la page /import, la CLI, ou curl.exe.

Exemple d'upload côté Electron (bouton + glisser-déposer) :

```js
async function importerCV(fileList) {
  const form = new FormData();
  for (const f of fileList) form.append("files", f);
  const res = await fetch("http://127.0.0.1:8765/gmail/cvs/upload", { method: "POST", body: form });
  const { imported, duplicates_skipped, rejected } = await res.json();
  // afficher : N importés, N doublons, N rejetés (avec la raison de chaque rejet)
}
```

Exemple côté Electron (renderer) pour les notifications :

```js
const API = "http://127.0.0.1:8765";
let lastId = 0;
setInterval(async () => {
  const events = await (await fetch(`${API}/gmail/events?after_id=${lastId}`)).json();
  for (const e of events) { lastId = e.id; if (e.type === "new_cvs") notify(e.message); }
}, 5000);
```

## Intégrer dans l'application principale

```python
from app.modules.gmail.api import router as gmail_router
app.include_router(gmail_router)
```

Ou, côté Python pur : `from app.modules.gmail import create_agent` puis `agent.subscribe(callback)`.

## Brancher le vrai Gmail (OAuth)

1. Google Cloud Console → créer un projet → activer « Gmail API ».
2. Écran de consentement OAuth, puis identifiants → « ID client OAuth » de type « Application de bureau » → télécharger le JSON.
3. Le placer dans `data/secrets/credentials.json` (jamais commité).
4. Dans `.env` : `GMAIL_MODE=real`, puis `python -m app.modules.gmail.cli connect`.

**Jeton qui expire tous les 7 jours** : cela arrive quand le projet est en type « Externe » et en mode « Test ».
- Entreprise sous Google Workspace : créer le projet Google Cloud **dans l'organisation de l'entreprise** et choisir le type
  d'utilisateur **« Interne »**. Pas d'expiration à 7 jours, pas de vérification Google à passer. Chaque entreprise cliente
  a donc son propre `credentials.json` (à importer à l'installation).
- Autre cas : il faut publier l'application et passer la vérification Google. À ma connaissance, `gmail.readonly` est un
  scope « restreint » qui demande une évaluation de sécurité payante : à vérifier dans la documentation Google avant de s'engager.
  Pour les adresses simples, utilisez plutôt IMAP (aucun jeton à renouveler).

## Brancher une boîte en IMAP

Pas besoin de Google Cloud. **Gmail perso / Yahoo** : le recruteur crée un **mot de passe d'application** (Gmail : validation en 2 étapes d'abord).
**OVH** : on utilise simplement le mot de passe de la boîte mail. Puis : `POST /gmail/connect/imap`, ou en dev :
`GMAIL_MODE=real python -m app.modules.gmail.cli connect`.
Serveurs connus d'avance : Gmail, Yahoo. Pour OVH : offre MX Plan → `imap.mail.ovh.net` ou `ssl0.ovh.net` ; offre Email Pro → `pro?.mail.ovh.net` (le numéro est dans l'espace client OVH) ; port 993 dans tous les cas.
Outlook/Hotmail ne sont pas pris en charge : à ma connaissance Microsoft exige OAuth pour ces comptes.

## Variables d'environnement (à ajouter à .env.example)

```
GMAIL_MODE=fake
GMAIL_CREDENTIALS_PATH=data/secrets/credentials.json
GMAIL_TOKEN_PATH=data/secrets/token.json
MAIL_ACCOUNT_PATH=data/secrets/account.json
GMAIL_POLL_MINUTES=5
GMAIL_LOOKBACK_DAYS=30
```

## À ajouter à .gitignore

```
data/secrets/
data/*.db
data/cvs/*
!data/cvs/.gitkeep
```

## Réglages de l'Agent IA mail (écran « Paramètres » du frontend)

Tout tient dans **un seul objet JSON**, lu par `GET /gmail/config` et enregistré par `PUT /gmail/config`. Le frontend peut renvoyer
tel quel l'objet reçu (les champs calculés `profile`, `description`, `warnings` sont ignorés à l'envoi).

```json
{
  "mode": "last_days",          // new_only | last_days | since_date | all
  "days": 30,                   // si mode = last_days
  "since_date": null,           // "2026-10-01" si mode = since_date (minuit UTC)
  "unread_only": false,         // RÉGLAGE AVANCÉ (risqué, voir warnings)
  "ignore_automatic": true,     // newsletters, notifications, réponses automatiques
  "ignored_senders": [],        // adresses ("rh@x.com") ou domaines ("linkedin.com", couvre aussi mail.linkedin.com)
  "allowed_extensions": ["pdf", "docx"],
  "max_attachment_mb": 20,      // 1 à 50
  "folder": null,               // dossier IMAP ou étiquette Gmail à lire ; null = boîte de réception / tout

  "profile": "prudent",         // (lecture seule) prudent | new_only | everything | custom
  "description": "Récupère les emails reçus durant les 30 derniers jours — lus ou non lus (emails automatiques ignorés).",
  "warnings": []                // (lecture seule) phrases à afficher à côté des réglages risqués
}
```

### Parcours conseillé pour le frontend

1. **Connexion** (`POST /gmail/connect` ou `/gmail/connect/imap`). Ensuite `GET /gmail/status` : si `needs_setup` est `true`,
   afficher l'écran de démarrage « Reprendre les candidatures déjà reçues ? ».
2. **Choix de reprise** : « 30 derniers jours » (présélectionné), « depuis une date », « seulement les nouveaux ».
   La liste des profils vient de `GET /gmail/profiles` (rien à coder en dur).
3. **Aperçu** : `POST /gmail/preview` avec le réglage envisagé (même forme que `/gmail/config`) → « 42 emails avec CV :
   38 à importer, 3 ignorés, 1 déjà importé » + 20 exemples. Rien n'est téléchargé ni enregistré.
4. **Valider** : `PUT /gmail/config` (ou `PUT /gmail/config/profile/prudent`). Cela enregistre le choix et met `needs_setup` à `false`.
5. **Importer** : `POST /gmail/sync`, puis `POST /gmail/watch/start` pour suivre les nouveaux emails.
6. **Onglet « Ignorés (n)** » : `GET /gmail/ignored` (raison lisible pour chaque élément) et `POST /gmail/ignored/{id}/recover`
   pour le bouton « Récupérer quand même ». `GET /gmail/status` donne `ignored_count` pour le badge.
7. **Paramètres avancés** : `unread_only` et les règles d'exclusion. Afficher `warnings` sous les réglages concernés.

### Les 3 profils

| Profil | Réglages |
|---|---|
| `prudent` (recommandé) | 30 derniers jours puis les nouveaux ; emails automatiques ignorés |
| `new_only` | uniquement ce qui arrive à partir de maintenant |
| `everything` | tout l'historique, sans filtrer les emails automatiques, fichiers jusqu'à 50 Mo |

### Principes à retenir

- **Rien n'est ignoré en silence** : chaque pièce jointe écartée apparaît dans `/gmail/ignored` avec la raison
  (`rule` = `automatic`, `sender`, `extension` ou `size`).
- **Règles d'exclusion plutôt que de sélection** : on liste ce qu'on veut écarter, jamais « seulement si l'objet contient CV » ;
  un candidat qui écrit « Bonjour » ne doit pas être perdu.
- **Changer un réglage rescanne la période** : les emails déjà ignorés sont réévalués (si la règle a été assouplie, ils sont importés),
  et les CV déjà pris ne sont jamais recomptés.
- **Attention aux sites d'emploi** : certains envoient les candidatures comme des emails automatiques (en-tête de désabonnement).
  Si vos clients en reçoivent, surveiller l'onglet « Ignorés » ou désactiver `ignore_automatic`.
- Un `unread_only` actif fait manquer tout email ouvert avant la synchronisation suivante.

```powershell
python -m app.modules.gmail.cli config                                   # voir les réglages
python -m app.modules.gmail.cli config --profile prudent                 # appliquer un profil
python -m app.modules.gmail.cli config --sync-mode new_only              # seulement les nouveaux
python -m app.modules.gmail.cli config --period-days 14                  # 14 derniers jours
python -m app.modules.gmail.cli config --since-date 2026-10-01           # depuis une date
python -m app.modules.gmail.cli config --add-ignored-sender linkedin.com # ignorer un expéditeur ou un domaine
python -m app.modules.gmail.cli config --max-mb 10 --types pdf --folder Candidatures
python -m app.modules.gmail.cli preview --period-days 30                 # aperçu AVANT import (rien n'est enregistré)
python -m app.modules.gmail.cli ignored                                  # liste des ignorés et pourquoi
python -m app.modules.gmail.cli recover --id 3                           # « Récupérer quand même »
python -m app.modules.gmail.cli reset-cursor                             # repartir de zéro avec les réglages
```

Valeurs de départ au premier lancement (`.env`) : `GMAIL_SYNC_MODE`, `GMAIL_LOOKBACK_DAYS`, `GMAIL_SINCE_DATE`, `GMAIL_UNREAD_ONLY`.
Ensuite, les réglages enregistrés depuis l'application l'emportent. `GMAIL_MAX_RESULTS` (500) limite le nombre d'emails traités par
synchronisation : au-delà, la synchro s'arrête proprement (`truncated: true`) et la suivante continue sans rien perdre.

## Auditer : « pourquoi mon email n'est pas récupéré ? »

```powershell
python -m app.modules.gmail.cli diagnose --days 3     # rapport email par email, sans rien enregistrer
python -m app.modules.gmail.cli sync                  # affiche aussi les pièces jointes écartées et pourquoi
python -m app.modules.gmail.cli reset-cursor          # re-regarder toute la période de rattrapage
```
Même chose via l'API : `GET /gmail/diagnostics?days=3`. Le programme affiche en tête de chaque commande s'il est en mode
SIMULATION (fake) ou RÉEL.

## Tests

```bash
pytest tests/test_gmail.py -v
```
