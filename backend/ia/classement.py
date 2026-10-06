"""Étape 3 : à quel poste actif rattacher une candidature ?

Fonction pure, appelée avec les postes actifs et les résultats de scoring déjà calculés.
1. Le mail (objet, corps, lettre de motivation) cite la référence ou l'intitulé d'un poste : assignation directe.
2. Sinon, le poste de meilleure pertinence (compétences + adéquation) est retenu :
   - pertinence < SEUIL_NON_CLASSE : non classé ;
   - pertinence < SEUIL_PERTINENCE_FAIBLE, ou deux postes à moins de ECART_POSTES_PROCHES points : à vérifier.
Aucune candidature n'est écartée : ces statuts aident le recruteur à savoir où regarder.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .texte import normaliser

SEUIL_NON_CLASSE = 15.0
SEUIL_PERTINENCE_FAIBLE = 40.0
ECART_POSTES_PROCHES = 8.0

CLASSE = "classe"
A_VERIFIER = "a_verifier"
NON_CLASSE = "non_classe"


@dataclass(frozen=True)
class PosteActif:
    id: int
    intitule: str
    reference: str | None = None


@dataclass(frozen=True)
class SourceMail:
    objet: str = ""
    corps: str = ""
    lettre: str = ""  # texte des autres pièces jointes (lettre de motivation…)


@dataclass(frozen=True)
class Decision:
    poste_id: int | None
    statut: str  # classe | a_verifier | non_classe
    mode: str | None  # reference | automatique | None
    motif: str


def _motif_expression(expression: str) -> re.Pattern[str] | None:
    mots = re.findall(r"[a-z0-9]+", normaliser(expression))
    if not mots:
        return None
    return re.compile(r"(?<![a-z0-9])" + r"[\s.\-_/']*".join(map(re.escape, mots)) + r"(?![a-z0-9])")


def postes_cites(source: SourceMail, postes: list[PosteActif]) -> list[tuple[PosteActif, str, str]]:
    """Postes cités dans le mail : (poste, « référence » ou « intitulé », endroit)."""
    endroits = [("l'objet du mail", source.objet), ("le corps du mail", source.corps), ("la lettre de motivation", source.lettre)]
    cites = []
    for poste in postes:
        for genre, expression in (("référence", poste.reference), ("intitulé", poste.intitule)):
            motif = _motif_expression(expression or "")
            if motif is None or (genre == "référence" and len(re.sub(r"\W", "", expression or "")) < 3):
                continue  # une référence trop courte (« A1 ») provoquerait de fausses détections
            endroit = next((nom for nom, texte in endroits if texte and motif.search(normaliser(texte))), None)
            if endroit:
                cites.append((poste, genre, endroit))
                break  # la référence suffit, inutile de chercher l'intitulé
    return cites


def decider(source: SourceMail, postes: list[PosteActif], pertinences: dict[int, float]) -> Decision:
    if not postes:
        return Decision(None, NON_CLASSE, None, "Aucun poste actif : activez un poste pour classer les candidatures.")

    cites = postes_cites(source, postes)
    if cites:
        par_reference = [c for c in cites if c[1] == "référence"]
        candidats = par_reference or sorted(cites, key=lambda c: len(c[0].intitule), reverse=True)
        meilleurs = [c for c in candidats if c[1] == "référence" or len(c[0].intitule) == len(candidats[0][0].intitule)]
        if len(meilleurs) == 1:
            poste, genre, endroit = meilleurs[0]
            return Decision(poste.id, CLASSE, "reference", f"{genre.capitalize()} du poste « {poste.reference if genre == 'référence' else poste.intitule} » citée dans {endroit}.")
        poste = max((c[0] for c in meilleurs), key=lambda p: pertinences.get(p.id, 0.0))
        noms = ", ".join(f"« {c[0].intitule} »" for c in meilleurs)
        return Decision(poste.id, A_VERIFIER, "reference", f"Plusieurs postes sont cités dans le mail ({noms}) : le plus pertinent a été retenu.")

    classes = sorted(postes, key=lambda p: pertinences.get(p.id, 0.0), reverse=True)
    meilleur = classes[0]
    p1 = pertinences.get(meilleur.id, 0.0)
    if p1 < SEUIL_NON_CLASSE:
        return Decision(None, NON_CLASSE, None, f"Aucun poste actif ne correspond à ce CV (meilleure pertinence : {p1:.0f}/100).")
    if p1 < SEUIL_PERTINENCE_FAIBLE:
        return Decision(meilleur.id, A_VERIFIER, "automatique", f"Correspondance faible avec « {meilleur.intitule} » ({p1:.0f}/100).")
    if len(classes) > 1:
        second = classes[1]
        p2 = pertinences.get(second.id, 0.0)
        if p1 - p2 < ECART_POSTES_PROCHES:
            return Decision(
                meilleur.id, A_VERIFIER, "automatique",
                f"Profil proche de deux postes : « {meilleur.intitule} » ({p1:.0f}/100) et « {second.intitule} » ({p2:.0f}/100).",
            )
    return Decision(meilleur.id, CLASSE, "automatique", f"Poste le plus proche du CV : « {meilleur.intitule} » ({p1:.0f}/100).")
