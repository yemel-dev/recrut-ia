"""Entretiens vidéo côté recruteur : invitation, cycle de vie, consentement, alertes anti-triche, résultats.

Cycle de vie : planifie -> en_cours -> termine ; un entretien planifié ou en cours peut être annulé.
Le score d'entretien reste un indicateur (le regard surtout) : il ne modifie ni le score CV ni la décision du recruteur.
La transcription est chiffrée en base avec la clé de données de la session, comme les textes des CV.
Le candidat n'a pas de session : il accède à son entretien par le code du lien (valide jusqu'à `expire_le`) et donne
lui-même son consentement. L'enregistrement n'est accepté qu'après ce consentement ; il est chiffré morceau par morceau.
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
TYPES_ALERTE = ("application_suspecte", "perte_focus", "surveillance_interrompue")
TRANSITIONS = {
    "en_cours": ("planifie",),
    "termine": ("en_cours",),
    "annule": ("planifie", "en_cours"),
}
LONGUEUR_MAX_RESUME = 4000
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

    def planifier(self, candidature_id: int, date_entretien: datetime | None = None) -> dict[str, Any]:
        candidature = self.candidatures.get(candidature_id)
        if candidature is None:
            raise Introuvable("Cette candidature n'existe pas.")
        if any(e["statut"] in ("planifie", "en_cours") for e in self.entretiens.lister(candidature_id)):
            raise Conflit("Un entretien est déjà prévu pour cette candidature.")
        if date_entretien is not None and date_entretien.tzinfo is None:
            date_entretien = date_entretien.replace(tzinfo=timezone.utc)
        entretien = self.entretiens.creer(
            candidature_id=candidature_id,
            poste_id=candidature["poste_id"],
            code_invitation=secrets.token_urlsafe(12),
            date_entretien=date_entretien,
            expire_le=(date_entretien or _maintenant()) + VALIDITE_LIEN,
        )
        return self._resume(entretien)

    def lister(self, candidature_id: int | None = None, statut: str | None = None) -> list[dict[str, Any]]:
        if statut is not None and statut not in STATUTS:
            raise ErreurValidation({"statut": "Statut inconnu."})
        return [self._resume(e) for e in self.entretiens.lister(candidature_id, statut)]

    def consulter(self, entretien_id: int) -> dict[str, Any]:
        entretien = self._get(entretien_id)
        alertes = self.entretiens.alertes(entretien_id)
        return {
            **self._resume(entretien),
            "resume": entretien["resume"],
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

    def consentement_candidat(self, code: str, accepte: bool) -> dict[str, Any]:
        entretien = self.entretien_du_lien(code)
        self.entretiens.maj(entretien["id"], consentement_enregistrement=accepte, consentement_le=_maintenant())
        return self.presenter_au_candidat(code)

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
        nom = entretien["fichier_enregistrement"] or f"entretien-{entretien_id}.webm.injara"
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
            "debut_le": e["debut_le"],
            "fin_le": e["fin_le"],
            "score_regard": e["score_regard"],
            "score_contenu": e["score_contenu"],
            "score_confiance": e["score_confiance"],
            "score_entretien": e["score_entretien"],
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


def _score_entretien(regard: float | None, contenu: float | None, confiance: float | None) -> float | None:
    """Moyenne pondérée ; si une composante manque, les poids des autres sont ramenés à 100 %."""
    poids = ((regard, 0.30), (contenu, 0.40), (confiance, 0.30))
    presentes = [(v, p) for v, p in poids if v is not None]
    if not presentes:
        return None
    return round(sum(v * p for v, p in presentes) / sum(p for _, p in presentes), 1)
