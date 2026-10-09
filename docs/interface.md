# Interface de l'application

Refonte visuelle de 2026 (branche `redesign-ui`). Le détail des choix (assets, inspirations, contrastes) est dans
`DESIGN_NOTES.md` à la racine.

## Design system

- **Tokens** : `desktop/renderer/src/styles/tokens.css`. Échelles brutes (`--nuit-*`, `--vert-*`) dérivées de
  `#031e40` et `#37bb68`, puis tokens sémantiques (`--fond`, `--surface`, `--texte-doux`, `--accent`…) redéfinis
  par thème (`data-theme="sombre"` ou `"clair"` sur `<html>`). Les composants n'utilisent que les classes
  sémantiques générées dans `styles.css` (`bg-surface`, `text-doux`, `border-trait`, `text-accent-texte`…).
- **Polices** : Paytone One (titres : h1, h2, `.titre-ecran`, `.titre-section`), PT Sans 400/700 et italiques
  (police par défaut : texte, champs, boutons, tableaux, chiffres) et Satisfy (accents décoratifs seulement :
  slogan, mot d'accueil). Variables `--police-titres`, `--police-texte`, `--police-accent` (classes `font-titres`,
  `font-sans`, `font-accent`). Paquets `@fontsource`, embarquées : aucun chargement réseau. La page candidat
  (`backend/web/candidat/polices`) et le rapport PDF (`desktop/main/polices`, en data:) en ont leur propre copie.
- **Composants** : `components/ui.jsx` (boutons, champs, cartes, badges, onglets, segments, alertes, modale),
  `components/Menu.jsx` (menu déroulant et clic droit), `components/EtatVide.jsx`, `components/Infobulle.jsx`.
- **Animations** : paquet `motion`, valeurs communes dans `components/mouvement.js` ; mouvement réduit respecté
  (`MotionConfig reducedMotion="user"` et règles CSS). Pas d'animation sur les actions au clavier fréquentes.
- **Thème** : sombre par défaut ; clair ou « comme le système » dans le menu du compte (bas de la barre latérale)
  ou la palette de commandes. Préférence propre au poste (`localStorage`).
- **Logos** : `desktop/scripts/exporter-logos.py` régénère `renderer/public/marque/` et les icônes de
  `desktop/packaging/` depuis `design-ui-ux-graphic-chart/`.

## Fenêtre

Barre de titre dessinée par l'interface (`titleBarStyle: 'hidden'`). Boutons de fenêtre : natifs sous Windows
(Window Controls Overlay), pastilles natives sous macOS, dessinés par l'interface sous Linux (la surcouche native
fait planter Electron sous Wayland). Taille minimale : 1100 × 680.

## Raccourcis clavier

| Action | Raccourci |
|---|---|
| Palette de commandes (recherche de candidats, postes, actions) | Ctrl+K (⌘K sur macOS) |
| Tableau de bord, Candidatures, Postes, Boîte mail, Profil entreprise | Ctrl+1 à Ctrl+5 |
| Créer un poste | Ctrl+N |
| Importer des CV | Ctrl+I |
| Replier la barre latérale | Ctrl+B |
| Menu d'une ligne de la liste des candidatures | clic droit ou Maj+F10 |
| Aide des raccourcis | ? |

Les raccourcis sont désactivés dans la salle d'entretien, pour ne pas la quitter par erreur.
