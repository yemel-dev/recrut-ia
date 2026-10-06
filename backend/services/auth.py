"""Compte unique, connexion, session en mémoire et récupération par clé de secours."""
from __future__ import annotations

import hmac
import secrets
import threading
from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from ..config import KdfParams
from ..database.repositories import CompteRepository
from . import cles
from .erreurs import Conflit, ErreurValidation, NonAutorise
from .validation import email_valide

LONGUEUR_MIN_MOT_DE_PASSE = 12
LONGUEUR_MAX_MOT_DE_PASSE = 256
_IDENTIFIANTS_INCORRECTS = "Email ou mot de passe incorrect."


@dataclass
class Session:
    jeton: str
    email: str
    cle_de_donnees: bytes


@dataclass(frozen=True)
class ResultatConnexion:
    jeton_session: str
    email: str


@dataclass(frozen=True)
class ResultatRecuperation:
    nouvelle_cle_de_recuperation: str


def valider_mot_de_passe(mot_de_passe: str, champ: str = "mot_de_passe") -> None:
    if len(mot_de_passe) < LONGUEUR_MIN_MOT_DE_PASSE:
        raise ErreurValidation({champ: f"Le mot de passe doit contenir au moins {LONGUEUR_MIN_MOT_DE_PASSE} caractères."})
    if len(mot_de_passe) > LONGUEUR_MAX_MOT_DE_PASSE:
        raise ErreurValidation({champ: f"Le mot de passe ne doit pas dépasser {LONGUEUR_MAX_MOT_DE_PASSE} caractères."})
    if not mot_de_passe.strip():
        raise ErreurValidation({champ: "Le mot de passe ne peut pas être composé uniquement d'espaces."})


class AuthService:
    """Une seule session à la fois. Elle vit en mémoire : arrêter le backend déconnecte."""

    def __init__(self, comptes: CompteRepository, kdf: KdfParams) -> None:
        self.comptes = comptes
        self.kdf = kdf
        self._hasher = PasswordHasher(
            time_cost=kdf.time_cost, memory_cost=kdf.memory_cost_kib, parallelism=kdf.parallelism
        )
        self._session: Session | None = None
        self._lock = threading.Lock()

    # --- État -----------------------------------------------------------------

    def compte_existe(self) -> bool:
        return self.comptes.exists()

    def session_valide(self, jeton: str | None) -> Session | None:
        session = self._session
        if session is None or not jeton or not hmac.compare_digest(session.jeton, jeton):
            return None
        return session

    def cle_de_donnees(self, jeton: str | None) -> bytes:
        """Clé de données de la session en cours (pour le futur chiffrement des CV)."""
        session = self.session_valide(jeton)
        if session is None:
            raise NonAutorise("Session expirée. Veuillez vous reconnecter.")
        return session.cle_de_donnees

    # --- Création du compte ---------------------------------------------------

    def creer_compte(self, email: str, mot_de_passe: str) -> str:
        """Crée le compte unique et renvoie la clé de récupération, à montrer une seule fois."""
        email = email.strip().lower()
        erreurs: dict[str, str] = {}
        if not email_valide(email):
            erreurs["email"] = "Adresse email invalide."
        try:
            valider_mot_de_passe(mot_de_passe)
        except ErreurValidation as exc:
            erreurs.update(exc.champs)
        if erreurs:
            raise ErreurValidation(erreurs)

        with self._lock:
            if self.comptes.exists():
                raise Conflit("Un compte existe déjà sur cet ordinateur.")
            cle_de_donnees = cles.nouvelle_cle_de_donnees()
            cle_de_recuperation = cles.nouvelle_cle_de_recuperation()
            self.comptes.create(
                email=email,
                mot_de_passe_hash=self._hasher.hash(mot_de_passe),
                **self._protections(cle_de_donnees, mot_de_passe, cle_de_recuperation),
            )
        return cle_de_recuperation

    # --- Connexion --------------------------------------------------------------

    def connecter(self, email: str, mot_de_passe: str) -> ResultatConnexion:
        compte = self.comptes.get()
        if compte is None:
            raise NonAutorise("Aucun compte n'existe encore sur cet ordinateur.")
        # Le hash est toujours vérifié, même si l'email est faux, pour ne pas révéler lequel des deux est erroné.
        mot_de_passe_ok = self._verifier(compte["mot_de_passe_hash"], mot_de_passe)
        if not mot_de_passe_ok or email.strip().lower() != compte["email"]:
            raise NonAutorise(_IDENTIFIANTS_INCORRECTS)

        cle_de_protection = cles.cle_depuis_mot_de_passe(mot_de_passe, compte["sel_mot_de_passe"], self.kdf)
        try:
            cle_de_donnees = cles.desenvelopper(compte["cle_par_mot_de_passe"], cle_de_protection)
        except cles.CleInvalide as exc:
            raise NonAutorise("Les données du compte sont illisibles.") from exc

        if self._hasher.check_needs_rehash(compte["mot_de_passe_hash"]):
            self.comptes.update(mot_de_passe_hash=self._hasher.hash(mot_de_passe))
        return self._ouvrir_session(compte["email"], cle_de_donnees)

    def deconnecter(self) -> None:
        with self._lock:
            self._session = None

    # --- Mot de passe oublié ------------------------------------------------------

    def reinitialiser(self, cle_de_recuperation: str, nouveau_mot_de_passe: str) -> ResultatRecuperation:
        """Déchiffre la clé de données avec la clé de récupération, puis la protège par le nouveau mot de passe.

        Une nouvelle clé de récupération est générée : l'ancienne a pu être exposée en étant saisie.
        """
        valider_mot_de_passe(nouveau_mot_de_passe, champ="nouveau_mot_de_passe")
        compte = self.comptes.get()
        if compte is None:
            raise NonAutorise("Aucun compte n'existe encore sur cet ordinateur.")
        cle_de_protection = cles.cle_depuis_recuperation(cle_de_recuperation, compte["sel_recuperation"])
        try:
            cle_de_donnees = cles.desenvelopper(compte["cle_par_recuperation"], cle_de_protection)
        except cles.CleInvalide as exc:
            raise ErreurValidation({"cle_de_recuperation": "Clé de récupération incorrecte."}) from exc

        nouvelle_cle = cles.nouvelle_cle_de_recuperation()
        with self._lock:
            self.comptes.update(
                mot_de_passe_hash=self._hasher.hash(nouveau_mot_de_passe),
                **self._protections(cle_de_donnees, nouveau_mot_de_passe, nouvelle_cle),
            )
            self._session = None
        return ResultatRecuperation(nouvelle_cle_de_recuperation=nouvelle_cle)

    # --- Interne ------------------------------------------------------------------

    def _protections(self, cle_de_donnees: bytes, mot_de_passe: str, cle_de_recuperation: str) -> dict[str, bytes]:
        sel_mdp, sel_recup = cles.nouveau_sel(), cles.nouveau_sel()
        return {
            "sel_mot_de_passe": sel_mdp,
            "cle_par_mot_de_passe": cles.envelopper(
                cle_de_donnees, cles.cle_depuis_mot_de_passe(mot_de_passe, sel_mdp, self.kdf)
            ),
            "sel_recuperation": sel_recup,
            "cle_par_recuperation": cles.envelopper(
                cle_de_donnees, cles.cle_depuis_recuperation(cle_de_recuperation, sel_recup)
            ),
        }

    def _verifier(self, hash_: str, mot_de_passe: str) -> bool:
        try:
            return self._hasher.verify(hash_, mot_de_passe)
        except (VerificationError, InvalidHashError):
            return False

    def _ouvrir_session(self, email: str, cle_de_donnees: bytes) -> ResultatConnexion:
        with self._lock:
            self._session = Session(jeton=secrets.token_urlsafe(32), email=email, cle_de_donnees=cle_de_donnees)
            return ResultatConnexion(jeton_session=self._session.jeton, email=email)
