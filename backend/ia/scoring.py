"""Étape 4 : score d'un CV pour un poste, sur 100.

Fonctions pures : elles reçoivent les données du CV et du poste, et ne touchent ni aux fichiers ni à la base.
Chaque critère renvoie un score entre 0 et 1 et le détail de son calcul (repris du principe de l'ancien projet).

Poids par défaut (modifiables par poste) : compétences 40, expérience 25, formation 20, adéquation 15.
Sans modèle d'adéquation, ce critère est ignoré et les autres poids sont recalculés pour totaliser 100.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import competences as module_competences
from .diplomes import NIVEAUX
from .semantique import similarite

POIDS_DEFAUT = {"competences": 40, "experience": 25, "formation": 20, "adequation": 15}

# Formation : niveau atteint ou dépassé = 100 %, puis on retire ce pourcentage par niveau manquant.
PENALITE_PAR_NIVEAU_MANQUANT = 0.40

# Adéquation : la similarité cosinus brute de Sentence-BERT est ramenée sur [0, 1] entre ces deux bornes.
# Calées avec python -m backend.ia.calibrer : CV correspondant 0,71-0,76 ; profil sans rapport 0,09-0,38.
SIMILARITE_PLANCHER = 0.30
SIMILARITE_PLAFOND = 0.70


@dataclass(frozen=True)
class DonneesCV:
    texte: str
    experience_mois: int
    diplome_niveau: str | None  # Bac, BTS, Licence, Master, Doctorat ou None
    diplome_ligne: str | None = None
    vecteur: list[float] | None = None


@dataclass(frozen=True)
class DonneesPoste:
    competences: list[str]
    experience_min_annees: int
    niveau_formation: str
    poids: dict[str, float] = field(default_factory=lambda: dict(POIDS_DEFAUT))
    vecteur: list[float] | None = None


@dataclass
class Resultat:
    score: float  # sur 100
    pertinence: float  # sur 100 : compétences + adéquation seulement (sert au classement par poste)
    criteres: dict[str, dict]
    adequation_ignoree: bool

    def detail(self) -> dict:
        return {"criteres": self.criteres, "adequation_ignoree": self.adequation_ignoree, "pertinence": self.pertinence}


# ----------------------------------------------------------------------------- critères


def score_competences(texte_cv: str, requises: list[str]) -> tuple[float, dict]:
    if not requises:
        return 1.0, {"trouvees": [], "manquantes": [], "message": "Aucune compétence requise."}
    trouvees, manquantes = module_competences.comparer(requises, texte_cv)
    return len(trouvees) / len(requises), {
        "trouvees": trouvees,
        "manquantes": manquantes,
        "message": f"{len(trouvees)} sur {len(requises)} {'compétence requise trouvée' if len(requises) == 1 else 'compétences requises trouvées'} dans le CV.",
    }


def score_experience(experience_mois: int, annees_requises: int) -> tuple[float, dict]:
    annees = round(experience_mois / 12, 1)
    detail = {"experience_retenue_mois": experience_mois, "experience_retenue_annees": annees, "experience_requise_annees": annees_requises}
    if annees_requises <= 0:
        return 1.0, {**detail, "message": "Aucune expérience minimale demandée."}
    score = min(1.0, experience_mois / (annees_requises * 12))
    return score, {**detail, "message": f"Expérience retenue : {_annees(annees)}, pour {_annees(annees_requises)} demandé{'s' if annees_requises >= 2 else ''}."}


def score_formation(niveau_cv: str | None, ligne: str | None, niveau_requis: str) -> tuple[float, dict]:
    requis = NIVEAUX.get(niveau_requis)
    detail = {"diplome_retenu": niveau_cv, "ligne": ligne, "niveau_requis": niveau_requis}
    if requis is None:
        return 1.0, {**detail, "message": "Aucun niveau de formation exigé."}
    if niveau_cv is None:
        return 0.0, {**detail, "niveaux_manquants": None, "message": "Aucun diplôme obtenu n'a été trouvé dans la section formation du CV."}
    manquants = max(0, requis - NIVEAUX[niveau_cv])
    score = max(0.0, 1.0 - PENALITE_PAR_NIVEAU_MANQUANT * manquants)
    message = f"{niveau_cv} pour {niveau_requis} demandé" + (" : niveau atteint." if manquants == 0 else f" : {manquants} niveau(x) en dessous.")
    return score, {**detail, "niveaux_manquants": manquants, "message": message}


def score_adequation(vecteur_cv: list[float] | None, vecteur_poste: list[float] | None) -> tuple[float | None, dict]:
    if vecteur_cv is None or vecteur_poste is None:
        return None, {"message": "Adéquation non calculée : modèle sémantique indisponible."}
    brute = similarite(vecteur_cv, vecteur_poste)
    score = min(1.0, max(0.0, (brute - SIMILARITE_PLANCHER) / (SIMILARITE_PLAFOND - SIMILARITE_PLANCHER)))
    return score, {"similarite": round(brute, 4), "message": f"Similarité entre le CV et la description du poste : {brute:.2f}."}


# ----------------------------------------------------------------------------- score global


def scorer(cv: DonneesCV, poste: DonneesPoste) -> Resultat:
    calcules = {
        "competences": score_competences(cv.texte, poste.competences),
        "experience": score_experience(cv.experience_mois, poste.experience_min_annees),
        "formation": score_formation(cv.diplome_niveau, cv.diplome_ligne, poste.niveau_formation),
        "adequation": score_adequation(cv.vecteur, poste.vecteur),
    }
    adequation_ignoree = calcules["adequation"][0] is None
    poids = poids_effectifs(poste.poids, adequation_ignoree)

    criteres, total = {}, 0.0
    for nom, (score, detail) in calcules.items():
        contribution = (score or 0.0) * poids[nom]
        total += contribution
        criteres[nom] = {
            "score": None if score is None else round(score * 100, 1),
            "poids": round(poids[nom], 2),
            "poids_demande": poste.poids.get(nom, POIDS_DEFAUT[nom]),
            "contribution": round(contribution, 2),
            "detail": detail,
        }
    return Resultat(score=round(total, 1), pertinence=pertinence(calcules, poste.poids), criteres=criteres, adequation_ignoree=adequation_ignoree)


def poids_effectifs(poids: dict[str, float], adequation_ignoree: bool) -> dict[str, float]:
    """Poids ramenés à 100 ; l'adéquation est retirée si elle n'a pas pu être calculée."""
    retenus = {nom: float(poids.get(nom, POIDS_DEFAUT[nom])) for nom in POIDS_DEFAUT}
    if adequation_ignoree:
        retenus["adequation"] = 0.0
    somme = sum(retenus.values())
    if somme <= 0:  # poids tous nuls : on revient aux poids par défaut
        return poids_effectifs(POIDS_DEFAUT, adequation_ignoree)
    return {nom: valeur * 100 / somme for nom, valeur in retenus.items()}


def pertinence(calcules: dict[str, tuple], poids: dict[str, float]) -> float:
    """Ce CV correspond-il à CE poste ? Compétences et adéquation seulement, sur 100.

    L'expérience et le diplôme ne disent rien du métier : un comptable expérimenté et diplômé ne doit pas paraître
    pertinent pour un poste de développeur.
    """
    competences = calcules["competences"][0]
    adequation = calcules["adequation"][0]
    if adequation is None:
        return round(competences * 100, 1)
    p_comp = float(poids.get("competences", POIDS_DEFAUT["competences"]))
    p_adeq = float(poids.get("adequation", POIDS_DEFAUT["adequation"]))
    if p_comp + p_adeq <= 0:
        p_comp, p_adeq = POIDS_DEFAUT["competences"], POIDS_DEFAUT["adequation"]
    return round((competences * p_comp + adequation * p_adeq) * 100 / (p_comp + p_adeq), 1)


def _annees(valeur: float) -> str:
    valeur = round(valeur, 1)
    texte = f"{valeur:g}".replace(".", ",")
    return f"{texte} an" + ("s" if valeur >= 2 else "")
