"""Réseau de la visio : quels serveurs STUN/TURN les deux navigateurs utilisent pour se joindre.

La vidéo passe directement d'un navigateur à l'autre. Quand l'un des deux est derrière un réseau strict (pare-feu
d'entreprise, partage de connexion mobile, NAT symétrique), la connexion directe échoue et seule la relève par un serveur
TURN fonctionne : sans lui, le candidat reste devant « connexion en cours ». Le STUN public de Google est toujours
présent ; le recruteur y ajoute son TURN (n'importe quel fournisseur, ou coturn) dans l'application.

Les identifiants du TURN sont chiffrés avec la clé de données de la session. Ils sont donnés au navigateur du candidat
(il en a besoin pour se connecter) : préférez des identifiants à durée limitée ou un compte dédié, révocable.
INJARA_ICE_SERVERS (JSON) reste prioritaire : voir `signalisation.serveurs_ice`.

Cloudflare Realtime TURN : si CLOUDFLARE_TURN_TOKEN_ID et CLOUDFLARE_API_TOKEN sont définis (fichier .env, jamais dans
le code), INJARA demande à Cloudflare des identifiants temporaires (valables 24 h) et les garde en mémoire jusqu'à
une heure avant leur expiration. Ordre de priorité : INJARA_ICE_SERVERS, puis le TURN saisi dans l'application, puis Cloudflare.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Callable

from ..database.repositories import ParametreRepository
from . import coffre
from .erreurs import ErreurValidation, Indisponible, Introuvable, SessionRequise
from .signalisation import SERVEURS_ICE_PAR_DEFAUT, serveurs_ice as serveurs_ice_env

log = logging.getLogger("injara.reseau")
_PORT_53 = re.compile(r":53(?:\?|$)")

CLE = "reseau_turn"
URL_CLOUDFLARE = "https://rtc.live.cloudflare.com/v1/turn/keys/{cle}/credentials/generate"
DUREE_IDENTIFIANTS = 24 * 3600  # secondes : durée de vie demandée à Cloudflare
MARGE_RENOUVELLEMENT = 3600  # on en redemande une heure avant l'expiration
PAUSE_APRES_ECHEC = 60  # secondes sans réessayer après un échec, pour ne pas ralentir chaque chargement de page
DELAI_CLOUDFLARE = 5  # secondes
SCHEMAS = ("turn:", "turns:")
MAX_URLS = 5
LONGUEUR_MAX = 300


class ReseauService:
    def __init__(self, parametres: ParametreRepository, cle: Callable[[], bytes | None], ouvrir=urllib.request.urlopen) -> None:
        self.parametres = parametres
        self._cle = cle
        self._ouvrir = ouvrir  # remplaçable dans les tests : aucun appel réseau réel
        self._cloudflare: tuple[list[dict[str, Any]], float] | None = None  # (serveurs, expiration)
        self._cloudflare_essai = 0.0  # dernière tentative ratée
        self._cloudflare_erreur: str | None = None
        self._verrou = threading.Lock()

    def _turn(self) -> dict[str, Any] | None:
        valeur, cle = self.parametres.get(CLE), self._cle()
        if not valeur or cle is None:
            return None
        try:
            return json.loads(coffre.dechiffrer_texte(valeur, cle) or "")
        except (ValueError, coffre.Indechiffrable):
            return None

    def serveurs_ice(self) -> list[dict[str, Any]]:
        """Serveurs donnés aux navigateurs : INJARA_ICE_SERVERS s'il est défini, sinon STUN + le TURN du recruteur."""
        if os.getenv("INJARA_ICE_SERVERS"):
            return serveurs_ice_env()
        turn = self._turn()
        serveurs = list(SERVEURS_ICE_PAR_DEFAUT)
        if turn:
            serveurs.append({"urls": turn["urls"], "username": turn["username"], "credential": turn["credential"]})
        elif self.cloudflare_configure():
            serveurs += self._serveurs_cloudflare()
        return serveurs

    # --- Cloudflare Realtime TURN : identifiants temporaires -------------------------------------------------

    @staticmethod
    def cloudflare_configure() -> bool:
        return bool(os.getenv("CLOUDFLARE_TURN_TOKEN_ID") and os.getenv("CLOUDFLARE_API_TOKEN"))

    def _serveurs_cloudflare(self) -> list[dict[str, Any]]:
        """Les serveurs TURN de Cloudflare avec des identifiants temporaires ; liste vide si Cloudflare ne répond pas."""
        with self._verrou:
            maintenant = time.monotonic()
            if self._cloudflare and maintenant < self._cloudflare[1]:
                return self._cloudflare[0]
            if maintenant - self._cloudflare_essai < PAUSE_APRES_ECHEC and self._cloudflare_erreur:
                return []
            try:
                serveurs = self._demander_a_cloudflare()
            except Exception as err:  # noqa: BLE001  (réseau, clé refusée, réponse inattendue : on retombe sur le STUN)
                self._cloudflare, self._cloudflare_essai, self._cloudflare_erreur = None, maintenant, str(err)
                log.warning("Identifiants TURN Cloudflare indisponibles : %s", err)
                return []
            self._cloudflare = (serveurs, maintenant + DUREE_IDENTIFIANTS - MARGE_RENOUVELLEMENT)
            self._cloudflare_erreur = None
            return serveurs

    def _demander_a_cloudflare(self) -> list[dict[str, Any]]:
        requete = urllib.request.Request(
            URL_CLOUDFLARE.format(cle=os.environ["CLOUDFLARE_TURN_TOKEN_ID"].strip()),
            data=json.dumps({"ttl": DUREE_IDENTIFIANTS}).encode(),
            headers={
                "Authorization": f"Bearer {os.environ['CLOUDFLARE_API_TOKEN'].strip()}", "Content-Type": "application/json",
                "User-Agent": "INJARA/1.0",  # le « Python-urllib » par défaut est parfois refusé (403) par le pare-feu de Cloudflare
            },
            method="POST",
        )
        try:
            with self._ouvrir(requete, timeout=DELAI_CLOUDFLARE) as reponse:
                corps = json.loads(reponse.read().decode())
        except urllib.error.HTTPError as err:
            motif = err.read(300).decode("utf-8", "replace").strip() if hasattr(err, "read") and err.fp else ""  # le motif donné par Cloudflare, sans secret
            raise RuntimeError(f"Cloudflare a répondu {err.code}{f' : {motif}' if motif else ''} (vérifiez l'identifiant et le jeton)") from None
        serveurs = corps.get("iceServers")
        if isinstance(serveurs, dict):  # Cloudflare renvoie un seul objet ; le navigateur attend une liste
            serveurs = [serveurs]
        if not isinstance(serveurs, list) or not serveurs:
            raise RuntimeError("réponse de Cloudflare inattendue")
        propres = []
        for serveur in serveurs:
            urls = [u for u in ([serveur["urls"]] if isinstance(serveur.get("urls"), str) else serveur.get("urls", [])) if not _PORT_53.search(u)]  # Firefox bloque le port 53 (exactement : 5349 reste valable)
            if urls:
                propres.append({**serveur, "urls": urls})
        return propres

    def etat(self) -> dict[str, Any]:
        """La configuration, sans le mot de passe du TURN."""
        turn = self._turn()
        return {
            "turn": {"configure": True, "urls": turn["urls"], "username": turn["username"]} if turn else {"configure": False},
            "cloudflare": {"configure": self.cloudflare_configure(), "erreur": self._cloudflare_erreur},
            "source_forcee": bool(os.getenv("INJARA_ICE_SERVERS")),  # la variable d'environnement l'emporte sur la configuration
        }

    def configurer(self, urls: list[str], username: str, credential: str) -> dict[str, Any]:
        cle = self._cle()
        if cle is None:
            raise SessionRequise("Vous devez être connecté.")
        urls = [u.strip() for u in urls if u and u.strip()]
        erreurs = {}
        if not urls or len(urls) > MAX_URLS:
            erreurs["urls"] = f"Indiquez de 1 à {MAX_URLS} adresses."
        elif any(not u.startswith(SCHEMAS) or len(u) > LONGUEUR_MAX or " " in u for u in urls):
            erreurs["urls"] = "Chaque adresse doit commencer par turn: ou turns: (par exemple turn:serveur.exemple.com:3478)."
        if not username.strip() or len(username) > LONGUEUR_MAX:
            erreurs["username"] = "Nom d'utilisateur requis."
        if not credential or len(credential) > LONGUEUR_MAX:
            erreurs["credential"] = "Mot de passe requis."
        if erreurs:
            raise ErreurValidation(erreurs)
        charge = json.dumps({"urls": urls, "username": username.strip(), "credential": credential})
        self.parametres.set(CLE, coffre.chiffrer_texte(charge, cle))
        return self.etat()

    def supprimer(self) -> dict[str, Any]:
        self.parametres.set(CLE, "")
        return self.etat()

    def pour_test(self) -> list[dict[str, Any]]:
        """Les serveurs à essayer depuis l'interface du recruteur (avec identifiants) ; erreur si aucun TURN n'est configuré."""
        self._cloudflare_essai = 0.0  # un test volontaire réessaie tout de suite, sans attendre la pause
        serveurs = self.serveurs_ice()
        if not any(_est_turn(s) for s in serveurs):
            if self.cloudflare_configure() and not self._turn() and self._cloudflare_erreur:
                raise Indisponible(f"Cloudflare n'a pas fourni d'identifiants TURN : {self._cloudflare_erreur}.")
            raise Introuvable("Aucun serveur TURN n'est configuré.")
        return serveurs


def _est_turn(serveur: dict[str, Any]) -> bool:
    urls = serveur.get("urls", [])
    return any(str(u).startswith(SCHEMAS) for u in ([urls] if isinstance(urls, str) else urls))
