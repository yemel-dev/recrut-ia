"""Modèles des mails aux candidats et remplacement des variables.

Deux modèles, modifiables par l'entreprise : invitation à un entretien et réponse négative. Le mail de modification
(date d'entretien changée après l'invitation) reprend le modèle d'invitation, avec un objet et une phrase d'annonce.

Variables : {civilite_nom}, {poste}, {entreprise}, {date}, {heure}, {duree}, {lieu}, {message}.
- {civilite_nom} : le nom extrait du CV s'il semble fiable, sinon « Madame, Monsieur » (le genre n'est jamais deviné) ;
- {date}, {heure} : à l'heure locale de l'ordinateur du recruteur ;
- une ligne qui ne contient que {message} disparaît quand le message est vide.
Aucun modèle ne contient de score, de classement ni d'analyse automatique : seules ces variables existent.
"""
from __future__ import annotations

import re
from datetime import datetime

from ..ia.extraction import _MOTS_PAS_UN_NOM, _section_du_titre
from ..ia.texte import normaliser

INVITATION, MODIFICATION, REFUS = "invitation", "modification", "refus"
TYPES_MODELES = (INVITATION, REFUS)
VARIABLES = ("civilite_nom", "poste", "entreprise", "date", "heure", "duree", "lieu", "message")
CIVILITE_PAR_DEFAUT = "Madame, Monsieur"
LONGUEUR_MAX_OBJET = 200
LONGUEUR_MAX_CORPS = 5000

MODELES_PAR_DEFAUT = {
    INVITATION: {
        "objet": "Votre candidature au poste de {poste} – invitation à un entretien",
        "corps": (
            "Bonjour {civilite_nom},\n\n"
            "Nous avons étudié votre candidature au poste de {poste} et nous souhaitons vous rencontrer.\n\n"
            "Nous vous proposons un entretien le {date} à {heure}, pour une durée d'environ {duree}. Lieu : {lieu}.\n\n"
            "{message}\n\n"
            "Merci de confirmer votre présence en répondant à ce mail. Si cette date ne vous convient pas, "
            "indiquez-nous vos disponibilités.\n\n"
            "Cordialement,\n"
            "{entreprise}"
        ),
    },
    REFUS: {
        "objet": "Votre candidature au poste de {poste}",
        "corps": (
            "Bonjour {civilite_nom},\n\n"
            "Nous vous remercions de l'intérêt que vous portez à {entreprise} et du temps consacré à votre candidature "
            "au poste de {poste}.\n\n"
            "Après étude de votre dossier, nous ne donnons pas suite à votre candidature pour ce poste.\n\n"
            "Nous vous souhaitons une pleine réussite dans vos recherches.\n\n"
            "Cordialement,\n"
            "{entreprise}"
        ),
    },
}

# Mail de modification : modèle d'invitation, précédé de cette annonce.
OBJET_MODIFICATION = "Modification de votre entretien – poste de {poste}"
ANNONCE_MODIFICATION = "La date de votre entretien a changé. Voici les nouvelles informations."

_VARIABLE = re.compile(r"\{([a-z_]+)\}")
_NOM_FIABLE = re.compile(r"[^\W\d_]+(?:['-][^\W\d_]+)*")
_JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
_MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre")


def variables_inconnues(texte: str) -> list[str]:
    return sorted({v for v in _VARIABLE.findall(texte or "") if v not in VARIABLES})


def civilite_nom(nom_extrait_du_cv: str | None) -> str:
    """Le nom lu dans le CV s'il a la forme d'un nom, sinon « Madame, Monsieur ».

    Fiable : 2 à 4 mots de lettres, sans mot de métier ni titre de section (« Expérience Professionnelle »).
    """
    mots = (nom_extrait_du_cv or "").split()
    if not 2 <= len(mots) <= 4 or len(nom_extrait_du_cv) > 60 or not all(_NOM_FIABLE.fullmatch(mot) for mot in mots):
        return CIVILITE_PAR_DEFAUT
    norm = normaliser(nom_extrait_du_cv)
    if _MOTS_PAS_UN_NOM.search(norm) or _section_du_titre(norm) or any(_section_du_titre(mot) for mot in norm.split()):
        return CIVILITE_PAR_DEFAUT
    return " ".join(mots)


def formater_date(debut: datetime) -> str:
    local = debut.astimezone()
    return f"{_JOURS[local.weekday()]} {local.day}{'er' if local.day == 1 else ''} {_MOIS[local.month - 1]} {local.year}"


def formater_heure(debut: datetime) -> str:
    local = debut.astimezone()
    return f"{local.hour} h {local.minute:02d}"


def formater_duree(minutes: int) -> str:
    heures, reste = divmod(int(minutes), 60)
    if not heures:
        return f"{reste} minutes"
    return f"{heures} h {reste:02d}" if reste else f"{heures} heure{'s' if heures > 1 else ''}"


def formater_lieu(mode: str, adresse: str | None, lien: str | None = None) -> str:
    """Sur site : l'adresse. En ligne : le lien de la visio d'INJARA, que le candidat ouvre dans son navigateur."""
    if mode == "en_ligne":
        return f"en ligne, par visioconférence : {lien}" if lien else "en ligne (le lien de connexion vous sera communiqué)"
    return (adresse or "").strip() or "dans nos locaux"


def remplir(modele: str, valeurs: dict[str, str]) -> str:
    """Remplace les variables ; une ligne réduite à {message} disparaît si le message est vide."""
    lignes = []
    for ligne in (modele or "").splitlines():
        if ligne.strip() == "{message}" and not (valeurs.get("message") or "").strip():
            continue
        lignes.append(_VARIABLE.sub(lambda m: str(valeurs.get(m.group(1), m.group(0))), ligne))
    texte = "\n".join(lignes)
    return re.sub(r"\n{3,}", "\n\n", texte).strip()
