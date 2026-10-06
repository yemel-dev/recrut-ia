# Traitement automatique des candidatures

Chaque mail reçu par l'agent (ou chaque CV importé à la main) devient une **candidature**. INJARA la lit, en extrait
les informations utiles, la note pour chaque poste actif, la rattache au bon poste, puis affiche les 10 meilleurs
profils de chaque poste. **Le score est un indicateur : aucune candidature n'est rejetée ni masquée.**

Code : `backend/ia/` (analyse, fonctions pures), `backend/services/traitement.py` (pipeline),
`backend/services/candidatures.py` (côté recruteur). Journal : `injara.traitement`, une ligne par étape.

## Les étapes

| Étape | Ce qui est fait | Où |
|---|---|---|
| Import | Les CV de l'agent sont regroupés par mail. Le CV principal est choisi d'après le nom du fichier (`cv`, `resume`, `curriculum`) ; les autres pièces jointes sont lues comme lettre de motivation. | `traitement.importer_depuis_agent` |
| 1. Lecture | Texte du PDF (pypdf) ou du DOCX (paragraphes et tableaux). Moins de 150 caractères utiles, fichier protégé ou corrompu : **illisible**, avec un motif, jamais noté 0 en silence. | `ia/lecture.py` |
| 2. Extraction | Une seule fois par CV, sans dépendre d'un poste : contact, sections, périodes d'expérience, diplôme. Texte complet et vecteur Sentence-BERT enregistrés. | `ia/extraction.py`, `ia/diplomes.py` |
| 3. Classement | Postes actifs uniquement. Voir ci-dessous. | `ia/classement.py` |
| 4. Score | Sur 100, pour chaque poste actif, avec le détail. | `ia/scoring.py`, `ia/competences.py` |
| 5. Top 10 | Candidatures rattachées au poste, triées par score. | `services/candidatures.py` |

Le pipeline tourne dans un fil de fond pendant la session. Il se déclenche à la connexion, à l'arrivée de nouveaux CV
et à chaque modification d'un poste ; dans ce dernier cas, les candidatures sont **renotées sans relire les CV**.

## Extraction

- **Expérience** : seules les périodes de la section expérience comptent ; les dates d'études n'entrent jamais dans
  le total. Formats lus : « Février 2025 – Présent », « Sept. 2021 à février 2023 », « 09/2021 - 02/2023 »,
  « depuis janvier 2026 », « 2019 - 2021 » (année seule : comptée à partir de juin). Les périodes qui se chevauchent
  sont fusionnées. Une date future est arrêtée à aujourd'hui.
- **Stages** (stage, stagiaire, intern, ou section « Stages ») : comptés à part, hors du total. L'alternance compte
  comme de l'expérience.
- **Diplôme** : le plus élevé **obtenu**, lu dans la section formation uniquement. Un diplôme « en cours », « en
  préparation », ou dont la fin est dans le futur ne compte pas. « Scrum Master », « Masterclass » ne sont pas des
  diplômes. Correspondances : Bac+5, ingénieur, MBA, DEA, DESS = Master ; Bac+3/+4, Bachelor, maîtrise, M1,
  ingénieur des travaux = Licence ; BTS, DUT, DTS, HND, Bac+2 = BTS.
- **Contact** : nom (premières lignes, sinon nom de l'expéditeur), email, téléphone.

## Score sur 100

| Critère | Poids par défaut | Calcul |
|---|---|---|
| Compétences | 40 | Part des compétences requises trouvées dans le texte du CV (casse, accents, ponctuation ignorés ; expressions en plusieurs mots ; synonymes courants dans `ia/competences.py`) |
| Expérience | 25 | Expérience retenue / expérience demandée, plafonnée à 100 % |
| Formation | 20 | Niveau atteint ou dépassé = 100 %, puis −40 points par niveau manquant (60, 20, 0) |
| Adéquation globale | 15 | Similarité Sentence-BERT entre le CV et la description du poste, ramenée sur 100 entre `SIMILARITE_PLANCHER` et `SIMILARITE_PLAFOND` |

Les poids se règlent par poste (formulaire du poste, total 100). Sans modèle Sentence-BERT, l'adéquation est ignorée,
les trois autres poids sont recalculés pour totaliser 100, et l'interface le signale.

## Classement

1. **Poste cité dans le mail** (objet, corps ou lettre de motivation) : référence interne ou intitulé → assignation
   directe. Si plusieurs postes sont cités : la référence l'emporte, puis l'intitulé le plus long ; s'il reste une
   ambiguïté, statut « à vérifier ».
2. **Sinon**, le poste de meilleure **pertinence** est retenu. La pertinence n'utilise que les compétences et
   l'adéquation : l'expérience et le diplôme ne disent rien du métier (un comptable expérimenté et diplômé obtient un
   score honorable sur un poste de développeur, mais une pertinence quasi nulle).

| Constante (`ia/classement.py`) | Valeur | Effet |
|---|---|---|
| `SEUIL_NON_CLASSE` | 15 | Pertinence inférieure : « non classée » |
| `SEUIL_PERTINENCE_FAIBLE` | 40 | Pertinence inférieure : « à vérifier » |
| `ECART_POSTES_PROCHES` | 8 | Deux postes à moins de 8 points : « à vérifier » |

Le recruteur peut changer le poste depuis la fiche de la candidature. **Un choix manuel n'est jamais écrasé** par un
nouveau calcul ; « Revenir au classement automatique » l'annule.

## Modèle Sentence-BERT

`paraphrase-multilingual-MiniLM-L12-v2`, chargé une seule fois depuis `modeles/` (ou `INJARA_MODELES_DIR`), hors
ligne. Le chargement (jusqu'à deux minutes au premier lancement) se fait en arrière-plan dès l'ouverture de session :
en attendant, les CV sont lus et notés sans l'adéquation, puis encodés et renotés automatiquement quand le modèle est
prêt. `GET /traitement/etat` renvoie `adequation.en_chargement` pendant ce temps. Installation, à faire une fois :

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-ia.txt
python -m backend.ia.telecharger_modele
```

Sous Windows, torch exige le **runtime Microsoft Visual C++ 2015-2022 (x64)**. S'il manque, l'adéquation est
désactivée avec ce motif (le reste du traitement fonctionne). L'installeur d'INJARA devra l'embarquer.

Les bornes `SIMILARITE_PLANCHER` (0,15) et `SIMILARITE_PLAFOND` (0,65) sont provisoires : les caler avec
`python -m backend.ia.calibrer` (similarités brutes des CV fictifs pour plusieurs postes).

## Tests

`backend/tests/fixtures/cv/` contient des CV fictifs en texte ; `fixtures/fabrique.py` en fait de vrais PDF (dont un
PDF scanné, image seule) et DOCX. `test_ia_extraction.py`, `test_ia_scoring.py` et `test_traitement.py` couvrent
notamment : « Février 2025 – Présent », dates d'études, « Bac+5 », « Scrum Master », « Master en cours »,
« Django REST Framework », CV de comptable sans rapport, mail sans référence, PDF scanné, choix manuel conservé,
renotation sans relecture et top 10.
