"""Réglages des mails aux candidats : modèles (objet et corps) et mode test.

Mode test : tous les mails partent vers une adresse de redirection, avec le vrai destinataire rappelé au début de
l'objet. Actif par défaut en développement (INJARA_ENVIRONNEMENT, fourni par Electron), inactif dans l'application
installée, tant que l'entreprise ne l'a pas réglé elle-même.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any

from ..database.repositories import ParametreRepository
from . import modeles_mail as m
from .erreurs import ErreurValidation
from .validation import email_valide

CLE_MODELE = "mails.modele.{}"
CLE_MODE_TEST = "mails.mode_test"
CLE_SMTP = "mails.serveur_smtp"
_HOTE = re.compile(r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$")
EXEMPLE = {
    "civilite_nom": "Awa Ndong",
    "poste": "Développeur Python",
    "entreprise": "Votre entreprise",
    "duree": "1 heure",
    "lieu": "Immeuble Les Cocotiers, Bonapriso, Douala",
    "message": "Merci de vous munir d'une pièce d'identité.",
}


class ReglagesMailsService:
    def __init__(self, parametres: ParametreRepository, environnement: str = "developpement") -> None:
        self.parametres = parametres
        self.environnement = environnement

    # --- Modèles -----------------------------------------------------------------------------------------------

    def modele(self, type_: str) -> dict[str, Any]:
        brut = self.parametres.get(CLE_MODELE.format(type_))
        if brut:
            return {**json.loads(brut), "par_defaut": False}
        return {**m.MODELES_PAR_DEFAUT[type_], "par_defaut": True}

    def enregistrer_modele(self, type_: str, objet: str, corps: str) -> dict[str, Any]:
        self._type(type_)
        objet, corps = (objet or "").strip(), (corps or "").strip()
        erreurs = {}
        if not objet:
            erreurs["objet"] = "L'objet est obligatoire."
        elif len(objet) > m.LONGUEUR_MAX_OBJET:
            erreurs["objet"] = f"L'objet ne doit pas dépasser {m.LONGUEUR_MAX_OBJET} caractères."
        if not corps:
            erreurs["corps"] = "Le texte du mail est obligatoire."
        elif len(corps) > m.LONGUEUR_MAX_CORPS:
            erreurs["corps"] = f"Le texte ne doit pas dépasser {m.LONGUEUR_MAX_CORPS} caractères."
        for champ, texte in (("objet", objet), ("corps", corps)):
            inconnues = m.variables_inconnues(texte)
            if inconnues and champ not in erreurs:
                erreurs[champ] = "Variable inconnue : " + ", ".join("{" + v + "}" for v in inconnues) + "."
        if erreurs:
            raise ErreurValidation(erreurs)
        self.parametres.set(CLE_MODELE.format(type_), json.dumps({"objet": objet, "corps": corps}, ensure_ascii=False))
        return self.consulter()

    def retablir_modele(self, type_: str) -> dict[str, Any]:
        self._type(type_)
        self.parametres.supprimer(CLE_MODELE.format(type_))
        return self.consulter()

    # --- Mode test ---------------------------------------------------------------------------------------------

    def mode_test(self) -> dict[str, Any]:
        brut = self.parametres.get(CLE_MODE_TEST)
        if brut:
            return {**json.loads(brut), "par_defaut": False}
        return {"actif": self.environnement != "production", "adresse": "", "par_defaut": True}

    def definir_mode_test(self, actif: bool, adresse: str | None) -> dict[str, Any]:
        adresse = (adresse or "").strip().lower()
        if adresse and not email_valide(adresse):
            raise ErreurValidation({"adresse": "Adresse email invalide."})
        if actif and not adresse:
            raise ErreurValidation({"adresse": "Indiquez l'adresse qui recevra les mails en mode test."})
        self.parametres.set(CLE_MODE_TEST, json.dumps({"actif": bool(actif), "adresse": adresse}))
        return self.consulter()

    # --- Serveur d'envoi (boîtes liées par IMAP) ----------------------------------------------------------------

    def serveur_smtp(self) -> dict | None:
        """{"hote", "port"} saisis par l'entreprise, ou None : détection automatique."""
        brut = self.parametres.get(CLE_SMTP)
        return json.loads(brut) if brut else None

    def definir_serveur_smtp(self, hote: str | None, port: int | None) -> dict | None:
        hote = (hote or "").strip().lower()
        if not hote:
            self.parametres.supprimer(CLE_SMTP)  # retour à la détection automatique
            return None
        erreurs = {}
        if not _HOTE.match(hote):
            erreurs["hote"] = "Adresse de serveur invalide (exemple : smtp.mondomaine.cm)."
        if port is None or not 1 <= int(port) <= 65535:
            erreurs["port"] = "Port invalide (465 ou 587 en général)."
        if erreurs:
            raise ErreurValidation(erreurs)
        self.parametres.set(CLE_SMTP, json.dumps({"hote": hote, "port": int(port)}))
        return self.serveur_smtp()

    # --- Ensemble ----------------------------------------------------------------------------------------------

    def consulter(self) -> dict[str, Any]:
        return {
            "modeles": {t: self.modele(t) for t in m.TYPES_MODELES},
            "variables": list(m.VARIABLES),
            "mode_test": self.mode_test(),
            "environnement": self.environnement,
        }

    def apercu(self, type_: str, objet: str, corps: str, entreprise: str | None = None) -> dict[str, str]:
        """Le modèle rempli avec des valeurs d'exemple (avant même de l'enregistrer)."""
        self._type(type_)
        debut = (datetime.now().astimezone() + timedelta(days=7)).replace(hour=10, minute=0, second=0, microsecond=0)
        valeurs = {**EXEMPLE, "entreprise": entreprise or EXEMPLE["entreprise"], "date": m.formater_date(debut), "heure": m.formater_heure(debut)}
        return {"objet": m.remplir(objet, valeurs), "corps": m.remplir(corps, valeurs)}

    @staticmethod
    def _type(type_: str) -> None:
        if type_ not in m.TYPES_MODELES:
            raise ErreurValidation({"type": "Modèle inconnu."})
