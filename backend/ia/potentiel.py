"""Indicateur de potentiel (module 4) : règles explicites, pas un modèle prédictif.

Fonctions pures : elles reçoivent les données du CV (texte déjà lu, diplôme retenu) et le niveau demandé par le poste,
et ne touchent ni aux fichiers ni à la base. L'indicateur est affiché à côté du score sans jamais le modifier.

Cinq signaux, notés 0, 1 ou 2 selon les seuils nommés ci-dessous, ou « non évaluable » faute de données (le signal est
alors exclu du calcul, ce n'est pas une mauvaise note) :
1. progression de carrière : niveau du premier intitulé de poste comparé au plus récent ;
2. diversité des compétences : éléments listés dans les sections compétences et langues, et familles représentées ;
3. stabilité : durée moyenne par emploi, hors stages ;
4. formation face au poste : diplôme retenu comparé au niveau demandé ;
5. leadership et initiative : mots-clés regroupés en familles (encadrement, projet, création, certification, projets
   personnels).

Niveau : ratio = somme des notes / (2 × nombre de signaux évaluables), puis RATIO_* ; moins de SIGNAUX_MIN signaux
évaluables : « Non évaluable ». La justification contient une phrase par signal, tirée des faits du CV.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date

from . import extraction
from .diplomes import NIVEAUX
from .texte import normaliser, sans_accents

# --- Seuils (constantes nommées) ----------------------------------------------------------------------------

# 1. Progression : gain de niveau entre le plus ancien intitulé et le plus récent.
PROGRESSION_FORTE_NIVEAUX = 2  # note 2
PROGRESSION_NETTE_NIVEAUX = 1  # note 1
PROGRESSION_PERIODES_MIN = 2  # périodes avec un intitulé reconnu, sinon non évaluable

# 2. Diversité : nombre d'éléments distincts et de familles (techniques, langues, savoir-être).
DIVERSITE_ELEVEE_ELEMENTS = 10  # note 2, avec au moins DIVERSITE_ELEVEE_FAMILLES familles
DIVERSITE_ELEVEE_FAMILLES = 2
DIVERSITE_MOYENNE_ELEMENTS = 5  # note 1

# 3. Stabilité : durée moyenne par emploi (hors stages), en mois.
STABILITE_BONNE_MOIS = 24  # note 2
STABILITE_MOYENNE_MOIS = 12  # note 1
STABILITE_EXPERIENCE_MIN_MOIS = 12  # en dessous (emplois cumulés), non évaluable

# 4. Formation : niveaux de diplôme en dessous du niveau demandé.
FORMATION_ECART_TOLERE = 1  # un niveau en dessous : note 1 ; davantage : note 0

# 5. Leadership et initiative : familles de mots-clés trouvées.
LEADERSHIP_FORT_FAMILLES = 3  # note 2
LEADERSHIP_PRESENT_FAMILLES = 1  # note 1

# Niveau global
SIGNAUX_MIN = 3
SIGNAUX_MIN_EXCEPTIONNEL = 4
RATIO_MOYEN = 0.35
RATIO_ELEVE = 0.60
RATIO_EXCEPTIONNEL = 0.85
FAIBLE, MOYEN, ELEVE, EXCEPTIONNEL, NON_EVALUABLE = "Faible", "Moyen", "Élevé", "Exceptionnel", "Non évaluable"
RECOMMANDATION_ENCADREMENT = "Profil à fort potentiel d'évolution vers un poste d'encadrement."

# --- Niveaux des intitulés de poste (cherchés dans cet ordre ; aucun mot-clé : « confirmé ») -------------------

NOMS_NIVEAUX_POSTE = {0: "stagiaire", 1: "junior", 2: "confirmé", 3: "senior", 4: "responsable"}
NIVEAU_POSTE_PAR_DEFAUT = 2
_NIVEAUX_POSTE: list[tuple[int, re.Pattern[str]]] = [
    (0, re.compile(r"\bstagiaire\b|\bstage\b|\binterne?\b|\binternship\b|\bapprenti\w*|\balternan\w*")),
    (1, re.compile(r"\bjunior\b|\bjr\b|\bassistant\w*|\baide[- ]|\bdebutant\w*|\bauxiliaire\b|\btrainee\b")),
    (4, re.compile(r"\bresponsable\b|\bchef\b|\bmanager\b|\bdirect(?:eur|rice|or)\b|\bhead of\b|\bcoordinat(?:eur|rice|or)\b|"
                   r"\bsuperviseur\b|\bgerant\w*|\bcto\b|\bceo\b|\bdaf\b|\bdrh\b|\bdsi\b")),
    (3, re.compile(r"\bsenior\b|\bsr\b|\bprincipal\w*|\bexpert\w*|\blead\b|\breferent\w*|\barchitecte\b")),
]

# --- Familles de compétences ---------------------------------------------------------------------------------

_LANGUES = re.compile(
    r"^(?:francais|anglais|espagnol|allemand|italien|portugais|arabe|chinois|mandarin|russe|japonais|neerlandais|"
    r"english|french|spanish|german|ewondo|duala|bassa|fulfulde|haoussa|lingala|swahili)\b"
)
_SAVOIR_ETRE = re.compile(
    r"communication|travail en equipe|esprit d'equipe|leadership|autonomie|rigueur|organisation|adaptabilite|"
    r"creativite|gestion du stress|negociation|resolution de problemes|sens de l'ecoute|ponctualite|curiosite|"
    r"esprit d'analyse|esprit critique|prise de parole|management"
)
_SEPARATEURS_COMPETENCES = re.compile(r"[,;•|·/]|\s[-–]\s")
_PUCE = re.compile(r"^[\s\-–•*·▪►>]+")

# --- Leadership et initiative ---------------------------------------------------------------------------------

FAMILLES_LEADERSHIP: dict[str, re.Pattern[str]] = {
    "encadrement": re.compile(
        r"\bencadr\w*|\bsupervis\w*|\bmanage(?:ment|r)? (?:d'une |de l'|des |une |d')?equipe|\bequipe de \d+|"
        r"\bdirig\w* (?:une |l'|des )?equipe|\bchef d'equipe\b|\bteam lead\w*|\bmentor\w*|\bcoaching\b|\bforme (?:des|les)\b"
    ),
    "responsabilité de projet": re.compile(
        r"\bchef de projet\b|\bresponsable (?:du |de |des )?projets?\b|\bpilot(?:e|age|er|ait)\b|\bcoordin\w*|"
        r"\bconduite de projets?\b|\bgestion de projets?\b|\bproject manag\w*|\bproduct owner\b|\bscrum master\b"
    ),
    "création": re.compile(
        r"\bcre(?:e|ee|es|ation|ateur|atrice)\b|\bfond(?:e|ee|ateur|atrice)\b|\bco-?fond\w*|\blance(?:ment)?\b|"
        r"\bmis(?:e)? en place\b|\binitie\b|\bentrepreneur\w*"
    ),
    "certification": re.compile(r"\bcertifi\w*|\bccna\b|\bpmp\b|\bpsm\b|\bitil\b|\btoeic\b|\btoefl\b"),
    "projets personnels": re.compile(
        r"\bprojets? personnels?\b|\bbenevol\w*|\bvie associative\b|\bassociati(?:on|f)\b|\bopen[ -]?source\b|"
        r"\bgithub\b|\bhackathon\w*"
    ),
}

_DEBUT_DE_DATE = re.compile(
    r"\b(?:janv|fevr?|mars|avr|mai|juin|juil|aout|sept?|oct|nov|dec|jan|feb|mar|apr|may|jun|jul|aug|sep)[a-z]*\.?\s+(?:19|20)\d{2}"
    r"|\b\d{1,2}\s*[/.-]\s*(?:19|20)\d{2}|\b(?:19|20)\d{2}\b|\bdepuis\b|\bsince\b"
)
_SEPARATEUR_INTITULE = re.compile(r"\s[—–-]\s|\s[|@]\s|,|\(|\bchez\b|\bat\b")


# --- Données d'entrée ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class PeriodePoste:
    debut: str  # AAAA-MM
    mois: int
    stage: bool
    intitule: str | None


@dataclass(frozen=True)
class ProfilCV:
    """Ce que le potentiel utilise du CV : tout vient du texte déjà lu et de l'extraction, sans relire le fichier."""

    periodes: tuple[PeriodePoste, ...] = ()
    competences: tuple[str, ...] = ()  # éléments listés (sections compétences et langues)
    langues: tuple[str, ...] = ()  # éléments de la section langues
    diplome_niveau: str | None = None
    lignes: tuple[str, ...] = ()  # lignes du CV, pour les mots-clés de leadership


@dataclass
class Signal:
    cle: str
    nom: str
    note: int | None  # None : non évaluable
    phrase: str
    faits: dict = field(default_factory=dict)

    @property
    def evaluable(self) -> bool:
        return self.note is not None


@dataclass
class Potentiel:
    niveau: str
    ratio: float | None
    signaux: list[Signal]
    recommandation: str | None = None

    @property
    def justification(self) -> list[str]:
        return [s.phrase for s in self.signaux]

    def en_dict(self) -> dict:
        return {
            "niveau": self.niveau,
            "ratio": self.ratio,
            "signaux": [{**asdict(s), "evaluable": s.evaluable} for s in self.signaux],
            "justification": self.justification,
            "recommandation": self.recommandation,
        }


# --- Profil depuis le texte du CV --------------------------------------------------------------------------------


def profil_depuis_texte(texte: str, diplome_niveau: str | None, aujourdhui: date | None = None) -> ProfilCV:
    """Profil du CV à partir du texte déjà lu (déchiffré en mémoire) : périodes avec leur intitulé, compétences."""
    aujourdhui = aujourdhui or date.today()
    decoupage = extraction.decouper(texte or "")
    periodes, _ = extraction.trouver_periodes(decoupage, aujourdhui)
    avec_intitules = []
    curseur = 0
    for periode in periodes:  # trouver_periodes les rend dans l'ordre des lignes : on retrouve chaque ligne
        index = next((i for i in range(curseur, len(decoupage)) if decoupage[i].texte == periode.ligne), None)
        if index is not None:
            curseur = index
        avec_intitules.append(PeriodePoste(periode.debut, periode.mois, periode.stage, intitule_de(decoupage, index) if index is not None else None))
    competences, langues = _elements_listes(decoupage)
    return ProfilCV(
        periodes=tuple(avec_intitules),
        competences=competences,
        langues=langues,
        diplome_niveau=diplome_niveau,
        lignes=tuple(l.texte for l in decoupage),
    )


def intitule_de(decoupage: list[extraction.LigneCV], i: int) -> str | None:
    """Intitulé du poste d'une période : texte avant la date sur sa ligne, sinon la ligne au-dessus, sinon en dessous."""
    ligne = decoupage[i]
    reperes = sans_accents(ligne.texte).lower()  # même longueur que la ligne d'origine
    date_trouvee = _DEBUT_DE_DATE.search(reperes)
    candidats = [ligne.texte[: date_trouvee.start()]] if date_trouvee else []
    for j in (i - 1, i + 1):
        if 0 <= j < len(decoupage):
            voisine = decoupage[j]
            if voisine.section == ligne.section and not _PUCE.match(voisine.texte) and not _DEBUT_DE_DATE.search(voisine.norm) and len(voisine.texte) <= 90:
                candidats.append(voisine.texte)
    for candidat in candidats:
        propre = _SEPARATEUR_INTITULE.split(candidat.strip(" :—–-|"))[0].strip(" :—–-|.")
        if len(re.findall(r"[^\W\d_]", propre)) >= 3 and len(propre) <= 60:
            return propre
    return None


def niveau_intitule(intitule: str, stage: bool = False) -> int:
    if stage:
        return 0
    norm = normaliser(intitule)
    for niveau, motif in _NIVEAUX_POSTE:
        if motif.search(norm):
            return niveau
    return NIVEAU_POSTE_PAR_DEFAUT


def _elements_listes(decoupage: list[extraction.LigneCV]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    competences: dict[str, str] = {}
    langues: dict[str, str] = {}
    for ligne in decoupage:
        if ligne.section not in ("competences", "langues"):
            continue
        texte = _PUCE.sub("", ligne.texte)
        prefixe, deux_points, suite = texte.partition(":")
        if deux_points and len(prefixe) <= 30:
            texte = suite  # « Langages : Python, Java » : le libellé n'est pas une compétence
        for element in _SEPARATEURS_COMPETENCES.split(texte):
            element = element.strip(" .")
            if not 1 <= len(element) <= 50 or not re.search(r"[^\W_]", element):
                continue
            cle = normaliser(element)
            competences.setdefault(cle, element)
            if ligne.section == "langues":
                langues.setdefault(cle, element)
    return tuple(competences.values()), tuple(langues.values())


# --- Signaux --------------------------------------------------------------------------------------------------------


def _annee(periode: PeriodePoste) -> str:
    return periode.debut[:4]


def _duree(mois: int) -> str:
    if mois < 12:
        return "moins d'un an"
    annees = round(mois / 12)
    return f"{annees} an{'s' if annees > 1 else ''}"


def signal_progression(profil: ProfilCV) -> Signal:
    nom = "Progression de carrière"
    connues = sorted((p for p in profil.periodes if p.intitule), key=lambda p: p.debut)
    if len(connues) < PROGRESSION_PERIODES_MIN:
        return Signal("progression", nom, None, "Progression : non évaluable (moins de deux postes datés avec un intitulé).")
    premier, dernier = connues[0], connues[-1]
    n1, n2 = niveau_intitule(premier.intitule, premier.stage), niveau_intitule(dernier.intitule, dernier.stage)
    gain = n2 - n1
    a1, m1 = map(int, premier.debut.split("-"))
    a2, m2 = map(int, dernier.debut.split("-"))
    duree = _duree((a2 - a1) * 12 + m2 - m1)
    faits = {
        "premier": {"intitule": premier.intitule, "niveau": NOMS_NIVEAUX_POSTE[n1], "annee": _annee(premier)},
        "dernier": {"intitule": dernier.intitule, "niveau": NOMS_NIVEAUX_POSTE[n2], "annee": _annee(dernier)},
        "gain_niveaux": gain,
    }
    depart = f"« {premier.intitule} » ({NOMS_NIVEAUX_POSTE[n1]}, {_annee(premier)})"
    arrivee = f"« {dernier.intitule} » ({NOMS_NIVEAUX_POSTE[n2]}, {_annee(dernier)})"
    if gain >= PROGRESSION_FORTE_NIVEAUX:
        return Signal("progression", nom, 2, f"Progression : passé de {depart} à {arrivee}, soit {gain} niveaux gagnés en {duree}.", faits)
    if gain >= PROGRESSION_NETTE_NIVEAUX:
        return Signal("progression", nom, 1, f"Progression : passé de {depart} à {arrivee}, un niveau gagné en {duree}.", faits)
    return Signal("progression", nom, 0, f"Progression : pas d'évolution de niveau visible entre {depart} et {arrivee}.", faits)


def _famille(element: str, dans_langues: bool) -> str:
    norm = normaliser(element)
    if dans_langues or _LANGUES.search(norm):
        return "langues"
    if _SAVOIR_ETRE.search(norm):
        return "savoir-être"
    return "techniques"


def signal_diversite(profil: ProfilCV) -> Signal:
    nom = "Diversité des compétences"
    if not profil.competences:
        return Signal("diversite", nom, None, "Diversité : non évaluable (aucune compétence listée dans une section dédiée).")
    langues = {normaliser(l) for l in profil.langues}
    familles = sorted({_famille(e, normaliser(e) in langues) for e in profil.competences})
    n = len(profil.competences)
    faits = {"elements": n, "familles": familles, "exemples": list(profil.competences[:8])}
    texte = f"{n} compétence{'s' if n > 1 else ''} listée{'s' if n > 1 else ''}, en {len(familles)} famille{'s' if len(familles) > 1 else ''} ({', '.join(familles)})"
    if n >= DIVERSITE_ELEVEE_ELEMENTS and len(familles) >= DIVERSITE_ELEVEE_FAMILLES:
        return Signal("diversite", nom, 2, f"Diversité : {texte}.", faits)
    if n >= DIVERSITE_MOYENNE_ELEMENTS:
        return Signal("diversite", nom, 1, f"Diversité : {texte}.", faits)
    return Signal("diversite", nom, 0, f"Diversité : {texte} seulement.", faits)


def signal_stabilite(profil: ProfilCV) -> Signal:
    nom = "Stabilité professionnelle"
    emplois = [p for p in profil.periodes if not p.stage]
    total = sum(p.mois for p in emplois)
    if not emplois or total < STABILITE_EXPERIENCE_MIN_MOIS:
        return Signal("stabilite", nom, None, "Stabilité : non évaluable (moins d'un an d'emploi hors stages).")
    moyenne = round(total / len(emplois))
    faits = {"emplois": len(emplois), "moyenne_mois": moyenne}
    texte = f"{len(emplois)} emploi{'s' if len(emplois) > 1 else ''} hors stages, {moyenne} mois en moyenne par poste"
    if moyenne >= STABILITE_BONNE_MOIS:
        return Signal("stabilite", nom, 2, f"Stabilité : {texte}.", faits)
    if moyenne >= STABILITE_MOYENNE_MOIS:
        return Signal("stabilite", nom, 1, f"Stabilité : {texte}.", faits)
    return Signal("stabilite", nom, 0, f"Stabilité : {texte}, des changements fréquents.", faits)


def signal_formation(profil: ProfilCV, niveau_requis: str | None) -> Signal:
    nom = "Formation face au poste"
    if profil.diplome_niveau not in NIVEAUX:
        return Signal("formation", nom, None, "Formation : non évaluable (aucun diplôme obtenu trouvé dans le CV).")
    if niveau_requis not in NIVEAUX:
        return Signal("formation", nom, None, "Formation : non évaluable (aucun niveau demandé pour le poste).")
    ecart = NIVEAUX[profil.diplome_niveau] - NIVEAUX[niveau_requis]
    faits = {"diplome": profil.diplome_niveau, "niveau_requis": niveau_requis, "ecart": ecart}
    base = f"Formation : {profil.diplome_niveau} pour {niveau_requis} demandé"
    if ecart > 0:
        return Signal("formation", nom, 2, f"{base}, au-dessus du niveau demandé (sur-qualification à apprécier).", faits)
    if ecart == 0:
        return Signal("formation", nom, 2, f"{base}, niveau atteint.", faits)
    if -ecart <= FORMATION_ECART_TOLERE:
        return Signal("formation", nom, 1, f"{base}, un niveau en dessous.", faits)
    return Signal("formation", nom, 0, f"{base}, {-ecart} niveaux en dessous.", faits)


def signal_leadership(profil: ProfilCV) -> Signal:
    nom = "Leadership et initiative"
    trouvees: dict[str, str] = {}
    for ligne in profil.lignes:
        norm = normaliser(ligne)
        for famille, motif in FAMILLES_LEADERSHIP.items():
            if famille not in trouvees and motif.search(norm):
                extrait = _PUCE.sub("", ligne).strip()
                trouvees[famille] = extrait if len(extrait) <= 70 else extrait[:67].rstrip() + "…"
    faits = {"familles": trouvees}
    if not trouvees:
        return Signal("leadership", nom, 0, "Leadership et initiative : aucune mention d'encadrement, de projet, de création, de certification ou de projet personnel.", faits)
    texte = " ; ".join(f"{famille} (« {extrait} »)" for famille, extrait in trouvees.items())
    note = 2 if len(trouvees) >= LEADERSHIP_FORT_FAMILLES else 1 if len(trouvees) >= LEADERSHIP_PRESENT_FAMILLES else 0
    return Signal("leadership", nom, note, f"Leadership et initiative : {texte}.", faits)


# --- Ensemble --------------------------------------------------------------------------------------------------------


def niveau_depuis(signaux: list[Signal]) -> tuple[str, float | None]:
    evaluables = [s for s in signaux if s.evaluable]
    if len(evaluables) < SIGNAUX_MIN:
        return NON_EVALUABLE, None
    ratio = round(sum(s.note for s in evaluables) / (2 * len(evaluables)), 3)
    if ratio >= RATIO_EXCEPTIONNEL:
        return (EXCEPTIONNEL if len(evaluables) >= SIGNAUX_MIN_EXCEPTIONNEL else ELEVE), ratio
    if ratio >= RATIO_ELEVE:
        return ELEVE, ratio
    if ratio >= RATIO_MOYEN:
        return MOYEN, ratio
    return FAIBLE, ratio


def evaluer(profil: ProfilCV, niveau_requis: str | None) -> Potentiel:
    """Potentiel d'un CV pour un poste (seul le signal formation dépend du poste)."""
    signaux = [
        signal_progression(profil),
        signal_diversite(profil),
        signal_stabilite(profil),
        signal_formation(profil, niveau_requis),
        signal_leadership(profil),
    ]
    niveau, ratio = niveau_depuis(signaux)
    leadership = signaux[-1]
    recommandation = RECOMMANDATION_ENCADREMENT if niveau in (ELEVE, EXCEPTIONNEL) and leadership.note == 2 else None
    return Potentiel(niveau, ratio, signaux, recommandation)
