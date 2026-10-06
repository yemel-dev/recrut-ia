# Agent mail dans INJARA

L'agent (`backend/agent/`, Module 1) récupère les CV reçus en pièce jointe dans la boîte de recrutement.
Sa logique n'a pas été modifiée ; ce document explique comment il est branché dans l'application, et en quoi
cela diffère du *Guide d'intégration frontend — Agent IA Mail* rédigé pour son serveur de développement.

## Ce que voit le recruteur

| Écran | Rôle | Routes |
|---|---|---|
| **Boîte mail** (non liée) | Lier Gmail / Google Workspace, ou une autre messagerie (adresse, mot de passe, serveur) | `POST /gmail/connect`, `GET /gmail/imap/detect`, `POST /gmail/connect/imap`, `POST /agent/identifiants-google` |
| **Boîte mail** (premier réglage) | « Reprendre les candidatures déjà reçues ? » → aperçu → import, surveillance proposée | `GET /gmail/profiles`, `POST /gmail/preview`, `PUT /gmail/config[/profile/…]`, `POST /gmail/sync`, `PUT /agent/surveillance` |
| **Boîte mail** (liée) | Compte, déconnexion, profils, réglages avancés, diagnostic | `GET/PUT /gmail/config`, `POST /gmail/disconnect`, `GET /gmail/diagnostics` |
| **Candidatures** | CV reçus, onglet Ignorés, import manuel (bouton ou glisser-déposer), « Vérifier maintenant », surveillance | `GET /gmail/cvs`, `GET /gmail/ignored`, `POST /gmail/ignored/{id}/recover`, `POST /gmail/cvs/upload`, `POST /gmail/sync`, `PUT /agent/surveillance` |
| Partout | Notifications de nouveaux CV, alerte de reconnexion, bandeau MODE DÉMO, état dans la barre latérale | `GET /gmail/events`, `GET /gmail/status`, `GET /agent/etat` |

## Différences avec le guide frontend

1. **Sécurité de l'API.** Le guide fait appeler `http://127.0.0.1:PORT/gmail/...` directement par l'interface, sans
   authentification. Dans INJARA, toutes les routes `/gmail/*` sont montées telles quelles mais exigent le jeton de
   lancement **et une session ouverte**. L'interface passe par `window.injara.api` (IPC) ; il n'y a ni `apiBase`
   ni CORS. Le point 7 de la section sécurité du guide (jeton aléatoire) est donc réalisé.
2. **Fichiers.** L'interface n'a pas accès au disque. Le preload expose `window.injara.fichiers` :
   `choisirCV()`, `cheminDe(fichier)` (glisser-déposer), `importerCV(chemins)`, `ouvrirCV(saved_path)`,
   `importerIdentifiantsGoogle()`. Le processus principal vérifie les extensions et les tailles, et n'ouvre que des
   PDF ou DOCX situés dans le dossier des CV d'INJARA.
3. **Emplacement des données.** Les fichiers de l'agent ne sont plus dans `data/` à la racine du dépôt mais dans le
   dossier de données d'INJARA : `cvs/`, `agent_mail.db` (registre), `secrets/compte_mail.json`,
   `secrets/jeton_gmail.json`, `secrets/credentials.json`. Le mot de passe IMAP reste dans le coffre du système
   (`keyring`).
4. **Mode par défaut.** INJARA démarre en mode **réel**. `GMAIL_MODE=fake` (variable d'environnement ou `.env`) active
   la boîte de démonstration.
5. **Identifiants Google.** Le `credentials.json` de l'entreprise s'importe depuis l'écran Boîte mail ; il est vérifié
   (type « Application de bureau ») puis rangé dans `secrets/`.
6. **Surveillance.** Le choix « surveillance automatique » est mémorisé par INJARA (`PUT /agent/surveillance`, table
   `parametres`). Elle reprend à chaque connexion et s'arrête à la déconnexion ou à la fermeture de l'application,
   car les CV seront chiffrés avec la clé de la session.
7. **Erreurs 422.** Les erreurs de format ont la forme d'INJARA : `{"detail": "...", "champs": {"champ": "message"}}`.
   Les messages rédigés par les validateurs de l'agent (ex. « since_date est obligatoire quand mode = since_date »)
   sont conservés. Les 401 de session portent `code: "session_requise"`, ce qui les distingue d'un mot de passe de
   messagerie refusé.

## Travailler sur l'agent seul

Rien ne change : `python -m backend.agent.cli …` et
`uvicorn backend.agent.dev_server:app --port 8765` fonctionnent comme avant, avec les chemins du `.env`
(voir `backend/agent/README.md`). Ce serveur de développement n'est pas protégé : il ne doit servir qu'en local.

## Limites connues

- L'agent n'émet pas d'événement quand la surveillance échoue sur une exception (mot de passe changé, autorisation
  Google expirée) : l'erreur est seulement journalisée. L'alerte « Reconnecter le compte » ne s'affiche que si
  `sync_error` se répète ; sinon, le problème n'apparaît qu'en cliquant sur « Vérifier maintenant ».
- Ajouter une règle d'exclusion rescane la période : un email dont le CV a **déjà été importé** peut alors apparaître
  aussi dans « Ignorés ». « Récupérer quand même » le signale alors comme doublon.
- Les CV sont encore stockés en clair ; le chiffrement utilisera la clé de données de la session.
