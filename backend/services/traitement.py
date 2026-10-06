"""Pipeline de traitement des candidatures, en arrière-plan.

Étapes, journalisées une par une (journal « injara.traitement ») :
1. import : les CV récupérés par l'agent sont regroupés par mail (une candidature = un mail, CV principal choisi
   d'après le nom du fichier ; les autres pièces jointes servent de lettre de motivation) ;
2. lecture et extraction, une seule fois par CV (fichier illisible → statut « illisible », signalé) ;
3. score de chaque candidature pour chaque poste actif (et pour le poste choisi à la main, même inactif) ;
4. classement : poste cité dans le mail, sinon meilleur poste. Un choix manuel n'est jamais écrasé.

Quand un poste change, ses candidatures sont renotées à partir des données enregistrées, sans relire les CV.
Le traitement ne tourne que pendant une session (les CV seront chiffrés avec la clé de session).
"""
from __future__ import annotations

import logging
import re
import threading
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..database.repositories import CandidatureRepository, PosteRepository, ScoreRepository
from ..ia import classement, extraction, lecture, scoring, semantique
from ..ia.scoring import DonneesCV, DonneesPoste
from .agent_mail import AgentMailService

log = logging.getLogger("injara.traitement")

_NOM_CV = re.compile(r"\bcv\b|curriculum|resume|cv[_\-.]", re.IGNORECASE)
_NOM_LETTRE = re.compile(r"lettre|motivation|cover|\blm\b|lm[_\-.]", re.IGNORECASE)
LONGUEUR_MAX_LETTRE = 20_000


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def choisir_cv_principal(fichiers: list[dict]) -> tuple[dict, list[dict]]:
    """Parmi les pièces jointes d'un mail, le CV principal (d'après le nom) et les autres."""

    def note(fichier: dict) -> int:
        nom = Path(fichier["filename"]).stem
        return (2 if _NOM_CV.search(nom) else 0) - (2 if _NOM_LETTRE.search(nom) else 0)

    ordonnes = sorted(enumerate(fichiers), key=lambda paire: (-note(paire[1]), paire[0]))
    principal = ordonnes[0][1]
    return principal, [f for _, f in ordonnes[1:]]


class TraitementService:
    def __init__(
        self,
        candidatures: CandidatureRepository,
        scores: ScoreRepository,
        postes: PosteRepository,
        agent_mail: AgentMailService,
        modele: semantique.ModeleSemantique,
        aujourdhui: Callable[[], date] = date.today,
    ) -> None:
        self.candidatures = candidatures
        self.scores = scores
        self.postes = postes
        self.agent_mail = agent_mail
        self.modele = modele
        self.aujourdhui = aujourdhui
        self._demande = threading.Event()
        self._arret = threading.Event()
        self._fil: threading.Thread | None = None
        self._tout_renoter = True  # au démarrage, on vérifie tout une fois
        self._abonne_agent = False
        self._vecteurs_postes: dict[int, tuple[Any, list[float] | None]] = {}
        self._lock = threading.Lock()
        self._verrou = threading.RLock()  # un seul passage du pipeline à la fois
        self.en_cours = False
        self.derniere_execution: datetime | None = None
        self.derniere_erreur: str | None = None

    # ------------------------------------------------------------------ cycle de vie

    def demarrer(self) -> None:
        """À l'ouverture de session : lance le fil de travail et demande un premier passage."""
        with self._lock:
            if self._fil is None or not self._fil.is_alive():
                self._arret.clear()
                self._fil = threading.Thread(target=self._boucle, name="traitement-candidatures", daemon=True)
                self._fil.start()
        # Le modèle met jusqu'à deux minutes à se charger : les CV sont notés sans l'adéquation en attendant,
        # puis encodés et renotés au passage demandé ici.
        self.modele.precharger(lambda: self.demander("moteur d'analyse chargé"))
        self.demander("ouverture de session", tout_renoter=True)

    def arreter(self) -> None:
        self._arret.set()
        self._demande.set()
        fil = self._fil
        if fil is not None and fil is not threading.current_thread():
            fil.join(timeout=3)  # le passage en cours s'arrête à la candidature suivante

    def demander(self, raison: str, tout_renoter: bool = False) -> None:
        if tout_renoter:
            self._tout_renoter = True
        log.info("Traitement demandé : %s", raison)
        self._demande.set()

    def postes_modifies(self) -> None:
        self.demander("poste modifié", tout_renoter=True)

    def _boucle(self) -> None:
        while not self._arret.is_set():
            self._demande.wait()
            if self._arret.is_set():
                break
            self._demande.clear()
            try:
                self.traiter()
            except Exception as exc:  # le fil ne doit jamais mourir
                self.derniere_erreur = str(exc)
                log.exception("Traitement des candidatures en échec")

    def _sur_evenement_agent(self, evenement) -> None:
        if evenement.type == "new_cvs":
            self.demander(f"nouveaux CV ({evenement.message})")

    # ------------------------------------------------------------------ passage complet

    def traiter(self) -> dict[str, int]:
        """Un passage complet du pipeline (appelé par le fil de travail, ou directement dans les tests)."""
        with self._verrou:
            return self._traiter()

    def _traiter(self) -> dict[str, int]:
        self.en_cours = True
        debut = time.monotonic()
        try:
            importees = self.importer_depuis_agent()
            lues, illisibles = self.lire_et_extraire()
            vecteurs = self.completer_vecteurs()
            tout = self._tout_renoter or vecteurs > 0
            self._tout_renoter = False
            notees = self.noter_et_classer(tout=tout)
            self.derniere_execution = _maintenant()
            self.derniere_erreur = None
            bilan = {"importees": importees, "lues": lues, "illisibles": illisibles, "notees": notees}
            log.info("Traitement terminé en %.1f s : %s", time.monotonic() - debut, bilan)
            return bilan
        finally:
            self.en_cours = False

    # ------------------------------------------------------------------ étape 0 : import

    def importer_depuis_agent(self) -> int:
        agent = self.agent_mail.agent()
        if not self._abonne_agent:
            agent.subscribe(self._sur_evenement_agent)
            self._abonne_agent = True
        connues = self.candidatures.cles_connues()
        par_mail: dict[str, list] = {}
        decalage = 0
        while True:
            lot = agent.ledger.list_cvs(500, decalage)
            for cv in lot:
                if cv.message_id not in connues:
                    par_mail.setdefault(cv.message_id, []).append(cv)
            if len(lot) < 500:
                break
            decalage += 500
        for cle, cvs in par_mail.items():
            fichiers = [cv.model_dump(mode="json") for cv in sorted(cvs, key=lambda c: c.attachment_id)]
            principal, autres = choisir_cv_principal(fichiers)
            self.candidatures.creer(
                cle=cle,
                source=principal["source"],
                expediteur_nom=principal["sender_name"] or None,
                expediteur_email=principal["sender_email"] or None,
                objet=principal["subject"] if principal["source"] == "email" else None,
                corps=principal.get("body_excerpt") or None,
                recue_le=datetime.fromisoformat(principal["received_at"]),
                fichier_cv=principal["saved_path"],
                nom_fichier_cv=principal["filename"],
                sha256_cv=principal["sha256"],
                pieces_jointes=[{"nom": f["filename"], "chemin": f["saved_path"], "sha256": f["sha256"]} for f in autres],
            )
        if par_mail:
            log.info("Étape import : %d nouvelle(s) candidature(s)", len(par_mail))
        return len(par_mail)

    # ------------------------------------------------------------------ étapes 1 et 2 : lecture, extraction

    def lire_et_extraire(self) -> tuple[int, int]:
        lues = illisibles = 0
        for candidature_id in self.candidatures.ids_a_lire(extraction.VERSION_EXTRACTION):
            if self._arret.is_set():
                log.info("Étape lecture interrompue : fin de session")
                break
            candidature = self.candidatures.get(candidature_id)
            nom_fichier = candidature["nom_fichier_cv"]
            try:
                texte = lecture.lire_texte(candidature["fichier_cv"])
            except lecture.FichierIllisible as exc:
                illisibles += 1
                log.warning("Étape lecture ❌ candidature %d (%s) : %s", candidature_id, nom_fichier, exc.motif)
                self.candidatures.maj(
                    candidature_id,
                    statut_lecture="illisible",
                    motif_lecture=exc.motif,
                    statut_classement=candidature["statut_classement"] if candidature["mode_assignation"] == "manuel" else classement.NON_CLASSE,
                    motif_classement=candidature["motif_classement"] if candidature["mode_assignation"] == "manuel" else "CV illisible : à consulter directement.",
                )
                continue
            log.info("Étape lecture ✅ candidature %d (%s) : %d caractères", candidature_id, nom_fichier, len(texte))

            resultat = extraction.extraire(texte, self.aujourdhui())
            log.info(
                "Étape extraction ✅ candidature %d : expérience %d mois (+ %d mois de stage), diplôme %s",
                candidature_id, resultat.experience_mois, resultat.stages_mois, resultat.diplome.get("niveau") or "non trouvé",
            )
            vecteur = self.modele.encoder(texte) if self.modele.pret else None
            self.candidatures.maj(
                candidature_id,
                statut_lecture="lue",
                motif_lecture=None,
                texte=texte,
                texte_lettre=self._lire_lettres(candidature["pieces_jointes"]),
                extraction=resultat.en_dict(),
                nom=resultat.nom or candidature["expediteur_nom"],
                email=resultat.email or candidature["expediteur_email"],
                telephone=resultat.telephone,
                experience_mois=resultat.experience_mois,
                stages_mois=resultat.stages_mois,
                diplome_niveau=resultat.diplome.get("niveau"),
                version_extraction=extraction.VERSION_EXTRACTION,
                vecteur=semantique.en_octets(vecteur),
                modele_vecteur=self.modele.nom if vecteur is not None else None,
                extraite_le=_maintenant(),
                statut_classement=candidature["statut_classement"] if candidature["mode_assignation"] == "manuel" else "a_traiter",
            )
            lues += 1
        return lues, illisibles

    @staticmethod
    def _lire_lettres(pieces: list[dict]) -> str | None:
        textes = []
        for piece in pieces or []:
            try:
                textes.append(lecture.lire_texte(piece["chemin"]))
            except lecture.FichierIllisible:
                continue
        return "\n\n".join(textes)[:LONGUEUR_MAX_LETTRE] or None

    def completer_vecteurs(self) -> int:
        """Si le modèle est devenu disponible, encode les CV déjà lus (sans relire les fichiers)."""
        if not self.modele.pret:
            return 0
        n = 0
        for candidature in self.candidatures.lues():
            if candidature["vecteur"] is None or candidature["modele_vecteur"] != self.modele.nom:
                vecteur = self.modele.encoder(candidature["texte"] or "")
                self.candidatures.maj(candidature["id"], vecteur=semantique.en_octets(vecteur), modele_vecteur=self.modele.nom)
                n += 1
        if n:
            log.info("Étape vecteurs : %d CV encodé(s) pour l'adéquation", n)
        return n

    # ------------------------------------------------------------------ étapes 3 et 4 : score et classement

    def _donnees_poste(self, poste: dict) -> DonneesPoste:
        cle_cache = (poste["modifie_le"], self.modele.pret)  # recalculé quand le modèle devient prêt
        cache = self._vecteurs_postes.get(poste["id"])
        if cache is None or cache[0] != cle_cache:
            texte = "\n".join([poste["intitule"], poste["description"], ", ".join(poste["competences_requises"] or [])])
            cache = (cle_cache, self.modele.encoder(texte) if self.modele.pret else None)
            self._vecteurs_postes[poste["id"]] = cache
        return DonneesPoste(
            competences=list(poste["competences_requises"] or []),
            experience_min_annees=poste["experience_min_annees"] or 0,
            niveau_formation=poste["niveau_formation"],
            poids={
                "competences": poste["poids_competences"],
                "experience": poste["poids_experience"],
                "formation": poste["poids_formation"],
                "adequation": poste["poids_adequation"],
            },
            vecteur=cache[1],
        )

    @staticmethod
    def donnees_cv(candidature: dict) -> DonneesCV:
        diplome = (candidature["extraction"] or {}).get("diplome") or {}
        return DonneesCV(
            texte=candidature["texte"] or "",
            experience_mois=candidature["experience_mois"] or 0,
            diplome_niveau=candidature["diplome_niveau"],
            diplome_ligne=diplome.get("ligne"),
            vecteur=semantique.depuis_octets(candidature["vecteur"]),
        )

    def noter_et_classer(self, tout: bool = False, ids: set[int] | None = None) -> int:
        postes = {p["id"]: p for p in self.postes.list()}
        actifs = [p for p in postes.values() if p["statut"] == "actif"]
        postes_actifs = [classement.PosteActif(p["id"], p["intitule"], p["reference_interne"]) for p in actifs]
        donnees_postes = {p["id"]: self._donnees_poste(p) for p in postes.values()}
        n = 0
        for candidature in self.candidatures.lues():
            if self._arret.is_set() and ids is None:
                log.info("Étape score interrompue : fin de session")
                self._tout_renoter = self._tout_renoter or tout  # à reprendre à la prochaine session
                break
            if ids is not None:
                if candidature["id"] not in ids:
                    continue
            elif not tout and candidature["statut_classement"] != "a_traiter":
                continue
            if candidature["mode_assignation"] == "manuel" and candidature["poste_id"] is None and candidature["statut_classement"] == "classe":
                candidature["mode_assignation"] = None  # le poste choisi à la main a été supprimé : on reclasse
            donnees = self.donnees_cv(candidature)
            a_noter = {p["id"] for p in actifs}
            if candidature["poste_id"] in postes:
                a_noter.add(candidature["poste_id"])  # poste choisi à la main, même s'il n'est plus actif
            pertinences = {}
            for poste_id in a_noter:
                resultat = scoring.scorer(donnees, donnees_postes[poste_id])
                pertinences[poste_id] = resultat.pertinence
                self.scores.enregistrer(
                    candidature["id"], poste_id,
                    score=resultat.score, pertinence=resultat.pertinence,
                    adequation_ignoree=resultat.adequation_ignoree, detail=resultat.detail(),
                )
            if candidature["mode_assignation"] != "manuel":
                source = classement.SourceMail(candidature["objet"] or "", candidature["corps"] or "", candidature["texte_lettre"] or "")
                decision = classement.decider(source, postes_actifs, pertinences)
                self.candidatures.maj(
                    candidature["id"],
                    poste_id=decision.poste_id,
                    statut_classement=decision.statut,
                    mode_assignation=decision.mode,
                    motif_classement=decision.motif,
                    classee_le=_maintenant(),
                )
                log.info("Étape classement candidature %d : %s → poste %s (%s)", candidature["id"], decision.statut, decision.poste_id, decision.motif)
            n += 1
        if n:
            log.info("Étape score : %d candidature(s) notée(s) sur %d poste(s) actif(s)", n, len(actifs))
        return n

    def noter_une(self, candidature_id: int) -> None:
        """Renote tout de suite une candidature (après un choix manuel), sans attendre le fil de travail."""
        with self._verrou:
            self.noter_et_classer(ids={candidature_id})

    def etat(self) -> dict[str, Any]:
        return {
            "en_cours": self.en_cours,
            "derniere_execution": self.derniere_execution.isoformat() if self.derniere_execution else None,
            "derniere_erreur": self.derniere_erreur,
            "adequation": self.modele.statut(),
        }
