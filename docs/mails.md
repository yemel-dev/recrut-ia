# Mails aux candidats

Invitation à un entretien pour les candidats retenus, réponse négative pour les candidats écartés.

**Aucun mail ne part automatiquement.** Un changement de décision, une planification d'entretien ou une clôture de
la sélection n'envoie jamais rien : le recruteur prépare l'envoi, voit l'aperçu de chaque mail, puis confirme.

## Parcours

1. **Fiche candidat** : décision « retenu », puis carte « Entretien » → « Planifier un entretien » : en ligne (la
   visio d'INJARA, voir `docs/entretien-video.md`) ou sur site (adresse), date et heure, durée, message facultatif.
   C'est l'entretien du module vidéo, complété de ce que l'invitation annonce (durée, mode, adresse, message,
   confirmation) ; son cycle planifié → en cours → terminé ou annulé ne change pas. Une date passée est refusée ; un
   chevauchement avec un autre entretien est signalé sans bloquer. Le candidat confirme en répondant au mail ; le
   recruteur marque ensuite l'entretien « confirmé » ou le replanifie. Si la date change après l'invitation, la carte
   « Mails au candidat » propose de prévenir le candidat (mail de modification).
2. **Page du poste** :
   - « Envoyer les invitations » : candidats retenus avec un entretien planifié et daté, sans invitation envoyée ; un
     retenu sans entretien (ou sans date) est listé à part, avec la raison. Pour un entretien **en ligne**, `{lieu}`
     contient le **lien de la visio** du candidat : il faut donc que l'accès à distance soit activé, sinon le candidat
     est exclu de l'envoi avec cette raison ;
   - « Clôturer la sélection » : après confirmation, les candidatures encore « à examiner » passent à « écarté » ;
     « en attente » et « retenu » ne bougent pas ;
   - « Envoyer les réponses négatives » : candidats « écarté ».
   Chaque envoi ouvre un écran de confirmation : nombre de destinataires, aperçu du mail de chacun, exclus avec la
   raison, puis résultat ligne par ligne et « Relancer les échecs ».
3. **Carte « Mails »** de la fiche et **classement** : état de chaque mail (non envoyé, envoyé le…, échec et raison).

Toujours exclus : CV illisibles, candidatures non classées, candidats sans adresse, et ceux qui ont déjà reçu ce mail
pour ce poste. Seul « Renvoyer » (fiche, avec confirmation) envoie une seconde fois le même mail.

## Envoi

- Un mail à la fois ; chaque résultat est enregistré aussitôt (`mails_candidats` : envoyé ou échec, raison, date) et un
  échec n'arrête pas les autres.
- Destinataire : l'adresse qui a envoyé la candidature, à défaut l'email lu dans le CV.
- Réponse dans le fil du mail de candidature quand c'est possible (CV reçu par mail, compte Gmail). L'objet devient
  alors « Re: <objet du mail du candidat> » : Gmail ne range un message dans un fil que si l'objet correspond. Pour un
  CV importé à la main, ou si le fil est introuvable, c'est un nouveau mail avec l'objet du modèle.
- Texte brut UTF-8, sans pièce jointe. Les mails ne mentionnent jamais le score, le classement ni l'analyse.

## Modèles

Paramètres › Mails aux candidats : objet et texte de l'invitation et de la réponse négative, modifiables, avec
aperçu. Variables : `{civilite_nom}`, `{poste}`, `{entreprise}`, `{date}`, `{heure}`, `{duree}`, `{lieu}`, `{message}`
(toute autre variable est refusée). `{civilite_nom}` vaut le nom lu dans le CV s'il est fiable (2 à 4 mots de lettres,
sans mot de métier ni titre de section), sinon « Madame, Monsieur » ; le genre n'est jamais deviné. Une ligne réduite
à `{message}` disparaît quand le message est vide. Le nom de l'entreprise (profil entreprise) est obligatoire : il
signe les mails.

## Mode test

Tous les mails partent vers une adresse de redirection, avec le vrai destinataire au début de l'objet
(« [TEST → candidat@…] … »), hors du fil. Un envoi de test ne compte pas comme envoyé au candidat. Actif par défaut en
développement (`INJARA_ENVIRONNEMENT`, fourni par Electron), inactif dans l'application installée ; un bandeau le
signale sur tous les écrans. Actif sans adresse : l'envoi est bloqué.

## Depuis quelle boîte partent les mails

Les mails partent de la boîte de recrutement liée à INJARA, quelle que soit l'adresse du candidat (Gmail ou autre).
La boîte est connectée **une seule fois** (assistant de démarrage ou page Boîte mail, voir « Connexion de la boîte »
ci-dessous) : la même connexion sert à recevoir les candidatures et à envoyer les mails. Le transport suit :

| Boîte connectée… | Transport | Ce que l'entreprise fait |
|---|---|---|
| avec Google (Gmail, Google Workspace) | API Gmail | rien de plus : la fenêtre Google accorde lecture et envoi |
| par mot de passe (adresse pro chez un hébergeur, Yahoo…) | SMTP | rien : mêmes adresse et mot de passe que pour la lecture |

## Connexion de la boîte (une fois)

L'utilisateur donne seulement son adresse ; `services/detection_boite.py` trouve le reste, sans terme technique à
l'écran :

| Adresse | Ce qui est proposé |
|---|---|
| `@gmail.com`, ou domaine hébergé chez Google (serveurs MX Google) | « Se connecter avec Google » si la connexion Google est configurée sur le poste ; sinon mot de passe d'application, avec les étapes et un bouton vers la page Google |
| `@yahoo.*` | mot de passe d'application, étapes guidées et bouton vers la page Yahoo |
| `@outlook.*`, `@hotmail.*`, `@live.*` | explication : Microsoft n'accepte plus la connexion depuis d'autres applications |
| domaine de l'entreprise | hébergeur reconnu à ses serveurs MX (Microsoft 365, OVHcloud, Zoho, Hostinger, Gandi, Namecheap) ; sinon `imap.domaine` puis `mail.domaine` sont essayés ; en dernier recours, le serveur est demandé |

Après la connexion, l'envoi est essayé tout de suite et le résultat est affiché en clair (« Réception des
candidatures : prête », « Mails aux candidats : prêts » ou la raison). Routes : `GET /boite/detection`,
`POST /boite/google`, `POST /boite/mot-de-passe`, `GET /boite` ; code : `services/boite.py`.

Assistant de démarrage (`pages/Accueil.jsx`), ouvert après la première connexion tant qu'il n'est ni fait ni passé :
l'entreprise, la boîte, les candidatures déjà reçues, puis un récapitulatif. Chaque étape a « Plus tard ». Il ne
revient plus une fois terminé, ni si l'entreprise et la boîte sont déjà renseignées (`GET /accueil`,
`PUT /accueil/termine`).

### Envoi par SMTP (boîte liée par IMAP)

- Serveur d'envoi deviné d'après celui de lecture (`imap.domaine` → `smtp.domaine`, ports 465 puis 587) ; Gmail,
  Yahoo et Outlook sont connus d'avance. S'il ne répond pas, l'entreprise saisit le serveur et le port indiqués par son
  hébergeur (Paramètres › Mails aux candidats › « Modifier le serveur d'envoi »).
- La connexion est testée avant le premier envoi ; « Tester la connexion » la refait à la demande.
- Réponse dans le fil : l'en-tête Message-ID du mail de candidature est relu en IMAP (lecture seule).
- Une copie de chaque mail envoyé est déposée dans le dossier « Envoyés » de la boîte quand il est repérable.
- Microsoft 365 / Outlook professionnel désactive souvent l'envoi par mot de passe (« SMTP AUTH ») : l'écran le
  dit, et l'administrateur de la messagerie doit l'autoriser pour la boîte.
- Code : `services/expediteur_smtp.py`.

## Autorisation Gmail

- Une seule fenêtre Google accorde `gmail.readonly` (lecture, agent mail) et `gmail.send` (envoi). L'accord est
  rangé deux fois : dans le jeton de l'agent (qui l'utilise en lecture seule, sans changement de son côté) et dans
  `<données>/secrets/jeton_envoi_gmail.json` pour l'envoi. `gmail.readonly` suffit aussi pour l'identifiant du fil,
  les en-têtes du mail de candidature et l'adresse du compte ; `gmail.metadata` n'est pas demandé (il interdit la
  recherche dans la boîte dont l'agent a besoin).
- Le compte autorisé doit être celui qui reçoit les candidatures. Autorisation retirée, expirée, ou compte
  différent : bandeau « Reconnecter la boîte » et envoi bloqué.
- Une boîte connectée avant ce fonctionnement (lecture seule) se reconnecte une fois (Paramètres › Mails aux
  candidats › « Reconnecter la boîte »).
- Projet Google Cloud : déclarer `gmail.readonly` et `gmail.send` sur l'écran de consentement. En mode « test »
  (100 utilisateurs déclarés au plus), rien d'autre à faire ; une diffusion large demande la validation de
  l'application par Google (audit de sécurité pour `gmail.readonly`). Sans connexion Google configurée sur le poste,
  les adresses Gmail passent par un mot de passe d'application guidé.
- Mode démo (`GMAIL_MODE=fake`) : faux expéditeur, rien ne part.

## Code

| Fichier | Rôle |
|---|---|
| `services/envoi_mails.py` | Règles : éligibilité, aperçu, envoi un par un, historique, modification |
| `services/expediteur.py` | Interface de transport, message MIME, faux expéditeur |
| `services/boite.py`, `services/detection_boite.py` | Connexion de la boîte en une fois, assistant de démarrage |
| `services/expediteur_gmail.py` | API Gmail (accord Google commun à la lecture et à l'envoi) |
| `services/expediteur_smtp.py` | SMTP pour les boîtes liées par IMAP |
| `services/modeles_mail.py`, `services/reglages_mails.py` | Modèles, variables, mode test |
| `services/entretiens.py` (module vidéo) | Planification étendue : `POST /candidatures/{id}/entretiens`, `PUT /entretiens/{id}`, `PUT /entretiens/{id}/confirmation` |
| `desktop/renderer/src/mails/`, `entretiens/CarteEntretien.jsx` | Cartes de la fiche, actions du poste, écran de confirmation, planification |
