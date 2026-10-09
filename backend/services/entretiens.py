"""Entretiens vidéo côté recruteur : invitation, cycle de vie, consentement, alertes anti-triche, résultats.

Cycle de vie : planifie -> en_cours -> termine ; un entretien planifié ou en cours peut être annulé.
Le score d'entretien reste un indicateur (le regard surtout) : il ne modifie ni le score CV ni la décision du recruteur.
La transcription est chiffrée en base avec la clé de données de la session, comme les textes des CV.
Le candidat n'a pas de session : il accède à son entretien par le code du lien (valide jusqu'à `expire_le`) et donne
lui-même son consentement. L'enregistrement n'est accepté qu'après ce consentement ; il est chiffré morceau par morceau.

Planification annoncée au candidat (mails aux candidats) : durée, mode (en ligne : la visio d'INJARA ; sur site : une
adresse), message facultatif chiffré. Une date passée est refusée ; un chevauchement avec un autre entretien est signalé
sans bloquer. Le candidat confirme en répondant au mail : le recruteur le note (`confirme_le`). Changer la date remet
cette confirmation à zéro.
"""
from __future__ import annotations

import secrets
from itertools import chain
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

from ..database.repositories import CandidatureRepository, EntretienRepository, EntrepriseRepository, PosteRepository
from . import coffre
from .erreurs import Conflit, ErreurValidation, Introuvable, SessionRequise

STATUTS = ("planifie", "en_cours", "termine", "annule")
TYPES_ALERTE = (
    "application_suspecte", "perte_focus", "surveillance_interrompue",
    "regard_detourne", "visage_absent", "plusieurs_visages",  # relevées par l'analyse du regard (services/regard.py)
    "sortie_plein_ecran", "plusieurs_ecrans",  # relevées par la page du candidat (perte_focus l'est aussi)
)
# Ce que la page du candidat a le droit de signaler : « application_suspecte » et « surveillance_interrompue » sont
# réservés à un éventuel programme compagnon, de confiance, qui verrait les processus de l'ordinateur.
SIGNAUX_CANDIDAT = ("perte_focus", "sortie_plein_ecran", "plusieurs_ecrans")
MAX_SIGNAUX_CANDIDAT = 300  # par entretien : la route est publique, elle ne doit pas permettre de saturer la base
TRANSITIONS = {
    "en_cours": ("planifie",),
    "termine": ("en_cours",),
    "annule": ("planifie", "en_cours"),
}
LONGUEUR_MAX_RESUME = 4000
MODES = ("en_ligne", "sur_site")
DUREE_MIN, DUREE_MAX = 15, 480
LONGUEUR_MAX_MESSAGE = 1000
LONGUEUR_MAX_ADRESSE = 300
VALIDITE_LIEN = timedelta(days=7)  # après la date prévue (ou la création, sans date)
TAILLE_MAX_MORCEAU = 16 * 1024 * 1024


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


class EntretiensService:
    def __init__(
        self,
        entretiens: EntretienRepository,
        candidatures: CandidatureRepository,
        postes: PosteRepository,
        cle: Callable[[], bytes | None],
        entreprise: EntrepriseRepository,
        dossier_enregistrements: Path,
    ) -> None:
        self.entretiens = entretiens
        self.candidatures = candidatures
        self.postes = postes
        self.entreprise = entreprise
        self.dossier_enregistrements = dossier_enregistrements
        self._cle_session = cle

    def planifier(
        self,
        candidature_id: int,
        date_entretien: datetime | None = None,
        duree_minutes: int = 60,
        mode: str = "en_ligne",
        adresse: str | None = None,
        message: str | None = None,
    ) -> dict[str, Any]:
        candidature = self.candidatures.get(candidature_id)
        if candidature is None:
            raise Introuvable("Cette candidature n'existe pas.")
        if any(e["statut"] in ("planifie", "en_cours") for e in self.entretiens.lister(candidature_id)):
            raise Conflit("Un entretien est déjà prévu pour cette candidature.")
        date_entretien = _en_utc(date_entretien)
        champs = self._planification(date_entretien, duree_minutes, mode, adresse, message, date_verifiee=True)
        entretien = self.entretiens.creer(
            candidature_id=candidature_id,
            poste_id=candidature["poste_id"],
            code_invitation=secrets.token_urlsafe(12),
            date_entretien=date_entretien,
            expire_le=(date_entretien or _maintenant()) + VALIDITE_LIEN,
            **champs,
        )
        return self._detail(entretien)

    def replanifier(
        self,
        entretien_id: int,
        date_entretien: datetime | None,
        duree_minutes: int = 60,
        mode: str = "en_ligne",
        adresse: str | None = None,
        message: str | None = None,
    ) -> dict[str, Any]:
        """Change la date, la durée, le lieu ou le message d'un entretien planifié. Aucun mail ne part."""
        entretien = self._get(entretien_id)
        if entretien["statut"] != "planifie":
            raise Conflit("Seul un entretien planifié peut être modifié.")
        date_entretien = _en_utc(date_entretien)
        date_changee = date_entretien != entretien["date_entretien"]
        champs = self._planification(date_entretien, duree_minutes, mode, adresse, message, date_verifiee=date_changee)
        if date_changee:
            champs.update(date_entretien=date_entretien, expire_le=(date_entretien or _maintenant()) + VALIDITE_LIEN, confirme_le=None)
        return self._detail(self.entretiens.maj(entretien_id, **champs))

    def confirmer(self, entretien_id: int, confirme: bool = True) -> dict[str, Any]:
        """Le candidat a confirmé sa présence (en répondant au mail) : le recruteur le note."""
        entretien = self._get(entretien_id)
        if entretien["statut"] != "planifie":
            raise Conflit("Seul un entretien planifié peut être confirmé.")
        return self._detail(self.entretiens.maj(entretien_id, confirme_le=_maintenant() if confirme else None))

    def _planification(self, date_entretien, duree_minutes, mode, adresse, message, date_verifiee: bool) -> dict[str, Any]:
        adresse = (adresse or "").strip() or None
        message = (message or "").strip() or None
        erreurs = {}
        if date_verifiee and date_entretien is not None and date_entretien <= _maintenant():
            erreurs["date_entretien"] = "La date de l'entretien est déjà passée."
        if not DUREE_MIN <= int(duree_minutes) <= DUREE_MAX:
            erreurs["duree_minutes"] = f"La durée doit être comprise entre {DUREE_MIN} minutes et {DUREE_MAX // 60} heures."
        if mode not in MODES:
            erreurs["mode"] = "Choisissez en ligne ou sur site."
        elif mode == "sur_site" and not adresse:
            erreurs["adresse"] = "Indiquez l'adresse de l'entretien."
        if adresse and len(adresse) > LONGUEUR_MAX_ADRESSE:
            erreurs["adresse"] = f"L'adresse ne doit pas dépasser {LONGUEUR_MAX_ADRESSE} caractères."
        if message and len(message) > LONGUEUR_MAX_MESSAGE:
            erreurs["message"] = f"Le message ne doit pas dépasser {LONGUEUR_MAX_MESSAGE} caractères."
        if erreurs:
            raise ErreurValidation(erreurs)
        return {
            "duree_minutes": int(duree_minutes),
            "mode": mode,
            "adresse": adresse if mode == "sur_site" else None,
            "message": coffre.chiffrer_texte(message, self._cle()) if message else None,
        }

    def _detail(self, entretien: dict[str, Any]) -> dict[str, Any]:
        """Résumé, plus les entretiens qui chevauchent celui-ci (avertissement, jamais bloquant)."""
        resume = self._resume(entretien)
        debut = entretien["date_entretien"]
        if debut is None:
            return {**resume, "chevauchements": []}
        fin = debut + timedelta(minutes=entretien["duree_minutes"] or 60)
        return {
            **resume,
            "chevauchements": [
                {"candidat": c["candidat"], "poste_intitule": c["poste_intitule"], "date_entretien": c["date_entretien"], "duree_minutes": c["duree_minutes"]}
                for c in self.entretiens.chevauchements(debut, fin, sauf_id=entretien["id"])
            ],
        }

    def message_en_clair(self, entretien: dict[str, Any]) -> str | None:
        cle = self._cle_session()
        return coffre.dechiffrer_texte(entretien.get("message"), cle) if cle else None

    def lister(self, candidature_id: int | None = None, statut: str | None = None) -> list[dict[str, Any]]:
        if statut is not None and statut not in STATUTS:
            raise ErreurValidation({"statut": "Statut inconnu."})
        return [self._resume(e) for e in self.entretiens.lister(candidature_id, statut)]

    def consulter(self, entretien_id: int) -> dict[str, Any]:
        entretien = self._get(entretien_id)
        alertes = self.entretiens.alertes(entretien_id)
        return {
            **self._detail(entretien),
            "resume": entretien["resume"],
            "bilan_regard": entretien["bilan_regard"],
            "transcription": coffre.dechiffrer_texte(entretien["transcription"], self._cle()),
            "alertes": [{"id": a["id"], "type": a["type_alerte"], "details": a["details"], "horodatage": a["horodatage"]} for a in alertes],
        }

    def changer_statut(self, entretien_id: int, statut: str) -> dict[str, Any]:
        entretien = self._get(entretien_id)
        if statut not in TRANSITIONS:
            raise ErreurValidation({"statut": "Statut inconnu."})
        if entretien["statut"] not in TRANSITIONS[statut]:
            raise Conflit("Ce changement de statut n'est pas possible pour cet entretien.")
        champs: dict[str, Any] = {"statut": statut}
        if statut == "en_cours":
            champs["debut_le"] = _maintenant()
        elif statut == "termine":
            champs["fin_le"] = _maintenant()
        return self._resume(self.entretiens.maj(entretien_id, **champs))

    def enregistrer_consentement(self, entretien_id: int, accepte: bool) -> dict[str, Any]:
        entretien = self._get(entretien_id)
        if entretien["statut"] not in ("planifie", "en_cours"):
            raise Conflit("Le consentement ne peut plus être modifié pour cet entretien.")
        return self._resume(
            self.entretiens.maj(entretien_id, consentement_enregistrement=accepte, consentement_le=_maintenant())
        )

    def signaler_alerte(self, entretien_id: int, type_alerte: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        entretien = self._get(entretien_id)
        if type_alerte not in TYPES_ALERTE:
            raise ErreurValidation({"type": "Type d'alerte inconnu."})
        if entretien["statut"] != "en_cours":
            raise Conflit("Les alertes ne sont relevées que pendant l'entretien.")
        alerte = self.entretiens.ajouter_alerte(entretien_id, type_alerte, details or {})
        return {"id": alerte["id"], "type": alerte["type_alerte"], "details": alerte["details"], "horodatage": alerte["horodatage"]}

    def enregistrer_resultats(
        self,
        entretien_id: int,
        score_regard: float | None = None,
        score_contenu: float | None = None,
        score_confiance: float | None = None,
        transcription: str | None = None,
        resume: str | None = None,
    ) -> dict[str, Any]:
        """Résultats de l'analyse. Le score d'entretien est recalculé : regard 30 %, contenu 40 %, confiance 30 %."""
        entretien = self._get(entretien_id)
        erreurs = {}
        for nom, valeur in (("score_regard", score_regard), ("score_contenu", score_contenu), ("score_confiance", score_confiance)):
            if valeur is not None and not 0 <= valeur <= 100:
                erreurs[nom] = "Le score doit être compris entre 0 et 100."
        resume = (resume or "").strip() or None
        if resume and len(resume) > LONGUEUR_MAX_RESUME:
            erreurs["resume"] = f"Le résumé ne doit pas dépasser {LONGUEUR_MAX_RESUME} caractères."
        if erreurs:
            raise ErreurValidation(erreurs)
        champs: dict[str, Any] = {"resume": resume}
        for nom, valeur in (("score_regard", score_regard), ("score_contenu", score_contenu), ("score_confiance", score_confiance)):
            champs[nom] = valeur if valeur is not None else entretien[nom]
        champs["score_entretien"] = _score_entretien(champs["score_regard"], champs["score_contenu"], champs["score_confiance"])
        if transcription is not None:
            champs["transcription"] = coffre.chiffrer_texte(transcription, self._cle())
        self.entretiens.maj(entretien_id, **champs)
        return self.consulter(entretien_id)

    # --- Côté candidat : accès par le code du lien, sans session --------------------------------------------

    def entretien_du_lien(self, code: str) -> dict[str, Any]:
        """L'entretien d'un lien encore valable. Même message pour un code inconnu, expiré ou d'un entretien clos."""
        return self._verifier_lien(self.entretiens.get_par_code(code) if code else None)

    def pour_invitation(self, entretien_id: int) -> dict[str, Any]:
        """L'entretien du recruteur, à condition que son lien soit encore valable (pour donner le lien ou ouvrir la salle)."""
        return self._verifier_lien(self._get(entretien_id))

    @staticmethod
    def _verifier_lien(entretien: dict[str, Any] | None) -> dict[str, Any]:
        if (
            entretien is None
            or entretien["statut"] not in ("planifie", "en_cours")
            or (entretien["expire_le"] is not None and entretien["expire_le"] < _maintenant())
        ):
            raise Introuvable("Ce lien d'entretien est invalide ou a expiré.")
        return entretien

    def presenter_au_candidat(self, code: str) -> dict[str, Any]:
        entretien = self.entretien_du_lien(code)
        poste = self.postes.get(entretien["poste_id"]) if entretien["poste_id"] else None
        entreprise = self.entreprise.get() or {}
        return {
            "entreprise": entreprise.get("nom") or "",
            "poste": poste["intitule"] if poste else "",
            "date_entretien": entretien["date_entretien"],
            "statut": entretien["statut"],
            "consentement_enregistrement": entretien["consentement_enregistrement"],
        }

    def consentement_candidat(self, code: str, accepte: bool, consignes: bool = False) -> dict[str, Any]:
        entretien = self.entretien_du_lien(code)
        champs: dict[str, Any] = {"consentement_enregistrement": accepte, "consentement_le": _maintenant()}
        if consignes:
            champs["consignes_acceptees_le"] = _maintenant()
        self.entretiens.maj(entretien["id"], **champs)
        return self.presenter_au_candidat(code)

    def signal_candidat(self, code: str, type_signal: str, details: dict[str, Any]) -> bool:
        """Signal de vigilance envoyé par la page du candidat (il quitte la page, le plein écran, a un second écran).

        Pas de session : le code du lien suffit, mais seulement pour ces signaux, pendant l'entretien et avec le
        consentement du candidat. Renvoie False si le signal est ignoré (la page n'a pas à s'en préoccuper).
        """
        entretien = self.entretien_du_lien(code)
        if type_signal not in SIGNAUX_CANDIDAT:
            raise ErreurValidation({"type": "Signal inconnu."})
        if entretien["statut"] != "en_cours" or not entretien["consentement_enregistrement"]:
            return False
        if len(self.entretiens.alertes(entretien["id"])) >= MAX_SIGNAUX_CANDIDAT:
            return False
        self.entretiens.ajouter_alerte(entretien["id"], type_signal, details)
        return True

    # --- Enregistrement : chiffré au fil de l'eau, jamais en clair sur le disque -----------------------------

    def ajouter_enregistrement(self, entretien_id: int, donnees: bytes) -> None:
        entretien = self._get(entretien_id)
        if not entretien["consentement_enregistrement"]:
            raise Conflit("Le candidat n'a pas consenti à l'enregistrement.")
        if entretien["statut"] != "en_cours":
            raise Conflit("L'enregistrement n'est possible que pendant l'entretien.")
        if not donnees:
            raise ErreurValidation({"enregistrement": "Morceau vide."})
        if len(donnees) > TAILLE_MAX_MORCEAU:
            raise ErreurValidation({"enregistrement": "Morceau trop volumineux."})
        cle = self._cle()
        nom = entretien["fichier_enregistrement"] or f"entretien-{entretien_id}.{_format_video(donnees)}.injara"
        self.dossier_enregistrements.mkdir(parents=True, exist_ok=True)
        coffre.ajouter_morceau(self.dossier_enregistrements / nom, donnees, cle)
        if not entretien["fichier_enregistrement"]:
            self.entretiens.maj(entretien_id, fichier_enregistrement=nom)

    def lire_enregistrement(self, entretien_id: int) -> Iterator[bytes]:
        """Enregistrement déchiffré, morceau par morceau (le fichier complet n'est jamais chargé en mémoire)."""
        entretien = self._get(entretien_id)
        nom = entretien["fichier_enregistrement"]
        chemin = self.dossier_enregistrements / nom if nom else None
        if chemin is None or not chemin.is_file():
            raise Introuvable("Cet entretien n'a pas d'enregistrement.")
        cle = self._cle()
        morceaux = coffre.lire_morceaux(chemin, cle)
        try:
            premier = next(morceaux, b"")  # une clé ou un fichier invalide se voit dès le premier morceau, avant l'envoi
        except coffre.Indechiffrable:
            raise Conflit("L'enregistrement est illisible avec cette session.") from None
        return chain([premier], morceaux)

    def _resume(self, e: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": e["id"],
            "candidature_id": e["candidature_id"],
            "poste_id": e["poste_id"],
            "code_invitation": e["code_invitation"],
            "date_entretien": e["date_entretien"],
            "expire_le": e["expire_le"],
            "cree_le": e["cree_le"],
            "statut": e["statut"],
            "consentement_enregistrement": e["consentement_enregistrement"],
            "enregistrement": bool(e["fichier_enregistrement"]),
            "format_enregistrement": _format_video_nom(e["fichier_enregistrement"]),
            "consignes_acceptees_le": e["consignes_acceptees_le"],
            "debut_le": e["debut_le"],
            "fin_le": e["fin_le"],
            "score_regard": e["score_regard"],
            "score_contenu": e["score_contenu"],
            "score_confiance": e["score_confiance"],
            "score_entretien": e["score_entretien"],
            "duree_minutes": e["duree_minutes"],
            "mode": e["mode"],
            "adresse": e["adresse"],
            "message": self.message_en_clair(e),
            "confirme_le": e["confirme_le"],
        }

    def _get(self, entretien_id: int) -> dict[str, Any]:
        entretien = self.entretiens.get(entretien_id)
        if entretien is None:
            raise Introuvable("Cet entretien n'existe pas.")
        return entretien

    def _cle(self) -> bytes:
        cle = self._cle_session()
        if cle is None:
            raise SessionRequise("Vous devez être connecté.")
        return cle


def _en_utc(date: datetime | None) -> datetime | None:
    if date is None:
        return None
    date = date if date.tzinfo is not None else date.replace(tzinfo=timezone.utc)
    return date.astimezone(timezone.utc).replace(second=0, microsecond=0)


def _score_entretien(regard: float | None, contenu: float | None, confiance: float | None) -> float | None:
    """Moyenne pondérée ; si une composante manque, les poids des autres sont ramenés à 100 %."""
    poids = ((regard, 0.30), (contenu, 0.40), (confiance, 0.30))
    presentes = [(v, p) for v, p in poids if v is not None]
    if not presentes:
        return None
    return round(sum(v * p for v, p in presentes) / sum(p for _, p in presentes), 1)


def _format_video(premier_morceau: bytes) -> str:
    """Conteneur du premier morceau : MP4 (« ftyp » aux octets 4 à 8) ou, à défaut, WebM."""
    return "mp4" if premier_morceau[4:8] == b"ftyp" else "webm"


def _format_video_nom(nom: str | None) -> str | None:
    return None if not nom else "mp4" if ".mp4." in nom else "webm"
