# Mission : refonte UI/UX de la salle d'entretien vidéo INJARA

Tu interviens sur le frontend existant d'INJARA, une application de recrutement développée avec React 19, Vite, Tailwind CSS 4, Lucide React et Electron.

Je veux une refonte visuelle et ergonomique ambitieuse de la page d'entretien vidéo, inspirée des qualités de Google Meet, mais avec une identité visuelle propre à INJARA.

**Il ne s'agit pas de modifier quelques couleurs ou d'arrondir les cartes. Il faut repenser l'expérience utilisateur de cette page pour lui donner l'apparence et la sensation d'une véritable application de visioconférence professionnelle.**

## 1. Commence par comprendre le code existant

Avant toute modification :

- Lis intégralement `renderer/src/pages/Entretien.jsx`.
- Examine `renderer/src/entretiens/useSalle.js` pour comprendre le fonctionnement de la salle WebRTC.
- Examine `renderer/src/entretiens/enregistreur.js` et `renderer/src/entretiens/regard.js`.
- Examine `renderer/src/entretiens/testTurn.js`.
- Examine `renderer/src/components/Disposition.jsx`, `renderer/src/components/ui.jsx`, `renderer/src/styles.css` et les fichiers de configuration pertinents.
- Vérifie comment le candidat rejoint la salle et comment le frontend reçoit son consentement.
- Identifie les composants, fonctions, états React, événements, appels API et mécanismes de nettoyage dont dépend la page.

Ne suppose pas qu'une fonctionnalité est inutile simplement parce qu'elle n'est pas directement visible dans l'interface.

Après cette inspection, présente brièvement les fichiers que tu comptes modifier et les principaux risques de régression. Puis réalise la refonte. Ne t'arrête pas à une simple proposition de design.

## 2. Direction artistique

Je veux une interface :

- immersive, moderne, élégante et professionnelle ;
- inspirée de Google Meet pour l'organisation de la salle et de ses commandes ;
- suffisamment distinctive pour qu'on reconnaisse une interface INJARA ;
- agréable à utiliser pendant un entretien de plusieurs dizaines de minutes ;
- visuellement cohérente, avec une hiérarchie claire entre la vidéo, les commandes et les informations secondaires.

Respecte l'identité de marque existante :

- bleu marine INJARA : `#031E40` ;
- vert INJARA : `#00BF63`.

Tu peux introduire des nuances de bleu nuit, des gris profonds, des surfaces légèrement contrastées, des bordures discrètes et des effets de profondeur subtils.

Privilégie une salle de visioconférence sombre, immersive et confortable, sans transformer toute l'application en interface sombre si cela n'est pas nécessaire.

Évite le rendu générique composé de cartes blanches empilées sur un fond gris, les grands espaces vides, les boutons ordinaires sans hiérarchie, les décorations inutiles et les animations excessives.

## 3. Repenser la structure de la page

La salle vidéo doit devenir l'élément central de l'expérience.

### A. Barre supérieure

Crée une barre compacte qui peut contenir :

- le logo ou le nom INJARA ;
- le nom du candidat et, si pertinent, le poste concerné ;
- le statut réel de l'entretien ;
- un indicateur de connexion compréhensible ;
- un accès aux informations secondaires ;
- un moyen clair de revenir à la fiche de candidature.

La barre doit rester discrète pour ne pas concurrencer la vidéo.

### B. Zone vidéo principale

La vidéo distante doit occuper la plus grande partie de l'espace disponible.

Lorsque le candidat est connecté, affiche son flux vidéo de façon naturelle, avec un dimensionnement adapté au conteneur et sans déformation de l'image.

Améliore la présentation de la vidéo locale du recruteur :

- vignette positionnée dans un coin de la vidéo principale ;
- proportions cohérentes ;
- coins arrondis et contour subtil ;
- nom du participant si pertinent ;
- effet miroir conservé uniquement pour l'aperçu local si approprié.

Lorsque le candidat n'est pas encore connecté, ne laisse pas un grand rectangle vide. Crée un véritable écran d'attente avec une composition soignée, un message contextuel, un indicateur de progression lorsque cela correspond à un état réel, et des informations utiles.

Prévois des présentations distinctes pour :
- la salle fermée ;
- l'ouverture de la salle ;
- l'attente du candidat ;
- la présence du candidat pendant la négociation WebRTC ;
- la connexion vidéo établie ;
- la perte de connexion ou une erreur ;
- l'entretien terminé.

Ne présente jamais une connexion comme établie si le flux vidéo n'est pas réellement reçu.

### C. Barre de commandes inspirée de Google Meet

Crée une barre de commandes facilement identifiable, idéalement en bas de la salle.

Les commandes doivent être organisées selon leur importance et leur contexte.

Conserve les fonctionnalités existantes d'ouverture et de fermeture de salle, de démarrage de l'entretien et de fin d'entretien.

Ajoute ou améliore les commandes visuelles uniquement lorsque leur fonctionnement réel est disponible.

Important : examine les capacités actuelles de `useSalle.js` avant d'ajouter des boutons pour le micro ou la caméra.

Si le code existant ne permet pas de couper et de réactiver individuellement le micro ou la caméra, ne crée pas de faux boutons fonctionnels. Tu peux implémenter cette fonctionnalité si tu la maîtrises, en respectant le cycle de vie des pistes média et la connexion WebRTC, mais n'affaiblis jamais le fonctionnement existant. Sinon, conserve les commandes réellement disponibles et signale ce qui nécessiterait un travail technique séparé.

Le bouton de fin d'entretien doit être visuellement distinct et déclencher la confirmation déjà existante.

Utilise des icônes Lucide cohérentes, des infobulles accessibles, des états visuels explicites et des zones cliquables confortables.

### D. Panneau latéral d'informations

Les informations administratives ne doivent plus réduire inutilement la zone vidéo.

Crée un panneau latéral repliable, un tiroir ou une organisation équivalente pour présenter les fonctionnalités secondaires déjà existantes :

- invitation du candidat et lien de connexion ;
- activation ou désactivation de l'accès à distance ;
- date et informations de l'entretien ;
- état du consentement à l'enregistrement ;
- état de l'enregistrement ;
- informations de connexion et aide en cas de problème ;
- indicateurs de regard et de vigilance, selon le statut de l'entretien ;
- rapport et export de la vidéo après l'entretien.

Choisis une organisation logique plutôt que de tout afficher simultanément.

Le panneau doit être accessible sans quitter la salle et ne doit pas masquer excessivement la vidéo. Sur les petits écrans, il peut devenir un tiroir ou un panneau superposé.

Conserve la logique existante de `CarteInvitation` et de `ReseauTurn`, y compris les appels API, la gestion du tunnel, la copie du lien, les erreurs et la configuration TURN.

## 4. Préserver les fonctionnalités existantes

C'est une contrainte absolue.

Ne supprime pas et ne simule pas les fonctionnalités suivantes :

- chargement de l'entretien et de la candidature ;
- actualisation des informations permettant de détecter le consentement du candidat ;
- ouverture et fermeture de la salle ;
- négociation WebRTC et réception des flux vidéo ;
- reconnexion du candidat ;
- démarrage et terminaison de l'entretien ;
- confirmation avant la fin définitive ;
- enregistrement conditionné au consentement ;
- arrêt correct de l'enregistrement avant la terminaison ;
- analyse du regard et du mouvement de la tête ;
- indicateurs de vigilance ;
- génération et export du rapport PDF ;
- export de l'enregistrement ;
- invitation distante, activation du tunnel et expiration du lien ;
- configuration et test TURN ;
- affichage des erreurs et notifications existantes ;
- nettoyage des ressources média lorsque la page est quittée.

Conserve les routes, les endpoints API, les noms des champs métier, les contrats de `window.injara` et les règles de sécurité existantes.

N'invente aucun endpoint et ne modifie pas le backend pour contourner un problème d'interface.

Respecte le consentement du candidat. Aucun enregistrement ni traitement nouveau ne doit être déclenché simplement parce que tu as modifié la présentation de la page.

Ne retire pas les explications qui précisent les limites des indicateurs de regard et de vigilance.

## 5. Architecture et qualité du code

Travaille avec les dépendances et les conventions déjà présentes.

- Réutilise les composants et utilitaires existants lorsqu'ils sont adaptés.
- Tu peux créer des composants dédiés à la présentation de la salle si cela rend le code plus clair.
- Sépare autant que nécessaire la présentation visuelle de la logique métier.
- Évite de réécrire entièrement `useSalle.js` si une refonte de la présentation suffit.
- Ne remplace pas le système de navigation existant.
- Ne change pas arbitrairement les couleurs globales de toutes les pages.
- Évite les dépendances supplémentaires, sauf nécessité réelle et justification.
- Ne crée pas un prototype isolé qui ne fonctionne pas avec les données réelles.
- Respecte l'accessibilité : navigation au clavier, libellés accessibles, contrastes lisibles et états de focus visibles.

Le résultat doit fonctionner dans l'application Electron existante, pas uniquement dans une maquette HTML.

## 6. Responsive design et qualité visuelle

La salle doit être adaptée aux différentes dimensions de fenêtre.

Sur grand écran :
- vidéo prioritaire ;
- barre de commandes bien positionnée ;
- informations secondaires dans un panneau compact.

Sur fenêtre réduite :
- vidéo toujours exploitable ;
- commandes accessibles ;
- panneau latéral repliable ;
- aucun débordement horizontal gênant.

Sur les écrans tactiles, si le contexte d'utilisation le permet, prévois des zones d'interaction suffisamment grandes.

Utilise des transitions courtes et discrètes pour l'ouverture des panneaux et les changements d'état. Ne fais pas clignoter l'interface et ne simule pas d'activité réseau.

## 7. Tests et vérifications obligatoires

Après les modifications :

1. Exécute le script de build approprié depuis le bon dossier du projet.
2. Corrige les erreurs introduites par tes modifications.
3. Vérifie les imports, les classes Tailwind, les composants et les états conditionnels.
4. Examine les transitions entre salle fermée, salle ouverte, attente, connexion, entretien en cours et entretien terminé.
5. Vérifie que les actions de fin d'entretien, d'enregistrement, d'export et d'invitation restent reliées à leurs fonctions réelles.
6. Vérifie les comportements en fenêtre étroite et large, au moyen des outils disponibles.
7. Si tu ne peux pas tester un scénario nécessitant un véritable candidat connecté, indique-le clairement plutôt que de prétendre que le test a réussi.

Ne modifie pas les données de production et ne déclenche pas de véritable enregistrement pour effectuer les vérifications.

## 8. Compte rendu final

À la fin, fournis :

- les fichiers modifiés ;
- les principales améliorations UX réalisées ;
- les fonctionnalités conservées ;
- les commandes de test exécutées et leurs résultats ;
- les points qui restent à tester manuellement ;
- les éventuelles fonctionnalités que tu n'as pas pu implémenter sans changement technique supplémentaire.

**Critère de réussite :** lorsqu'on ouvre un entretien dans INJARA, on doit avoir l'impression d'entrer dans une véritable salle de visioconférence professionnelle, et non de consulter une fiche administrative contenant un rectangle vidéo.

Prends les décisions de design nécessaires sans me demander de choisir chaque couleur, espacement ou icône. Je te confie la direction artistique, mais pas le droit de casser les fonctionnalités existantes.