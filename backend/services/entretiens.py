"""Entretiens vidéo côté recruteur : invitation, cycle de vie, consentement, alertes anti-triche, résultats.

Cycle de vie : planifie -> en_cours -> termine ; un entretien planifié ou en cours peut être annulé.
Le score d'entretien reste un indicateur (le regard surtout) : il ne modifie ni le score CV ni la décision du recruteur.
La transcription est chiffrée en base avec la clé de données de la session, comme les textes des CV.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Callable

from ..database.repositories import CandidatureRepository, EntretienRepository, PosteRepository
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


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


class EntretiensService:
    def __init__(
        self,
        entretiens: EntretienRepository,
        candidatures: CandidatureRepository,
        postes: PosteRepository,
        cle: Callable[[], bytes | None],
    ) -> None:
        self.entretiens = entretiens
        self.candidatures = candidatures
        self.postes = postes
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

    def _resume(self, e: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": e["id"],
            "candidature_id": e["candidature_id"],
            "poste_id": e["poste_id"],
            "code_invitation": e["code_invitation"],
            "date_entretien": e["date_entretien"],
            "statut": e["statut"],
            "consentement_enregistrement": e["consentement_enregistrement"],
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
