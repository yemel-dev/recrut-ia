# INJARA : notes de design (refonte `redesign-ui`)

Document de travail de la refonte visuelle de l'application de bureau. Il sera complété à chaque étape
(inspirations, skills, typographie, palette dérivée, changements).

## 1. Inventaire du dossier `design-ui-ux-graphic-chart/`

21 fichiers : 14 logos PNG (4500 × 4500 px, fond transparent) et 7 références d'inspiration WebP.
Aucun SVG, aucun PDF, **aucune charte typographique** : le choix des polices reste ouvert (voir § 4).

### Logos

Le logo se compose d'un **symbole** (étoile à huit branches autour d'un octogone, tracé au trait épais,
évoquant les motifs géométriques type zellige) et d'un **logotype** « Injara » en minuscules arrondies
(terminaisons douces, point du « j » détaché en couleur).

| Fichier | Contenu | Couleurs relevées | Usage prévu |
|---|---|---|---|
| `21.png`, `22.png` | Logo vertical complet : symbole vert + « Injara » bleu nuit, point vert | `#00bf63`, `#091e3e` | Écran de démarrage (thème clair). `22` ≈ copie de `21` (quelques pixels diffèrent) |
| `32.png` | Logo vertical complet, tout blanc | `#ffffff` | Écran de démarrage, connexion (thème sombre) |
| `33.png` | Logo vertical complet, tout bleu nuit | `#031e40` | Exports, documents clairs monochromes |
| `34.png` | Logo vertical complet, tout noir | `#000000` | Impression monochrome (non utilisé dans l'app) |
| `23.png` | Symbole seul, vert | `#00bf63` | **Icône de l'app**, barre latérale, loader IA |
| `24.png` | Symbole seul, bleu nuit | `#031e40` | Symbole sur fond clair |
| `25.png` | Symbole seul, noir | `#000000` | Non utilisé |
| `26.png` | Symbole seul, blanc | `#ffffff` | Symbole sur fond sombre (filigranes) |
| `27.png` | Logotype horizontal « Injara » bleu nuit, point vert | `#091e3e`, `#00bf63` | Barre de titre / connexion (thème clair) |
| `28.png` | Logotype horizontal, tout blanc | `#ffffff` | Barre de titre / connexion (thème sombre) |
| `29.png` | Logotype horizontal, tout bleu nuit | `#0c1e3c` | Variante monochrome |
| `30.png` | Logotype vert, point bleu nuit | `#37ba68`, `#031e40` | Variante (non prévue) |
| `31.png` | Logotype vert, point vert | `#37ba68` | Variante (non prévue) |

Remarques :
- Le vert du logotype (`30`, `31`) est `#37ba68`, légèrement différent du vert officiel `#00bf63` (symbole).
  Les logos sont utilisés **tels quels** ; l'interface suit la palette officielle `#00bf63`.
- Le bleu nuit varie de `#031e40` à `#0c1e3c` selon les fichiers (antialiasing / export) : référence `#031e40`.
- Les PNG font 4500 px avec de grandes marges transparentes : ils seront **recadrés et réduits** (WebP/PNG aux
  tailles utiles) sans retouche du dessin. Variantes manquantes à produire par simple export : icône d'application
  16 → 1024 px et `.ico`, symbole sur pastille bleu nuit pour la barre des tâches.
- L'app embarque déjà `renderer/public/symbol-green.webp`, `injara-horizontal-navy.webp` et `icon.png` : ils seront
  remplacés par des exports de ces fichiers source.

### Références d'inspiration

| Fichier | Produit montré | Ce que j'en retiens pour INJARA |
|---|---|---|
| `interview.webp` | « Hirebyte » : salle d'entretien vidéo | Vidéo principale + vignette, barre de commandes flottante en pastilles rondes, colonne droite à onglets (questions / timeline), **bloc « résumé IA » distingué par un fond teinté et une icône étincelle** |
| `cfd30dc0….webp` | « Talently » : liste de candidats | Tableau dense et aéré, onglets de statut avec compteurs, badges de statut à pastille colorée, menu « … » contextuel par ligne (Voir, Planifier un entretien…), recherche globale `⌘K` dans la barre du haut, bouton IA dédié |
| `original-0494….webp` | « Hirezy » : fiche candidat | Colonne profil à gauche (identité, % de correspondance, action principale), **progression du recrutement en chevrons**, sections Overview / Expérience en colonne centrale |
| `original-7f1f….webp` | « Talentfly » : recherche de personnes | Filtres en colonne gauche avec puces supprimables, liste en tableau à lignes hautes |
| `original-eb96….webp` | « Workline » : candidats en trois colonnes | **Sidebar sombre + contenu clair**, navigation par étapes avec pastilles de couleur et compteurs, liste maître / détail, accent vert vif sur les actions |
| `login page.webp` | « Tuga's App » : connexion | Écran scindé : formulaire épuré à gauche, panneau illustré à droite ; champs en pilule |
| `login page 1.webp` | « Hotelook » : connexion | Même découpe scindée, panneau de droite avec citation + illustration au trait, bouton principal pleine largeur |

Direction commune : interfaces claires et très aérées, une sidebar, des tableaux denses mais lisibles, un accent
unique fort, des blocs IA identifiables, connexion en écran scindé. INJARA garde ces structures mais les porte dans
son identité (bleu nuit dominant en thème sombre, vert en accent, géométrie de l'étoile à huit branches).

## 2. Skills installés (`.claude/skills/`)

| Skill | Source | Pourquoi | Ce que j'en applique |
|---|---|---|---|
| `frontend-design` | Anthropic, dépôt officiel `anthropics/skills` (identique au catalogue `claude-plugins-official`) | Imposé par le brief | Choix typographiques assumés, une seule audace par écran, pas de « kit SaaS » de cartes identiques, pas de libellés en capitales espacées, textes d'interface clairs et actifs |
| `animate` | Emil Kowalski (`emilkowalski/skill`, MIT), auteur de Sonner et Vaul | Construction des animations Motion | Ne pas animer ce qui sert 100 fois par jour (palette `Ctrl+K`, raccourcis), `transform`/`opacity` uniquement, courbes fortes (`--ease-out: cubic-bezier(0.23,1,0.32,1)`), UI < 300 ms, jamais `scale(0)`, survols conditionnés à `(hover: hover) and (pointer: fine)` |
| `review-animations` | Emil Kowalski (même dépôt) | Relecture des animations avant chaque commit | Grille de dix règles (justification, fréquence, origine, interruption, accessibilité) |
| `web-design-guidelines` | Vercel (`vercel-labs/agent-skills`), règles tirées de `vercel-labs/web-interface-guidelines` | Accessibilité et typographie (pas de skill officiel dédié à ces deux sujets) | Focus visibles, `aria-live` sur les toasts, `…` et guillemets typographiques, `tabular-nums`, `text-wrap: balance`, `color-scheme`, `<select>` natifs colorés explicitement, confirmations avant suppression |

Écartés : `webapp-testing` (Anthropic) car il pilote un navigateur, pas Electron ; les skills d'accessibilité et de Motion
trouvés sur des annuaires communautaires (claudskills, openskillindex…) car leur source n'est pas vérifiable.
Aucun skill ne contient de script exécutable : ce sont uniquement des consignes en Markdown.

## 3. Inspirations

| Référence | Ce que je retiens | Adaptation pour INJARA |
|---|---|---|
| [motion.dev](https://motion.dev/) (v14) | `AnimatePresence` pour les sorties, `layout` pour les réordonnancements, `stagger`, ressorts | Seule bibliothèque d'animation. Transitions d'écran, modales, tiroirs, réordonnancement du classement |
| [prompt-motion.com](https://prompt-motion.com/) | Galerie de vidéos de motion design classées (Product UI, Shapes, Charts…) | Catégories « Product UI » et « Shapes » : loader géométrique tiré du symbole, apparition des jauges de score. Pas de particules : trop chargé pour un outil de travail |
| [Awwwards](https://www.awwwards.com/inspiration_search/) | Les sites primés du mois sont surtout des vitrines (portfolios, marques) ; la page ne montre ni captures ni tableaux de bord | Retenu seulement l'idée d'un **moment orchestré** unique (écran de connexion) plutôt que des effets partout |
| [itshover](https://itshover.com/icons) (code lu sur GitHub, Apache-2.0) | Icônes SVG animées au survol avec `motion/react` (`useAnimate`) : rotation de l'icône « actualiser », étincelles qui scintillent, couvercle de corbeille qui se soulève | Réinterprété **sans copier** : les icônes Lucide de l'app reçoivent un geste propre à leur sens (rotation pour actualiser, flèche qui avance, envoi qui décolle, étincelle IA qui pivote), en CSS (moins coûteux que du JS pour un survol), désactivé en mouvement réduit |
| Linear, [« Behind the latest design refresh »](https://linear.app/now/behind-the-latest-design-refresh) | « Ne réclame pas une attention que tu n'as pas méritée » : sidebar atténuée de quelques niveaux, séparateurs adoucis (« structure ressentie, pas vue »), moins d'icônes et plus petites, actions d'en-tête toujours au même endroit | Sidebar en bleu nuit 950 plus sombre que la zone de travail, traits à faible contraste, actions d'écran toujours en haut à droite |
| Raycast, Arc (connaissance générale, non consultés en ligne) | Palette de commandes instantanée et sans animation ; barre latérale qui se replie | Palette `Ctrl+K` sans animation d'ouverture (cohérent avec `animate`) ; sidebar repliable |
| Recherche Dribbble / Behance (ATS, salles vidéo IA) | Peu de résultats exploitables par la recherche : surtout des fiches de services. Motifs récurrents : score de correspondance mis en avant, file de revue humaine, scène vidéo sombre avec commandes en pastilles | Score en jauge annulaire avec chiffres tabulaires, rappel constant que la décision reste humaine (déjà dans l'app), scène vidéo bleu nuit |

Conclusion de direction artistique : **« la constellation »**. Le symbole à huit branches d'INJARA est le seul ornement :
il sert de loader IA, de filigrane sur l'écran de connexion et d'état vide. Tout le reste est sobre (surfaces bleu
nuit étagées, traits doux, une seule couleur d'accent). L'audace se concentre sur la typographie d'affichage
(Paytone One, ronde et dense, pour les titres) et sur l'IA, signalée par un liseré vert lumineux et une pulsation discrète.

## 4. Typographie

Trois polices, trois rôles (refonte de la connexion, octobre 2026) :

- **Paytone One** (400 seulement), pour les grands titres : h1, h2, `.titre-ecran`, `.titre-section`, nom de
  l'entreprise. Ronde et dense, elle prolonge le logotype « Injara ». `font-synthesis: none` : jamais de faux gras.
- **PT Sans** (400 et 700, avec italiques), police par défaut : texte, libellés, champs, boutons, tableaux,
  menus et chiffres (`.chiffre` = PT Sans 700). Ses chiffres sont tabulaires d'origine (chasse fixe), d'où des
  colonnes alignées sans `tnum`.
- **Satisfy** (400), accents décoratifs uniquement : slogan, mot d'accueil. Jamais pour du texte courant.

Toutes sont embarquées en woff2 (paquets `@fontsource`, sous-ensembles latin et latin étendu), jamais chargées
depuis un CDN, et la CSP l'impose (`font-src 'self'`). Vérification sur les fichiers : tous les caractères
« é è ê ë à â ç ô û ù î ï œ É È À Ç Œ « » ’ … » sont présents dans les trois polices.

Échelle de bureau (base 14 px), interlignes en px :

| Rôle | Taille | Interligne | Police, graisse, approche |
|---|---|---|---|
| Légende, étiquette (`text-xs`, `.etiquette`) | 12 | 16 | PT Sans 400 |
| Petit texte, métadonnées (`text-sm`) | 13 | 18 | PT Sans 400 |
| Corps (`text-base`) | 14 | 20 | PT Sans 400 |
| Titre de section (`.titre-section`) | 16 | 22 | Paytone One 400 |
| Sous-titre (`text-xl`) | 20 | 26 | — |
| Titre d'écran (`.titre-ecran`) | 24 | 30 | Paytone One 400 |
| Chiffre de statistique (`.chiffre text-3xl`) | 32 | 36 | PT Sans 700, tabulaire |
| Grand chiffre (`text-4xl`) | 44 | 48 | PT Sans 700 |

Pas de libellés en capitales espacées (l'ancienne interface en avait sur toutes les étiquettes) : étiquettes en
casse normale, plus petites et plus douces.

## 5. Palette dérivée et contrastes

Échelles : celles du brief, complétées par `nuit-850 #062548`, `nuit-500 #3a6aad`, `nuit-400 #5d88c4`,
`nuit-200 #b8cde8` et **`vert-800 #00733b`**. Ce dernier est un écart au brief : le vert 700 `#008a47` ne donne
que 4,44:1 sur blanc, sous le seuil AA de 4,5. Le vert 800 sert donc au texte vert en thème clair.

| Token | Sombre | Clair |
|---|---|---|
| Chrome (barres, en retrait) | `#010d1f` (nuit 950) | `#e9eff7` |
| Fond de la zone de travail | `#031e40` (nuit 900) | `#f5f8fc` |
| Surface (cartes, tableaux) | `#072648` | `#ffffff` |
| Surface 2 (menus, modales) | `#0b3160` | `#ffffff` + ombre |
| Texte fort | `#f0f5fb`, 13,9:1 sur surface | `#031e40`, 16,6:1 |
| Texte | `#c9d8ec`, 10,5:1 | `#23395a`, 11,6:1 |
| Texte doux | `#8fa9cc`, 6,3:1 | `#4d6587`, 5,9:1 |
| Texte tenu (indications de champ vide, désactivé) | `#6c88ae`, 4,2:1 | `#61779a` |
| Accent (boutons, actif, IA) | `#00bf63` | `#00bf63` |
| Texte vert | `#2ed384`, 7,8:1 | `#00733b`, 5,5:1 |
| Texte sur bouton vert | `#031e40`, 6,8:1 | `#031e40`, 6,8:1 |
| Danger, alerte, info | `#ff7a7a`, `#f5b94a`, `#7fb0ff` | `#c0292b`, `#8a5300`, `#1b4f93` |

Le blanc sur le vert ne passe pas (2,4:1) : les boutons verts ont un texte bleu nuit. Le vert reste un accent
(boutons principaux, élément actif, IA, succès), jamais une grande surface.

## 6. Mouvement

Motion (`motion` 14, via `LazyMotion` + `m`), règles du skill `animate` :

- courbes : `cubic-bezier(0.23, 1, 0.32, 1)` (entrées et sorties), `cubic-bezier(0.32, 0.72, 0, 1)` (tiroirs) ;
- durées : 150, 220 et 300 ms. Seules l'apparition du symbole sur l'écran de connexion (1,1 s) et la jauge de
  score (0,9 s) dépassent, car elles sont rares ;
- aucune animation sur la palette `Ctrl+K`, les raccourcis ou le repli de la barre latérale (actions au clavier,
  très fréquentes) ;
- `transform` et `opacity` uniquement, sauf le dépliage du détail d'un score (hauteur, 200 ms) ;
- survols animés seulement à la souris (`@media (hover: hover) and (pointer: fine)`) ;
- mouvement réduit : plus de déplacement ni de boucle décorative, seuls les fondus restent.

Moments animés :
- apparition des écrans ;
- modales (`@starting-style`, sans JavaScript) ;
- menus et notifications ;
- cascade des listes ;
- jauges de score et barres de critères ;
- « l'IA analyse » (pulsation et reflet verts) ;
- confirmation « Décision enregistrée » ;
- zone de dépôt des CV ;
- icônes animées au survol (attribut `data-geste`).

## 7. Identité

- Logos utilisés tels quels, recadrés et réduits par `desktop/scripts/exporter-logos.py`. Aucun redessin : je
  n'ai pas vectorisé le logo, faute de SVG fourni.
- Icône d'application : symbole vert sur carré arrondi bleu nuit, de 16 à 1024 px, `icon.png` et `icon.ico`
  (l'installeur Windows utilise maintenant le `.ico`).
- Le symbole à huit branches sert de chargement (rotation lente), de filigrane de l'écran de connexion et d'état
  vide.
- Icônes : Lucide (déjà présent), aucun emoji.

## 8. Ce qui a changé

| Écran | Changements | Commit |
|---|---|---|
| Shell | Barre de titre sur mesure ; barre latérale repliable ; barre d'état (boîte mail, moteur d'analyse, hors ligne) ; palette `Ctrl+K` avec recherche de candidats et de postes ; raccourcis ; menu du compte avec le thème ; notifications animées ; lien d'évitement « Aller au contenu » | `ui: design system…` |
| Accès | Écran scindé avec panneau de marque ; clé de récupération restylée | `ui: refonte des écrans d'accès` |
| Tableau de bord | Flux des CV avec répartition, meilleures candidatures, postes actifs, entretiens prévus, actions rapides ; correction de « La boîte null est liée » | `ui: refonte du tableau de bord` |
| Candidatures | Filtres segmentés, tableau dense avec initiales, menu contextuel (fiche, CV, copier l'email), navigation clavier, zone de dépôt, états vides | `ui: refonte des candidatures` |
| Fiche | Jauge de score animée, blocs IA signalés, frise des expériences, confirmation de décision | `ui: refonte de la fiche candidature` |
| Postes | Liste avec menu d'actions, détail avec statut segmenté, classement à détail dépliable, jauge des pondérations, barre d'actions collante | `ui: refonte des postes…` |
| Boîte mail | Passage aux tokens (cartes de choix, tableaux, sections repliables) | `ui: refonte de la boîte mail…` |
| Profil entreprise | Carte d'identité (monogramme, secteur, ville) | `ui: refonte du profil entreprise` |
| Salle d'entretien | Bleu nuit au lieu d'anthracite, couleurs codées en dur remplacées ; l'écran de fin suit le thème | `ui: refonte de la salle d'entretien…` |
| Page candidat | Couleurs, polices et logo d'INJARA ; 2 routes publiques en liste fermée | `ui: refonte de la page candidat` |

Logique inchangée : les appels `api.*` et `window.injara.*`, les routes, les états et les formulaires sont ceux
d'avant. Ajouts côté processus principal (fenêtre et thème) et côté backend (polices et logo de la page candidat)
seulement.

## 9. Vérification

- `npm run build` passe à chaque commit ; `pytest` : 458 tests verts.
- Chaque écran a été lancé dans l'application (données de démo : 3 postes, 13 candidatures, entretiens) et
  capturé en 1280 × 720 et 1100 × 680, en thèmes sombre et clair. Console : aucune erreur ni avertissement.
- Clavier : tabulation avec focus visible, `Ctrl+1` à `Ctrl+5`, `Ctrl+N`, `Ctrl+K` puis recherche et Entrée, `?`.
- Mouvement réduit émulé : interface utilisable, sans déplacement.

## 10. Points à valider

1. **Barre de titre sous Windows** : je n'ai pu tester que Linux. Sous Windows, ce sont les boutons natifs
   par-dessus la page qui s'affichent ; à vérifier sur un vrai poste, ainsi que l'aimantation des fenêtres de
   Windows 11 au survol du bouton « agrandir ».
2. **Linux / Wayland** : la surcouche native de boutons fait planter Electron sur ton poste. J'ai donc dessiné
   les boutons dans l'interface sous Linux. Plus généralement, les fenêtres Electron avec cadre natif plantent
   sur ce poste sous Wayland ; ça ne concerne plus INJARA, mais c'est bon à savoir.
3. **Vert du logotype** `#37ba68` (fichiers 30 et 31), différent du vert officiel `#00bf63` : je ne l'ai pas
   utilisé. À harmoniser dans la charte ?
4. **Taille minimale** de fenêtre portée de 960 × 640 à 1100 × 680.
5. **Salle d'entretien en bleu nuit**, ton choix ; elle reste sombre en thème clair, comme les outils de visio.
6. **Page candidat** passée en sombre (elle était claire) pour l'identité de marque.
7. **Taille du JavaScript** : 618 Ko (188 Ko compressés), contre 437 Ko avant (Motion et les nouveaux
   composants). Sans effet notable pour une application chargée depuis le disque.
8. **Polices** : Paytone One sert aussi aux titres de section (h2, 16 px) ; si elle paraît trop présente en petit
   corps, il suffit de rendre `.titre-section` à PT Sans 700.
