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
| Le backend s'arrête quand Electron ferme son entrée standard, même si Electron plante | `backend/__main__.py` |
| Les routes de l'agent mail (`/gmail/*`, `/agent/*`) exigent la session, comme le reste | `backend/api/routes_agent.py` |
| Seul un 401 `code: "session_requise"` ferme la session (un mot de passe de messagerie refusé ne déconnecte pas) | `backend/api/app.py`, `desktop/main/api.js` |
| Import de CV : le processus principal lit lui-même les fichiers (PDF, DOCX, ZIP, 200 Mo max) ; ouverture d'un CV : uniquement un PDF ou DOCX situé dans le dossier des CV | `desktop/main/api.js` |

## Compte et clés

- **Un seul compte par installation.** Une deuxième création renvoie 409.
- **Mot de passe** : 12 caractères minimum, haché avec argon2id (`argon2-cffi`, paramètres par défaut : 3 passes, 64 Mio, 4 fils).
- **Clé de données** : 32 octets aléatoires générés à la création du compte. Elle est destinée au chiffrement des CV
  (pas encore branché). Elle n'est jamais écrite en clair ; elle est stockée deux fois, chiffrée en AES-256-GCM :
  - par une clé dérivée du mot de passe (argon2id, sel aléatoire) ;
  - par une clé dérivée de la clé de récupération (HKDF-SHA256, sel aléatoire). HKDF suffit ici car la clé de
    récupération contient 160 bits aléatoires, contrairement à un mot de passe.
- **Clé de récupération** : 160 bits en base32, au format `XXXX-XXXX-…` (8 groupes). Affichée une seule fois, avec
  une case à cocher obligatoire. La saisie tolère minuscules, espaces et tirets.
- **Mot de passe oublié** : la clé de récupération déchiffre la clé de données, qui est re-protégée par le nouveau
  mot de passe. Une **nouvelle** clé de récupération est alors générée et l'ancienne cesse de fonctionner (elle a pu
  être exposée en étant saisie). La clé de données, elle, ne change pas : les futurs CV chiffrés restent lisibles.
- **Session** : en mémoire dans le backend (jeton aléatoire + clé de données déchiffrée). Fermer l'application arrête
  le backend et donc déconnecte. `AuthService.cle_de_donnees(jeton)` est le point d'accès prévu pour le chiffrement.

## Agent mail

- Le mot de passe d'une messagerie n'existe que dans le champ du formulaire (vidé dès la réponse) et dans le corps de
  la requête ; l'agent le range dans le coffre du système (`keyring`). Le jeton Gmail et le `credentials.json` sont
  dans `<données>/secrets/`.
- L'agent lit la boîte en lecture seule (`gmail.readonly` ou IMAP) ; la surveillance ne tourne que pendant une session.

## Limites connues (à traiter plus tard)

- Les données de l'entreprise et des postes sont en clair dans SQLite, de même que les CV reçus (dossier `cvs/`) pour
  l'instant : leur chiffrement avec la clé de données est la prochaine étape.
- Pas de verrouillage automatique après inactivité, ni de limitation du nombre d'essais de connexion (argon2 ralentit
  déjà chaque essai, et l'API n'est joignable qu'avec le jeton de lancement).
- Perdre à la fois le mot de passe et la clé de récupération rend la clé de données irrécupérable : c'est voulu.
