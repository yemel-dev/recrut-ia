"""Niveaux de diplôme et leur détection dans une ligne de la section formation.

Correspondances (reprises de l'ancien projet et complétées pour le Cameroun) :
- Doctorat : doctorat, PhD.
- Master : master, mastère, MBA, M2, MSc, DEA, DESS, Bac+5, diplôme d'ingénieur, ingénieur de conception.
- Licence : licence, bachelor, BSc, Bac+3, Bac+4, maîtrise, M1, ingénieur des travaux (Bac+3 au Cameroun).
- BTS : BTS, DUT, DTS, HND, DEUG, Bac+2.
- Bac : baccalauréat, GCE A Level.
"""
from __future__ import annotations

import re

NIVEAUX = {"Bac": 0, "BTS": 1, "Licence": 2, "Master": 3, "Doctorat": 4}
NOM_NIVEAU = {v: k for k, v in NIVEAUX.items()}

# Expressions qui contiennent un mot de diplôme sans en être un ; retirées de la ligne avant l'analyse.
_FAUX_DIPLOMES = re.compile(
    r"scrum[\s-]*master|master[\s-]*class|webmaster|master[\s-]*data|quartier[\s-]*maitre|"
    r"licence[s]? (?:microsoft|logiciel|d'exploitation|de transport)|permis",
)

# Ordre important : « ingénieur des travaux » et « bac+5 » doivent être lus avant « ingénieur » et « bac ».
_MOTIFS: list[tuple[int, re.Pattern[str]]] = [
    (4, re.compile(r"\bdoctorat\b|\bdoctorate\b|\bph\.?\s?d\b")),
    (2, re.compile(r"\bingenieur (?:des|de) travaux\b")),
    (3, re.compile(r"\bbac\s*\+\s*5\b|\bmasters?\b|\bmastere\b|\bmba\b|\bm2\b|\bmsc\b|\bdea\b|\bdess\b|"
                   r"\bdiplome d'?\s?ingenieur\b|\bingenieur de conception\b|\bingenieur\b")),
    (2, re.compile(r"\bbac\s*\+\s*[34]\b|\blicence\b|\bbachelor'?s?\b|\bb\.?sc\b|\bmaitrise\b|\bm1\b")),
    (1, re.compile(r"\bbac\s*\+\s*2\b|\bbts\b|\bdut\b|\bdts\b|\bhnd\b|\bhigher national diploma\b|\bdeug\b|"
                   r"\bbrevet de technicien superieur\b")),
    (0, re.compile(r"\bbaccalaureat\b|\bbac\b(?!\s*\+)|\bgce\s*a[\s/-]*level\b|\ba[\s-]level\b")),
]

# Indices qu'un diplôme n'est pas (encore) obtenu.
EN_COURS = re.compile(
    r"\ben cours\b|\ben preparation\b|\bactuellement\b|\bprepar(?:e|ation)\b|\bcandidat\b|\bprevu\b|"
    r"\battendu\b|\bexpected\b|\bongoing\b|\bin progress\b|\betudiant\b|\bniveau\b|\b(?:1|2|3)(?:ere|e|eme)? annee\b"
)


def niveau_dans_ligne(ligne_normalisee: str) -> int | None:
    """Niveau le plus élevé cité dans une ligne normalisée, ou None."""
    ligne = _FAUX_DIPLOMES.sub(" ", ligne_normalisee)
    trouves = []
    for niveau, motif in _MOTIFS:
        correspondance = motif.search(ligne)
        if correspondance:
            trouves.append(niveau)
            ligne = ligne[: correspondance.start()] + " " + ligne[correspondance.end():]  # évite une double lecture
    return max(trouves) if trouves else None
