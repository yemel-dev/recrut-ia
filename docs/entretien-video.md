# Module entretien vidéo

Le recruteur planifie un entretien depuis une candidature, envoie un lien au candidat, et mène l'entretien en
visio depuis INJARA. Le candidat n'installe rien : il ouvre le lien dans son navigateur.

## Fonctionnalités

| # | Fonctionnalité | État |
|---|---|---|
| 1 | Lien candidat, visio WebRTC, enregistrement local chiffré | Fait |
| 2 | Analyse du regard et des mouvements de tête (MediaPipe) | Fait |
| 4 | Consignes et vigilance dans le navigateur du candidat | Fait |
| 5 | Section « entretien » du rapport PDF | Fait |
| + | Serveur TURN (Cloudflare ou manuel) pour les candidats distants | Fait |

## Comment ça marche

1. **Le lien.** Une page servie sous `/public/` est exposée par un tunnel Cloudflare nommé (domaine stable,
   par ex. `https://meet.injara.site`, géré par le service `cloudflared` de la machine). On renseigne
   `INJARA_URL_PUBLIQUE` et `INJARA_PORT` (le port local visé par le tunnel) dans `.env` : INJARA ne lance alors
   aucun tunnel. Sans cela, repli sur un tunnel rapide `cloudflared` (adresse aléatoire). ngrok n'est plus géré. HTTPS est obligatoire : sans lui le navigateur refuse la caméra.
2. **La signalisation.** Candidat et recruteur se parlent par WebSocket (`backend/services/signalisation.py`) pour
   échanger offre, réponse et candidats ICE. Le recruteur s'y connecte depuis le processus principal Electron.
   Les routes `/public/` n'utilisent pas le jeton de lancement : chacune s'authentifie par le code d'invitation
   ou par un ticket à usage unique (60 s).
3. **Le média.** Image et son passent en pair-à-pair (WebRTC), pas par le tunnel. Sur le même réseau local cela
   marche seul. Entre deux réseaux différents, il faut souvent un **relais TURN** (voir plus bas).
4. **L'enregistrement.** Fait localement par le recruteur (`enregistreur.js`), chiffré avec la clé de données de la
   session (AES-256-GCM, `coffre.py`). Format : MP4 (H.264) quand le moteur d'Electron sait l'encoder, WebM en
   repli ; le backend reconnaît le conteneur au premier morceau et l'export garde la bonne extension.

## Analyse du regard (étape 2)

`backend/ia/regard.py` : MediaPipe Face Landmarker (blendshapes et matrice de transformation). Une calibration
fixe la posture de référence. Seuils : tête 25° (lacet) et 20° (tangage), regard 0,35 / 0,40, événement après 3 s.
Score = part du temps où le candidat est attentif. Routes : `PUT /entretiens/{id}/regard`, `GET .../regard`.
Le modèle se télécharge dans `modeles/` (ignoré par git).

## Consignes et vigilance (étape 4)

Avant d'entrer, le candidat doit accepter les consignes (fermer les autres applications, etc.). La page signale
au backend (`POST /public/api/{code}/signal`, 300 signaux max) : changement d'onglet, perte de focus, sortie du
plein écran, second écran. **Limite assumée** : un navigateur ne voit pas les autres applications ; aucun
programme compagnon n'est prévu. Le recruteur voit ces signaux dans `CarteVigilance`.

## Rapport (étape 5)

`RapportService` ajoute la section entretien (durée, regard, vigilance, mention) ; `desktop/main/rapport.js`
l'imprime en PDF. Bouton d'export sur la page Entretien.

## Serveur TURN

Sans relais, un candidat derrière certains réseaux (CGNAT, pare-feu) reste sur « connexion en cours ».
`backend/services/reseau.py` choisit les serveurs ICE dans cet ordre :

1. `INJARA_ICE_SERVERS` (variable d'environnement) ;
2. TURN saisi à la main dans l'interface (stocké chiffré) ;
3. **Cloudflare Realtime TURN**, si `CLOUDFLARE_TURN_TOKEN_ID` et `CLOUDFLARE_API_TOKEN` sont dans `.env` :
   identifiants temporaires (24 h), renouvelés automatiquement, mis en pause 60 s après un échec ;
4. STUN seul.

Le bouton « Tester le serveur » (page Entretien) vérifie qu'un candidat de type `relay` est obtenu
(`testTurn.js`). Routes : `GET /reseau`, `PUT`/`DELETE /reseau/turn`, `GET /reseau/test`.
Les valeurs Cloudflare ne vont **jamais** dans le code : uniquement dans `.env` (voir `.env.example`).

## Fichiers principaux

- Backend : `backend/web/candidat/` (page candidat), `backend/api/routes_candidat.py`,
  `backend/api/routes_entretiens.py`, `backend/services/{entretiens,signalisation,tunnel,reseau,regard,rapport}.py`,
  `backend/ia/regard.py`.
- Interface : `desktop/renderer/src/entretiens/`, `desktop/renderer/src/pages/Entretien.jsx`,
  `desktop/main/{api,rapport}.js`.
- Tests : `backend/tests/test_{entretien_visio,regard,vigilance,rapport_entretien,reseau}.py`.

## Limites connues

- MediaPipe est exclu de l'installeur (`packaging/injara-backend.spec`) : l'analyse du regard est
  indisponible dans la version installée tant qu'il n'y est pas intégré.
- Seuils du regard non calibrés sur de vrais entretiens.
- La vidéo réelle via Electron est peu testée.
- Les scores `contenu` et `confiance` n'ont pas encore de module qui les produise.
- L'installation n'a pas de `.env` : le TURN Cloudflare doit y être configuré ou saisi à la main.

## Suite envisagée

Diagnostic de connexion (états ICE, type de candidat retenu), service INJARA hébergé (domaine stable,
signalisation et coturn à identifiants éphémères), reconnexion automatique.
