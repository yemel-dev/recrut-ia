"""Clôture d'un poste : la réponse négative part automatiquement à tous les candidats non retenus.

Quand le recruteur passe un poste à « clôturé » (après avoir confirmé, en voyant combien de candidats seront
prévenus) :
- toutes les candidatures du poste qui ne sont pas « retenu » (à examiner, en attente) passent à « écarté » ;
- la réponse négative part à chacune d'elles, en arrière-plan, avec les règles habituelles (EnvoiMailsService) :
  jamais deux fois au même candidat, ni à un CV illisible ou sans adresse ; un échec n'arrête pas les autres et
  reste visible sur le poste (« Envoyer les réponses négatives » permet de relancer) ;
- les retenus ne reçoivent rien : le recruteur leur écrit lui-même (invitation).
Si l'envoi est impossible (nom de l'entreprise manquant, boîte non autorisée), le poste est clôturé quand même et
la raison est rendue : les réponses pourront partir plus tard depuis le poste.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable

from . import modeles_mail as m
from .envoi_mails import EnvoiMailsService
from .postes import PostesService

log = logging.getLogger("injara.mails.cloture")


def _en_arriere_plan(tache: Callable[[], None]) -> None:
    threading.Thread(target=tache, name="reponses-negatives", daemon=True).start()


class CloturePosteService:
    def __init__(
        self,
        postes: PostesService,
        envoi: EnvoiMailsService,
        lancer: Callable[[Callable[[], None]], None] = _en_arriere_plan,
    ) -> None:
        self.postes = postes
        self.envoi = envoi
        self.lancer = lancer  # les tests l'exécutent tout de suite

    def apercu(self, poste_id: int) -> dict[str, Any]:
        """Ce que la clôture fera : candidats prévenus, ceux qui ne peuvent pas l'être (raison), ce qui bloque."""
        return self.envoi.apercu_cloture(poste_id)

    def cloturer(self, poste_id: int) -> dict[str, Any]:
        poste = self.postes.consulter(poste_id)
        if poste["statut"] == "cloture":
            return {**poste, "cloture": None}
        apercu = self.envoi.apercu_cloture(poste_id)
        poste = self.postes.changer_statut(poste_id, "cloture")
        ecartes = self.envoi.ecarter_non_retenus(poste_id)
        en_cours = not apercu["blocages"] and apercu["a_informer"] > 0
        if en_cours:
            self.lancer(lambda: self._envoyer(poste_id))
        return {
            **poste,
            "cloture": {
                "ecartes": ecartes,
                "a_informer": apercu["a_informer"] if en_cours else 0,
                "envoi_impossible": " ".join(apercu["blocages"]) or None,
            },
        }

    def _envoyer(self, poste_id: int) -> None:
        try:
            preparation = self.envoi.preparer(poste_id, m.REFUS)
            ids = [d["candidature_id"] for d in preparation["destinataires"]]
            if ids:
                bilan = self.envoi.envoyer_lot(poste_id, m.REFUS, ids)
                log.info("Clôture du poste %d : %d réponse(s) négative(s) envoyée(s), %d échec(s)", poste_id, bilan["envoyes"], bilan["echecs"])
        except Exception:
            log.exception("Réponses négatives de la clôture du poste %d impossibles", poste_id)
