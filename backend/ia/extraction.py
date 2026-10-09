"""Étape 2 : extraction des informations d'un CV, indépendante de tout poste.

Fonctions pures : elles reçoivent le texte (et la date du jour) et renvoient des données sérialisables.

Règles :
- l'expérience ne se lit que dans la section expérience ; les dates d'études (section formation) ne comptent jamais ;
- une période se lit au mois près (« Février 2025 – Présent », « 09/2021 - 02/2023 ») ; une année seule compte
  à partir de juin (estimation au milieu de l'année) ;
- les périodes qui se chevauchent sont fusionnées ; les stages sont comptés à part et n'entrent pas dans le total ;
  l'alternance compte comme de l'expérience ;
- le diplôme retenu est le plus élevé **obtenu**, lu dans la section formation uniquement (un diplôme « en cours »
  ne compte pas).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date

from . import diplomes
from .texte import lignes, normaliser

VERSION_EXTRACTION = 1

# ----------------------------------------------------------------------------- contact

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_TELEPHONE = re.compile(r"(?<![\w])(?:\+|00)?\d[\d .\-()/]{7,18}\d(?![\w])")
_MOT_DE_NOM = re.compile(r"[^\W\d_](?:[^\W\d_]|['.-])*")  # lettres, avec traits d'union et apostrophes
_MOTS_PAS_UN_NOM = re.compile(
    r"curriculum|vitae|\bcv\b|resume|profil|developpeu|ingenieu|comptable|technicien|manager|chef|"
    r"responsable|assistant|stagiaire|etudiant|consultant|analyste|adresse|tel|mail|ne le|nee le|@|\d"
)


def extraire_contact(texte: str) -> dict:
    email = _EMAIL.search(texte or "")
    telephone = None
    for candidat in _TELEPHONE.finditer(texte or ""):
        chiffres = re.sub(r"\D", "", candidat.group())
        brut = candidat.group()
        if 9 <= len(chiffres) <= 15 and not re.fullmatch(r"\s*\d{4}\s*[-/]\s*\d{4}\s*", brut):
            telephone = " ".join(brut.replace("(", " ").replace(")", " ").split())
            break
    return {"nom": _deviner_nom(texte), "email": email.group().lower() if email else None, "telephone": telephone}


def _deviner_nom(texte: str) -> str | None:
    """Le nom est en général l'une des premières lignes : 2 à 4 mots, sans chiffre ni mot de métier."""
    for ligne in lignes(texte)[:6]:
        mots = ligne.replace(",", " ").split()
        if not 2 <= len(mots) <= 4 or len(ligne) > 50:
            continue
        norm = normaliser(ligne)
        if _MOTS_PAS_UN_NOM.search(norm) or _section_du_titre(norm) or not all(_MOT_DE_NOM.fullmatch(m) for m in mots):
            continue  # « EXPÉRIENCE PROFESSIONNELLE » a la forme d'un nom : c'est un titre de section
        return " ".join(m if not m.isupper() else m.capitalize() for m in mots)
    return None


# ----------------------------------------------------------------------------- sections

TITRES_SECTIONS = {
    "experience": [
        "experience", "experiences", "experience professionnelle", "experiences professionnelles",
        "parcours professionnel", "emplois", "emploi", "historique professionnel", "postes occupes",
        "professional experience", "work experience", "employment", "employment history", "career",
        "experiences et stages", "stages et experiences", "stages", "stage",
    ],
    "formation": [
        "formation", "formations", "formation academique", "education", "etudes", "diplomes", "diplomes et formations",
        "cursus", "cursus scolaire", "cursus universitaire", "parcours academique", "parcours scolaire",
        "academic background", "qualifications", "diplomes obtenus", "formation et diplomes",
    ],
    "competences": [
        "competences", "competence", "competences techniques", "competences cles", "competences professionnelles",
        "skills", "technical skills", "aptitudes", "connaissances", "connaissances informatiques", "informatique",
        "outils", "savoir-faire", "domaines de competence",
    ],
    "langues": ["langues", "langue", "languages", "langues parlees"],
    "autres": [
        "profil", "a propos", "resume", "objectif", "objectifs", "centres d'interet", "loisirs", "interets", "hobbies",
        "certifications", "certificats", "projets", "references", "activites", "vie associative", "distinctions",
        "publications", "qualites", "atouts", "informations personnelles", "contact",
    ],
}
_TITRE_VERS_SECTION = {titre: section for section, titres in TITRES_SECTIONS.items() for titre in titres}


def _section_du_titre(ligne_normalisee: str) -> str | None:
    """Une ligne est un titre de section si elle est courte et correspond à un intitulé connu."""
    propre = re.sub(r"^[\W\d_]+|[\W_]+$", "", ligne_normalisee).strip()
    if not propre or len(propre) > 45:
        return None
    return _TITRE_VERS_SECTION.get(propre)


@dataclass
class LigneCV:
    texte: str  # ligne d'origine
    norm: str  # ligne normalisée
    section: str  # experience | formation | competences | langues | autres | entete
    sous_titre_stage: bool = False  # la ligne est sous un titre « Stages »


def decouper(texte: str) -> list[LigneCV]:
    resultat: list[LigneCV] = []
    section, stage = "entete", False
    for ligne in lignes(texte):
        norm = normaliser(ligne)
        titre = _section_du_titre(norm)
        if titre:
            section = titre
            stage = re.sub(r"[\W_]+", " ", norm).strip() in ("stages", "stage")
            continue
        resultat.append(LigneCV(ligne, norm, section, stage))
    return resultat


def sections_en_texte(decoupage: list[LigneCV]) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    for l in decoupage:
        sections.setdefault(l.section, []).append(l.texte)
    return {nom: "\n".join(contenu) for nom, contenu in sections.items()}


# ----------------------------------------------------------------------------- périodes

_MOIS = {
    "janvier": 1, "janv": 1, "jan": 1, "january": 1,
    "fevrier": 2, "fevr": 2, "fev": 2, "february": 2, "feb": 2,
    "mars": 3, "mar": 3, "march": 3,
    "avril": 4, "avr": 4, "april": 4, "apr": 4,
    "mai": 5, "may": 5,
    "juin": 6, "june": 6, "jun": 6,
    "juillet": 7, "juil": 7, "july": 7, "jul": 7,
    "aout": 8, "august": 8, "aug": 8,
    "septembre": 9, "sept": 9, "sep": 9, "september": 9,
    "octobre": 10, "oct": 10, "october": 10,
    "novembre": 11, "nov": 11, "november": 11,
    "decembre": 12, "dec": 12, "december": 12,
}
_NOMS_MOIS = "|".join(sorted(_MOIS, key=len, reverse=True))
_DATE = rf"(?:(?:{_NOMS_MOIS})\.?\s+(?:19|20)\d{{2}}|(?:0?[1-9]|1[0-2])\s*[/.-]\s*(?:19|20)\d{{2}}|(?:19|20)\d{{2}})"
_PRESENT = (
    r"(?:a ce jour|ce jour|aujourd'hui|aujourd hui|present|presente|actuel|actuellement|en cours|"
    r"maintenant|now|current|currently|today)"
)
_SEPARATEUR = r"\s*(?:-|a|au|to|jusqu'a|jusqu'au|jusqu'en|>)\s*"
_PERIODE = re.compile(rf"(?:de|du|from)?\s*(?P<debut>{_DATE}){_SEPARATEUR}(?P<fin>{_DATE}|{_PRESENT})\b")
_DEPUIS = re.compile(rf"\b(?:depuis|since|des)\s+(?:le |l')?(?P<debut>{_DATE})\b")

MOT_STAGE = re.compile(r"\bstages?\b|\bstagiaire\b|\binterns?\b|\binternship\b|\btrainee\b")
MOT_ETUDES = re.compile(
    r"\buniversite\b|\buniversity\b|\becole\b|\bschool\b|\blycee\b|\bcollege\b|\binstitut\b|\bfaculte\b|"
    r"\betudiant\b|\betudes\b|\bdiplome\b|\bformation\b"
)


def _lire_date(texte: str, aujourdhui: date) -> tuple[int, int, bool] | None:
    """(année, mois, précision au mois ?) ; None si ce n'est pas une date."""
    texte = texte.strip().rstrip(".")
    if re.fullmatch(_PRESENT, texte):
        return aujourdhui.year, aujourdhui.month, True
    m = re.fullmatch(rf"({_NOMS_MOIS})\.?\s+(\d{{4}})", texte)
    if m:
        return int(m.group(2)), _MOIS[m.group(1)], True
    m = re.fullmatch(r"(\d{1,2})\s*[/.-]\s*(\d{4})", texte)
    if m:
        return int(m.group(2)), int(m.group(1)), True
    m = re.fullmatch(r"\d{4}", texte)
    if m:
        return int(texte), 6, False  # année seule : milieu de l'année
    return None


@dataclass
class Periode:
    debut: str  # AAAA-MM
    fin: str  # AAAA-MM
    en_cours: bool
    mois: int
    stage: bool
    ligne: str
    precision: str  # « mois » ou « annee »

    def bornes(self) -> tuple[int, int]:
        a1, m1 = map(int, self.debut.split("-"))
        a2, m2 = map(int, self.fin.split("-"))
        return a1 * 12 + m1 - 1, a2 * 12 + m2 - 1


def trouver_periodes(decoupage: list[LigneCV], aujourdhui: date) -> tuple[list[Periode], bool]:
    """Périodes d'expérience (stages compris, marqués). Renvoie aussi si une section expérience a été trouvée."""
    a_section_experience = any(l.section == "experience" for l in decoupage)
    a_sections = any(l.section != "entete" for l in decoupage)
    periodes: list[Periode] = []
    for i, ligne in enumerate(decoupage):
        if a_section_experience:
            if ligne.section != "experience":
                continue
        elif ligne.section == "formation":
            continue
        for debut_txt, fin_txt in _periodes_dans(ligne.norm):
            debut = _lire_date(debut_txt, aujourdhui)
            fin = _lire_date(fin_txt, aujourdhui) if fin_txt else (aujourdhui.year, aujourdhui.month, True)
            if not debut or not fin:
                continue
            index_debut, index_fin = debut[0] * 12 + debut[1] - 1, fin[0] * 12 + fin[1] - 1
            index_aujourdhui = aujourdhui.year * 12 + aujourdhui.month - 1
            if index_fin > index_aujourdhui:  # date future : on s'arrête à aujourd'hui
                index_fin = index_aujourdhui
            if index_debut > index_fin or index_fin - index_debut > 50 * 12 or debut[0] < 1960:
                continue
            contexte = _contexte(decoupage, i)
            if not a_sections and MOT_ETUDES.search(contexte):
                continue  # CV sans sections : on écarte les lignes qui parlent d'études
            en_cours = fin_txt is None or bool(re.fullmatch(_PRESENT, fin_txt.strip()))
            periodes.append(Periode(
                debut=f"{index_debut // 12:04d}-{index_debut % 12 + 1:02d}",
                fin=f"{index_fin // 12:04d}-{index_fin % 12 + 1:02d}",
                en_cours=en_cours,
                mois=index_fin - index_debut + 1,
                stage=ligne.sous_titre_stage or bool(MOT_STAGE.search(contexte)),
                ligne=ligne.texte,
                precision="mois" if debut[2] and fin[2] else "annee",
            ))
    return periodes, a_section_experience


def _periodes_dans(ligne_norm: str) -> list[tuple[str, str | None]]:
    trouvees = [(m.group("debut"), m.group("fin")) for m in _PERIODE.finditer(ligne_norm)]
    if not trouvees:
        trouvees = [(m.group("debut"), None) for m in _DEPUIS.finditer(ligne_norm)]
    return trouvees


def _contexte(decoupage: list[LigneCV], i: int) -> str:
    """La ligne de la période et ses voisines immédiates de la même section, si elles ne portent pas une autre période."""
    morceaux = [decoupage[i].norm]
    for j in (i - 1, i + 1):
        if 0 <= j < len(decoupage) and decoupage[j].section == decoupage[i].section and not _periodes_dans(decoupage[j].norm):
            morceaux.append(decoupage[j].norm)
    return " ".join(morceaux)


def total_mois(periodes: list[Periode]) -> int:
    """Durée totale en mois, périodes qui se chevauchent fusionnées."""
    intervalles = sorted(p.bornes() for p in periodes)
    total, courant = 0, None
    for debut, fin in intervalles:
        if courant and debut <= courant[1] + 1:
            courant = (courant[0], max(courant[1], fin))
        else:
            if courant:
                total += courant[1] - courant[0] + 1
            courant = (debut, fin)
    if courant:
        total += courant[1] - courant[0] + 1
    return total


# ----------------------------------------------------------------------------- diplôme


def trouver_diplome(decoupage: list[LigneCV], aujourdhui: date) -> dict:
    """Diplôme le plus élevé obtenu, lu dans la section formation."""
    formation = [l for l in decoupage if l.section == "formation"]
    section_trouvee = bool(formation)
    if not section_trouvee:  # repli : lignes hors expérience qui ressemblent à une formation
        formation = [l for l in decoupage if l.section in ("entete", "autres") and MOT_ETUDES.search(l.norm)]
    retenu, ignores = None, []
    for i, ligne in enumerate(formation):
        niveau = diplomes.niveau_dans_ligne(ligne.norm)
        if niveau is None:
            continue
        suivante = formation[i + 1].norm if i + 1 < len(formation) else ""
        if diplomes.niveau_dans_ligne(suivante) is not None:
            suivante = ""
        if _en_cours(ligne.norm + " " + suivante, aujourdhui):
            ignores.append({"niveau": diplomes.NOM_NIVEAU[niveau], "ligne": ligne.texte, "raison": "en cours"})
            continue
        if retenu is None or niveau > retenu["code"]:
            retenu = {"code": niveau, "niveau": diplomes.NOM_NIVEAU[niveau], "ligne": ligne.texte}
    return {
        "niveau": retenu["niveau"] if retenu else None,
        "ligne": retenu["ligne"] if retenu else None,
        "ignores": ignores,
        "section_formation_trouvee": section_trouvee,
    }


def _en_cours(texte_norm: str, aujourdhui: date) -> bool:
    if diplomes.EN_COURS.search(texte_norm):
        return True
    for _, fin in _periodes_dans(texte_norm):
        if fin is None or re.fullmatch(_PRESENT, fin.strip()):
            return True
        lue = _lire_date(fin, aujourdhui)
        if lue and (lue[0], lue[1] if lue[2] else 1) > (aujourdhui.year, aujourdhui.month):
            return True  # diplôme dont la fin est dans le futur
    return False


# ----------------------------------------------------------------------------- tout ensemble


@dataclass
class Extraction:
    nom: str | None
    email: str | None
    telephone: str | None
    sections: dict[str, str]
    periodes: list[dict] = field(default_factory=list)
    experience_mois: int = 0
    stages_mois: int = 0
    section_experience_trouvee: bool = False
    diplome: dict = field(default_factory=dict)
    version: int = VERSION_EXTRACTION

    def en_dict(self) -> dict:
        return asdict(self)


def extraire(texte: str, aujourdhui: date | None = None) -> Extraction:
    aujourdhui = aujourdhui or date.today()
    decoupage = decouper(texte)
    periodes, section_experience = trouver_periodes(decoupage, aujourdhui)
    emplois = [p for p in periodes if not p.stage]
    stages = [p for p in periodes if p.stage]
    contact = extraire_contact(texte)
    return Extraction(
        nom=contact["nom"],
        email=contact["email"],
        telephone=contact["telephone"],
        sections=sections_en_texte(decoupage),
        periodes=[asdict(p) for p in periodes],
        experience_mois=total_mois(emplois),
        stages_mois=total_mois(stages),
        section_experience_trouvee=section_experience,
        diplome=trouver_diplome(decoupage, aujourdhui),
    )
