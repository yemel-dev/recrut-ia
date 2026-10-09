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
(Unbounded, large, pour les titres et les scores) et sur l'IA, signalée par un liseré vert lumineux et une pulsation discrète.
