# Sécurité du socle INJARA

## Liaison Electron ↔ backend Python

| Mesure | Où |
|---|---|
| Le backend écoute uniquement sur `127.0.0.1`, sur un port libre choisi par le système | `backend/__main__.py` |
| Electron génère un jeton aléatoire (256 bits) à chaque lancement et le passe par `INJARA_TOKEN` | `desktop/main/backend.js` |
| Toute requête sans ce jeton (en-tête `X-Injara-Token`) reçoit 401, y compris `/docs` (désactivé de toute façon) | `backend/api/securite.py` |
| Le backend refuse de démarrer sans jeton | `backend/api/app.py` |
| L'interface n'appelle pas le backend : elle passe par IPC, et le processus principal ajoute les jetons. Ni le jeton de lancement ni le jeton de session n'atteignent l'interface | `desktop/main/api.js` |
| `contextIsolation`, `sandbox`, `nodeIntegration: false` ; le preload n'expose que `window.injara.api.{get,post,put,delete}` et `window.injara.fichiers` (choix, import et ouverture de CV, identifiants Google) | `desktop/main/index.js`, `desktop/preload/index.js` |
| CSP stricte au build (`connect-src 'none'`), navigation externe et nouvelles fenêtres bloquées, permissions refusées sauf l'écriture dans le presse-papiers | `desktop/vite.config.mjs`, `desktop/main/index.js` |
| Le backend s'arrête quand Electron ferme son entrée standard, même si Electron plante. Le tube est lu sur un descripteur privé (stdin remplacé par NUL) : sous Windows, une lecture en attente sur stdin bloquerait le lancement de tout sous-processus | `backend/__main__.py` |
| Les routes de l'agent mail (`/gmail/*`, `/agent/*`) exigent la session, comme le reste | `backend/api/routes_agent.py` |
| Seul un 401 `code: "session_requise"` ferme la session (un mot de passe de messagerie refusé ne déconnecte pas) | `backend/api/app.py`, `desktop/main/api.js` |
| Import de CV : le processus principal lit lui-même les fichiers (PDF, DOCX, ZIP, 200 Mo max) ; ouverture d'un CV : par l'identifiant de la candidature uniquement, jamais par un chemin | `desktop/main/api.js` |

## Compte et clés

- **Un seul compte par installation.** Une deuxième création renvoie 409.
- **Mot de passe** : 12 caractères minimum, haché avec argon2id (`argon2-cffi`, paramètres par défaut : 3 passes, 64 Mio, 4 fils).
- **Clé de données** : 32 octets aléatoires générés à la création du compte. Elle chiffre les CV (voir plus bas).
  Elle n'est jamais écrite en clair ; elle est stockée deux fois, chiffrée en AES-256-GCM :
  - par une clé dérivée du mot de passe (argon2id, sel aléatoire) ;
  - par une clé dérivée de la clé de récupération (HKDF-SHA256, sel aléatoire). HKDF suffit ici car la clé de
    récupération contient 160 bits aléatoires, contrairement à un mot de passe.
- **Clé de récupération** : 160 bits en base32, au format `XXXX-XXXX-…` (8 groupes). Affichée une seule fois, avec
  une case à cocher obligatoire. La saisie tolère minuscules, espaces et tirets.
- **Mot de passe oublié** : la clé de récupération déchiffre la clé de données, qui est re-protégée par le nouveau
  mot de passe. Une **nouvelle** clé de récupération est alors générée et l'ancienne cesse de fonctionner (elle a pu
  être exposée en étant saisie). La clé de données, elle, ne change pas : les CV chiffrés restent lisibles.
- **Session** : en mémoire dans le backend (jeton aléatoire + clé de données déchiffrée). Fermer l'application arrête
  le backend et donc déconnecte. `AuthService.cle_session()` donne la clé au traitement de fond.

## Chiffrement des CV

`backend/services/coffre.py`, AES-256-GCM avec la clé de données de la session.

- **Fichiers** : l'agent mail écrit chaque CV reçu en clair (son module n'est pas modifié). Le traitement le chiffre
  dès le passage suivant (quelques secondes) dans `<fichier>.injara`, puis efface le clair. Les autres pièces jointes
  (lettres) aussi. Les fichiers restés en clair d'une version précédente sont chiffrés au premier passage.
- **Texte extrait** : le texte du CV et celui des lettres sont enregistrés chiffrés en base (préfixe `injara:v1:`).
  L'extraction enregistrée en clair ne garde que les noms des sections du CV, pas leur texte (les bases plus
  anciennes sont nettoyées au premier passage du traitement).
- **Note du recruteur** sur sa décision : chiffrée de la même façon.
- **Lecture** : les CV sont déchiffrés en mémoire, jamais sur le disque. Sans session, rien n'est traité.
- **Ouverture par le recruteur** : le backend renvoie le CV déchiffré (`GET /candidatures/{id}/cv`) ; Electron le pose
  dans `<temp>/injara-cv-ouverts/`, l'ouvre avec le logiciel du système, et vide ce dossier à la déconnexion, à la
  fermeture et au lancement suivant (un fichier encore ouvert, verrouillé sous Windows, part au nettoyage suivant).
- Un fichier chiffré altéré est signalé « illisible » et ne s'ouvre pas.

## Agent mail

- Le mot de passe d'une messagerie n'existe que dans le champ du formulaire (vidé dès la réponse) et dans le corps de
  la requête ; l'agent le range dans le coffre du système (`keyring`). Le jeton Gmail et le `credentials.json` sont
  dans `<données>/secrets/`.
- L'agent lit la boîte en lecture seule (`gmail.readonly` ou IMAP) ; la surveillance ne tourne que pendant une session.

## Limites connues (à traiter plus tard)

- Restent en clair dans SQLite : l'entreprise, les postes, et pour chaque candidature les nom, email, téléphone,
  objet et extrait du mail, ainsi que l'extraction détaillée (périodes, ligne du diplôme). Le registre de l'agent
  mail (`gmail_ledger*.db`) garde aussi expéditeurs, objets et extraits en clair.
- Entre son écriture par l'agent et le passage du traitement, un CV reste quelques secondes en clair sur le disque ;
  l'effacement ne garantit pas la disparition physique des données sur un SSD.
- Pas de verrouillage automatique après inactivité, ni de limitation du nombre d'essais de connexion (argon2 ralentit
  déjà chaque essai, et l'API n'est joignable qu'avec le jeton de lancement).
- Perdre à la fois le mot de passe et la clé de récupération rend la clé de données irrécupérable : c'est voulu.
