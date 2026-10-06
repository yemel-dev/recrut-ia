"""Recherche des compétences requises par un poste dans le texte d'un CV.

Pas de liste fixe de compétences : INJARA cherche celles que le recruteur a saisies, pour tous les métiers.
- casse, accents et ponctuation ignorés (« Node.js », « nodejs », « node js ») ;
- une compétence en plusieurs mots est cherchée comme une expression (« Django REST Framework ») ;
- « c++ », « c# » restent distincts de « c » ; « Java » ne se trouve pas dans « JavaScript » ;
- quelques synonymes courants, regroupés dans SYNONYMES (modifiable).
"""
from __future__ import annotations

import re
from functools import lru_cache

from .texte import normaliser

# Chaque groupe contient des écritures équivalentes. Les sigles trop ambigus (« ai », « ml ») sont volontairement absents.
SYNONYMES: list[list[str]] = [
    ["javascript", "js", "ecmascript"],
    ["typescript", "ts"],
    ["postgresql", "postgres", "psql"],
    ["mysql", "my sql"],
    ["sql server", "mssql", "ms sql", "microsoft sql server"],
    ["kubernetes", "k8s"],
    ["node.js", "nodejs", "node"],
    ["react", "react.js", "reactjs"],
    ["vue.js", "vuejs", "vue"],
    ["angular", "angularjs"],
    ["c#", "csharp", "c sharp"],
    [".net", "dotnet", "asp.net"],
    ["django rest framework", "drf"],
    ["api rest", "rest api", "api restful", "restful"],
    ["ci/cd", "integration continue", "continuous integration"],
    ["machine learning", "apprentissage automatique"],
    ["intelligence artificielle", "ia", "artificial intelligence"],
    ["power bi", "powerbi"],
    ["excel", "ms excel", "microsoft excel"],
    ["word", "ms word", "microsoft word"],
    ["powerpoint", "ms powerpoint", "microsoft powerpoint"],
    ["pack office", "ms office", "microsoft office", "suite office", "suite bureautique"],
    ["gestion de projet", "gestion de projets", "project management", "management de projet"],
    ["comptabilite", "comptabilite generale", "accounting"],
    ["syscohada", "ohada"],
    ["ressources humaines", "rh", "human resources", "gestion des ressources humaines"],
    ["service client", "relation client", "customer service"],
    ["anglais", "english"],
    ["francais", "french"],
]


@lru_cache(maxsize=None)
def _groupes() -> dict[str, tuple[str, ...]]:
    index: dict[str, tuple[str, ...]] = {}
    for groupe in SYNONYMES:
        cles = tuple(dict.fromkeys(_cle(m) for m in groupe))
        for cle in cles:
            index[cle] = cles
    return index


def _jetons(expression: str) -> list[str]:
    """« Node.js » → ['node', 'js'] ; « C++ » → ['c++'] ; « C# » → ['c#'] ; « .NET » → ['.net'] (le point initial compte)."""
    texte = normaliser(expression).strip()
    jetons = re.findall(r"[a-z0-9]+[+#]*|[+#]+", texte)
    if texte.startswith(".") and jetons:
        jetons[0] = "." + jetons[0]
    return jetons


def _cle(expression: str) -> str:
    return " ".join(_jetons(expression))


@lru_cache(maxsize=2048)
def _motif(cle: str) -> re.Pattern[str]:
    """Jetons séparés par n'importe quelle ponctuation (ou rien), sans coller à un autre mot."""
    morceaux = [re.escape(j) for j in cle.split()]
    return re.compile(r"(?<![a-z0-9+#])" + r"[\s.\-_/']*".join(morceaux) + r"(?![a-z0-9+#])")


def variantes(competence: str) -> tuple[str, ...]:
    cle = _cle(competence)
    return _groupes().get(cle, (cle,)) if cle else ()


def chercher(competence: str, texte_normalise: str) -> str | None:
    """Renvoie l'écriture trouvée dans le texte (déjà normalisé), ou None."""
    for variante in variantes(competence):
        trouve = _motif(variante).search(texte_normalise)
        if trouve:
            return trouve.group()
    return None


def comparer(competences_requises: list[str], texte: str) -> tuple[list[dict], list[str]]:
    """(compétences trouvées avec leur écriture dans le CV, compétences manquantes)."""
    texte_normalise = normaliser(texte)
    trouvees, manquantes = [], []
    for competence in competences_requises:
        ecriture = chercher(competence, texte_normalise)
        if ecriture:
            trouvees.append({"competence": competence, "trouvee_sous": ecriture})
        else:
            manquantes.append(competence)
    return trouvees, manquantes
