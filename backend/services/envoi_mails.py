"""Mails aux candidats : préparation, aperçu, envoi un par un, historique.

Règles :
- aucun mail ne part automatiquement : le recruteur prépare l'envoi, voit l'aperçu, puis confirme ;
- invitation : candidats « retenu » du poste avec un entretien planifié et daté ; un retenu sans entretien est listé
  à part ; un entretien en ligne exige le lien de la visio (accès à distance activé), qui figure dans le mail ;
- réponse négative : candidats « écarté » du poste ; à la clôture du poste, elle part automatiquement à tous les
  non retenus (services/cloture_poste.py), après la confirmation de la clôture ;
- toujours exclus : CV illisibles, candidatures non classées, sans adresse, et ceux qui ont déjà reçu ce mail
  (sauf « renvoyer », action explicite) ;
- un mail à la fois : chaque résultat est enregistré tout de suite, un échec n'arrête pas les autres ;
- réponse dans le fil du mail de candidature quand c'est possible : l'objet devient alors « Re: <objet d'origine> »,
  sans quoi Gmail ne range pas le message dans le fil.
Les mails ne contiennent jamais de score, de classement ni d'analyse : seules les variables des modèles existent.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable

from ..database.repositories import (
    CandidatureRepository,
    EntrepriseRepository,
    EntretienRepository,
    MailCandidatRepository,
    PosteRepository,
)
from . import coffre, mail_html
from . import modeles_mail as m
from .erreurs import Conflit, ErreurValidation, Introuvable, SessionRequise
from .expediteur import EchecEnvoi, Expediteur, MailSortant
from .reglages_mails import ReglagesMailsService
from .validation import email_valide

log = logging.getLogger("injara.mails")

TYPES_LOT = (m.INVITATION, m.REFUS)
DECISION_DU_TYPE = {m.INVITATION: "retenu", m.REFUS: "ecarte"}
NOMS_TYPES = {m.INVITATION: "Invitation", m.MODIFICATION: "Modification de l'entretien", m.REFUS: "Réponse négative"}


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def destinataire_de(candidature: dict[str, Any]) -> str | None:
    """L'adresse qui a envoyé la candidature, à défaut l'email lu dans le CV."""
    for adresse in (candidature.get("expediteur_email"), candidature.get("email")):
        if adresse and email_valide(adresse.strip()):
            return adresse.strip().lower()
    return None


def resumer(historique: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """État de chaque type de mail à partir de l'historique (le plus récent d'abord).

    envoye : au moins un envoi réussi ; echec : le dernier essai a échoué ; non_envoye : rien.
    Les lignes d'un ancien mode test (adresse de redirection) sont ignorées : le candidat n'a rien reçu.
    """
    etats = {}
    for type_ in (m.INVITATION, m.MODIFICATION, m.REFUS):
        lignes = [l for l in historique if l["type"] == type_ and not l["mode_test"]]
        envoye = next((l for l in lignes if l["statut"] == "envoye"), None)
        if envoye:
            etat = {"statut": "envoye", "le": envoye["cree_le"], "destinataire": envoye["destinataire"]}
            if lignes[0]["statut"] == "echec" and lignes[0]["id"] != envoye["id"]:
                etat["dernier_echec"] = lignes[0]["erreur"]  # un renvoi explicite a échoué
        elif lignes:
            etat = {"statut": "echec", "le": lignes[0]["cree_le"], "erreur": lignes[0]["erreur"], "destinataire": lignes[0]["destinataire"]}
        else:
            etat = {"statut": "non_envoye"}
        etats[type_] = etat
    return etats


class EnvoiMailsService:
    def __init__(
        self,
        candidatures: CandidatureRepository,
        postes: PosteRepository,
        entretiens: EntretienRepository,
        mails: MailCandidatRepository,
        entreprise: EntrepriseRepository,
        reglages: ReglagesMailsService,
        expediteur: Callable[[], Expediteur],
        cle: Callable[[], bytes | None],
        maintenant: Callable[[], datetime] = _maintenant,
        lien_entretien: Callable[[dict], str | None] = lambda entretien: None,
    ) -> None:
        self.candidatures = candidatures
        self.postes = postes
        self.entretiens = entretiens
        self.mails = mails
        self.entreprise = entreprise
        self.reglages = reglages
        self.expediteur = expediteur
        self.cle = cle
        self.maintenant = maintenant
        self.lien_entretien = lien_entretien  # lien public de la visio du candidat, ou None (accès à distance coupé)
        self._verrou = threading.Lock()  # un envoi à la fois : pas de doublon sur un double clic

    # --- Préparation (aperçu) ---------------------------------------------------------------------------------

    def preparer(self, poste_id: int, type_: str) -> dict[str, Any]:
        """Destinataires avec l'aperçu de leur mail, exclus avec la raison, et ce qui bloque l'envoi."""
        poste = self._poste(poste_id)
        self._type_lot(type_)
        contexte = self._contexte()
        destinataires, exclus = [], []
        for candidature in self._candidatures_du_poste(poste_id, DECISION_DU_TYPE[type_]):
            raison, mail = self._eligibilite(candidature, poste, type_, contexte)
            if raison:
                exclus.append({**self._identite(candidature), "raison": raison})
            else:
                destinataires.append({**self._identite(candidature), **mail})
        return {
            "type": type_,
            "type_libelle": NOMS_TYPES[type_],
            "poste": {"id": poste["id"], "intitule": poste["intitule"]},
            "destinataires": destinataires,
            "exclus": exclus,
            **self._cadre(contexte),
        }

    def envoyer_lot(self, poste_id: int, type_: str, candidature_ids: list[int], echecs_seulement: bool = False) -> dict[str, Any]:
        """Envoie aux candidatures choisies parmi celles que preparer() retient (revérifiées une par une)."""
        poste = self._poste(poste_id)
        self._type_lot(type_)
        with self._verrou:
            contexte = self._contexte()
            self._verifier_cadre(contexte)
            resultats = []
            voulues = set(candidature_ids)
            for candidature in self._candidatures_du_poste(poste_id, DECISION_DU_TYPE[type_]):
                if candidature["id"] not in voulues:
                    continue
                if echecs_seulement and resumer(self.mails.pour_candidature(candidature["id"]))[type_]["statut"] != "echec":
                    continue
                raison, mail = self._eligibilite(candidature, poste, type_, contexte)
                if raison:
                    resultats.append({**self._identite(candidature), "statut": "ignore", "raison": raison})
                    continue
                resultats.append(self._envoyer_un(candidature, poste, type_, mail, contexte))
        envoyes = sum(r["statut"] == "envoye" for r in resultats)
        return {
            "type": type_,
            "resultats": resultats,
            "envoyes": envoyes,
            "echecs": sum(r["statut"] == "echec" for r in resultats),
            "ignores": sum(r["statut"] == "ignore" for r in resultats),
        }

    # --- Clôture du poste (services/cloture_poste.py) ------------------------------------------------------------

    def apercu_cloture(self, poste_id: int) -> dict[str, Any]:
        """Avant de clôturer : combien de non retenus recevront la réponse négative, qui ne la recevra pas (raison),
        et ce qui empêcherait l'envoi."""
        poste = self._poste(poste_id)
        contexte = self._contexte()
        du_poste = [c for c in self.candidatures.toutes() if c["poste_id"] == poste_id]
        a_informer, exclus = 0, []
        for candidature in du_poste:
            if candidature["decision"] == "retenu":
                continue
            raison, _ = self._eligibilite({**candidature, "decision": "ecarte"}, poste, m.REFUS, contexte)
            if raison:
                exclus.append({**self._identite(candidature), "raison": raison})
            else:
                a_informer += 1
        return {
            "retenus": sum(c["decision"] == "retenu" for c in du_poste),
            "a_informer": a_informer,
            "exclus": exclus,
            "blocages": self._blocages(contexte),
        }

    def ecarter_non_retenus(self, poste_id: int) -> int:
        """Les candidatures du poste « à examiner » ou « en attente » passent à « écarté »."""
        maintenant = datetime.now(timezone.utc)
        ecartees = 0
        for candidature in self.candidatures.toutes():
            if candidature["poste_id"] == poste_id and candidature["decision"] in ("a_examiner", "en_attente"):
                self.candidatures.maj(candidature["id"], decision="ecarte", decision_le=maintenant)
                ecartees += 1
        return ecartees

    # --- Un candidat (fiche) ------------------------------------------------------------------------------------

    def etat_candidature(self, candidature_id: int) -> dict[str, Any]:
        candidature = self._candidature(candidature_id)
        historique = self.mails.pour_candidature(candidature_id)
        poste_id = candidature["poste_id"]
        du_poste = [l for l in historique if l["poste_id"] == poste_id] if poste_id else []
        return {
            "destinataire": destinataire_de(candidature),
            "etats": resumer(du_poste),
            "modification_proposee": bool(poste_id) and self._modification_a_envoyer(candidature_id, poste_id, du_poste),
            "historique": [
                {k: l[k] for k in ("id", "type", "statut", "destinataire", "objet", "dans_le_fil", "erreur", "cree_le")}
                for l in historique
                if not l["mode_test"]
            ],
        }

    def preparer_un(self, candidature_id: int, type_: str, forcer: bool = False) -> dict[str, Any]:
        """Aperçu du mail d'un candidat (invitation, modification ou réponse négative)."""
        candidature, poste = self._candidature_et_poste(candidature_id)
        contexte = self._contexte()
        raison, mail = self._eligibilite(candidature, poste, type_, contexte, forcer=forcer)
        return {
            "type": type_,
            "type_libelle": NOMS_TYPES[type_],
            "destinataires": [] if raison else [{**self._identite(candidature), **mail}],
            "exclus": [{**self._identite(candidature), "raison": raison}] if raison else [],
            **self._cadre(contexte),
        }

    def envoyer_un(self, candidature_id: int, type_: str, forcer: bool = False) -> dict[str, Any]:
        """Envoi depuis la fiche : `forcer` renvoie un mail déjà envoyé (action explicite du recruteur)."""
        with self._verrou:
            candidature, poste = self._candidature_et_poste(candidature_id)
            contexte = self._contexte()
            self._verifier_cadre(contexte)
            raison, mail = self._eligibilite(candidature, poste, type_, contexte, forcer=forcer)
            if raison:
                raise Conflit(raison)
            return self._envoyer_un(candidature, poste, type_, mail, contexte)

    # --- Règles -------------------------------------------------------------------------------------------------

    def _eligibilite(self, candidature, poste, type_, contexte, forcer: bool = False) -> tuple[str | None, dict | None]:
        if type_ not in (m.INVITATION, m.MODIFICATION, m.REFUS):
            raise ErreurValidation({"type": "Type de mail inconnu."})
        attendue = "retenu" if type_ in (m.INVITATION, m.MODIFICATION) else "ecarte"
        if candidature["statut_lecture"] == "illisible":
            return "CV illisible : à traiter à la main.", None
        if candidature["statut_classement"] == "non_classe" or candidature["poste_id"] is None:
            return "Candidature non classée.", None
        if candidature["decision"] != attendue:
            return f"Décision « {'retenu' if attendue == 'retenu' else 'écarté'} » requise.", None
        destinataire = destinataire_de(candidature)
        if not destinataire:
            return "Aucune adresse email (ni expéditeur du mail, ni adresse dans le CV).", None

        historique = [l for l in self.mails.pour_candidature(candidature["id"]) if l["poste_id"] == poste["id"]]
        etats = resumer(historique)
        entretien = None
        if type_ in (m.INVITATION, m.MODIFICATION):
            entretien = self.entretiens.actif(candidature["id"], poste["id"])
            if entretien is None or entretien["statut"] != "planifie":
                return "Aucun entretien planifié : planifiez-le sur la fiche du candidat.", None
            if entretien["date_entretien"] is None:
                return "L'entretien n'a pas de date : fixez-la sur la fiche du candidat.", None
            if entretien["date_entretien"] <= self.maintenant():
                return "La date de l'entretien est passée : replanifiez-le.", None
            if entretien["mode"] == "en_ligne" and not self.lien_entretien(entretien):
                return "Entretien en ligne : activez l'accès à distance pour que le lien de la visio figure dans le mail.", None
        if type_ == m.MODIFICATION:
            if etats[m.INVITATION]["statut"] != "envoye":
                return "L'invitation n'a pas encore été envoyée : envoyez l'invitation.", None
            if not forcer and not self._modification_a_envoyer(candidature["id"], poste["id"], historique):
                return "La date n'a pas changé depuis le dernier mail.", None
        elif not forcer and etats[type_]["statut"] == "envoye":
            return f"{NOMS_TYPES[type_]} déjà envoyée le {etats[type_]['le']:%d/%m/%Y}.", None
        return None, self._composer(candidature, poste, type_, destinataire, entretien, contexte)

    def _modification_a_envoyer(self, candidature_id: int, poste_id: int, historique: list[dict]) -> bool:
        """Vrai si la date de l'entretien diffère de la dernière date annoncée au candidat."""
        entretien = self.entretiens.actif(candidature_id, poste_id)
        annonces = [l for l in historique if l["type"] in (m.INVITATION, m.MODIFICATION) and l["statut"] == "envoye" and not l["mode_test"]]
        if entretien is None or not annonces:
            return False
        return annonces[0]["entretien_debut"] != entretien["date_entretien"]

    def _composer(self, candidature, poste, type_, destinataire, entretien, contexte) -> dict[str, Any]:
        modele = self.reglages.modele(m.REFUS if type_ == m.REFUS else m.INVITATION)
        valeurs = {
            "civilite_nom": m.civilite_nom((candidature["extraction"] or {}).get("nom")),
            "poste": poste["intitule"],
            "entreprise": contexte["entreprise"],
            "date": "", "heure": "", "duree": "", "lieu": "", "message": "",
        }
        if entretien:
            valeurs.update(
                date=m.formater_date(entretien["date_entretien"]),
                heure=m.formater_heure(entretien["date_entretien"]),
                duree=m.formater_duree(entretien["duree_minutes"]),
                lieu=m.formater_lieu(entretien["mode"], entretien["adresse"], self.lien_entretien(entretien)),
                message=coffre.dechiffrer_texte(entretien["message"], self._cle()) or "",
            )
        objet = m.remplir(m.OBJET_MODIFICATION if type_ == m.MODIFICATION else modele["objet"], valeurs)
        corps = m.remplir(modele["corps"], valeurs)
        if type_ == m.MODIFICATION:
            corps = corps.replace("\n\n", f"\n\n{m.ANNONCE_MODIFICATION}\n\n", 1)
        html = mail_html.rendre(corps, mail_html.Signature.depuis_profil(contexte["profil"]), _encadre(type_, entretien, valeurs, self.lien_entretien), objet)

        objet_sans_fil = objet  # nouveau mail : l'objet du modèle
        dans_le_fil = bool(candidature["source"] == "email" and candidature["objet"])
        if dans_le_fil:
            origine = candidature["objet"].strip()
            objet = origine if origine.lower().startswith("re:") else f"Re: {origine}"
        return {
            "destinataire": destinataire,
            "destinataire_effectif": destinataire,
            "objet": objet,
            "objet_sans_fil": objet_sans_fil,
            "corps": corps,
            "html": html,
            "dans_le_fil": dans_le_fil,
            "entretien_debut": entretien["date_entretien"].isoformat() if entretien else None,
        }

    def _envoyer_un(self, candidature, poste, type_, mail, contexte) -> dict[str, Any]:
        expediteur = contexte["expediteur"]
        fil = None
        if mail["dans_le_fil"]:
            try:
                fil = expediteur.fil(candidature["cle"])
            except Exception as exc:  # fil introuvable : on envoie un nouveau mail
                log.warning("Fil du mail de candidature %d introuvable : %s", candidature["id"], exc)
        objet = mail["objet"] if fil is not None or not mail["dans_le_fil"] else mail["objet_sans_fil"]
        statut, erreur, gmail_id = "envoye", None, None
        try:
            gmail_id = expediteur.envoyer(MailSortant(mail["destinataire_effectif"], objet, mail["corps"], fil, mail["html"]))
        except EchecEnvoi as exc:
            statut, erreur = "echec", exc.raison
        except Exception as exc:  # panne imprévue : enregistrée comme un échec, le lot continue
            log.exception("Envoi du mail à la candidature %d en échec", candidature["id"])
            statut, erreur = "echec", f"Erreur inattendue : {exc}"
        self.mails.ajouter(
            candidature_id=candidature["id"],
            poste_id=poste["id"],
            type=type_,
            statut=statut,
            mode_test=False,
            destinataire=mail["destinataire"],
            destinataire_effectif=mail["destinataire_effectif"],
            objet=objet,
            corps=coffre.chiffrer_texte(mail["corps"], self._cle()),
            dans_le_fil=fil is not None,
            entretien_debut=datetime.fromisoformat(mail["entretien_debut"]) if mail["entretien_debut"] else None,
            erreur=erreur,
            gmail_id=gmail_id,
        )
        log.info("Mail %s à la candidature %d : %s%s", type_, candidature["id"], statut, f" ({erreur})" if erreur else "")
        return {**self._identite(candidature), "statut": statut, "erreur": erreur, "destinataire_effectif": mail["destinataire_effectif"]}

    # --- Contexte -----------------------------------------------------------------------------------------------

    def _contexte(self) -> dict[str, Any]:
        expediteur = self.expediteur()
        return {
            "expediteur": expediteur,
            "autorisation": expediteur.etat(),
            "entreprise": ((self.entreprise.get() or {}).get("nom") or "").strip(),
            "profil": self.entreprise.get() or {},
        }

    @staticmethod
    def _blocages(contexte) -> list[str]:
        blocages = []
        if not contexte["entreprise"]:
            blocages.append("Renseignez le nom de l'entreprise dans le profil entreprise : il signe les mails.")
        if not contexte["autorisation"]["autorise"]:
            blocages.append(contexte["autorisation"]["motif"] or "L'envoi de mails n'est pas autorisé.")
        return blocages

    def _cadre(self, contexte) -> dict[str, Any]:
        return {
            "autorisation": contexte["autorisation"],
            "blocages": self._blocages(contexte),
        }

    def _verifier_cadre(self, contexte) -> None:
        blocages = self._blocages(contexte)
        if blocages:
            raise Conflit(" ".join(blocages))

    def _candidatures_du_poste(self, poste_id: int, decision: str) -> list[dict[str, Any]]:
        return [c for c in self.candidatures.toutes() if c["poste_id"] == poste_id and c["decision"] == decision]

    @staticmethod
    def _identite(candidature) -> dict[str, Any]:
        return {"candidature_id": candidature["id"], "nom": candidature["nom"] or candidature["expediteur_nom"] or candidature["nom_fichier_cv"]}

    def _poste(self, poste_id: int) -> dict[str, Any]:
        poste = self.postes.get(poste_id)
        if poste is None:
            raise Introuvable("Ce poste n'existe pas ou a été supprimé.")
        return poste

    def _candidature(self, candidature_id: int) -> dict[str, Any]:
        candidature = self.candidatures.get(candidature_id)
        if candidature is None:
            raise Introuvable("Cette candidature n'existe pas.")
        return candidature

    def _candidature_et_poste(self, candidature_id: int):
        candidature = self._candidature(candidature_id)
        if candidature["poste_id"] is None:
            raise Conflit("Rattachez d'abord la candidature à un poste.")
        return candidature, self._poste(candidature["poste_id"])

    @staticmethod
    def _type_lot(type_: str) -> None:
        if type_ not in TYPES_LOT:
            raise ErreurValidation({"type": "Envoi groupé : invitation ou réponse négative."})

    def _cle(self) -> bytes:
        cle = self.cle()
        if cle is None:
            raise SessionRequise("Session expirée. Veuillez vous reconnecter.")
        return cle


def _encadre(type_: str, entretien: dict | None, valeurs: dict[str, str], lien: Callable[[dict], str | None]) -> mail_html.Entretien | None:
    """Encadré « Votre entretien » du mail mis en forme (invitation et modification)."""
    if entretien is None or type_ == m.REFUS:
        return None
    en_ligne = entretien["mode"] == "en_ligne"
    return mail_html.Entretien(
        date=valeurs["date"],
        heure=valeurs["heure"],
        duree=valeurs["duree"],
        lieu="En ligne (visioconférence)" if en_ligne else (entretien["adresse"] or "").strip() or "Dans nos locaux",
        lien=lien(entretien) if en_ligne else None,
        titre="Nouvelle date de votre entretien" if type_ == m.MODIFICATION else "Votre entretien",
    )
