"""Analyse du regard et des mouvements de tête du candidat (module 4 de l'entretien vidéo).

Deux parties :
- `AnalyseurVisage` : lit une image (JPEG) avec MediaPipe Face Landmarker et en tire une `Mesure` (nombre de visages,
  rotation de la tête, direction du regard). Le modèle est chargé à la demande, hors ligne, depuis le dossier des modèles.
- `SuiviRegard` : accumule les mesures d'un entretien, relève les événements (regard détourné, visage absent, plusieurs
  visages) et calcule le bilan et le score. Il ne dépend ni de MediaPipe ni de l'horloge : il se teste sans caméra.

Ce n'est qu'un indicateur : regarder ailleurs un instant n'a rien d'anormal (réfléchir, lire ses notes de l'entretien).
Les seuils sont des valeurs de départ, à ajuster avec des entretiens réels.
"""
from __future__ import annotations

import math
import statistics
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..services.erreurs import Indisponible

NOM_MODELE_VISAGE = "face_landmarker.task"
URL_MODELE_VISAGE = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"

# --- Seuils (écart par rapport à la posture habituelle du candidat, mesurée au début) ---
ECART_LACET_MAX = 25.0  # degrés : tête tournée à gauche ou à droite
ECART_TANGAGE_MAX = 20.0  # degrés : tête levée ou baissée
ECART_REGARD_X_MAX = 0.35  # 0 à 1 : yeux tournés sur le côté
ECART_REGARD_Y_MAX = 0.40  # 0 à 1 : yeux levés ou baissés
ECHANTILLONS_CALIBRAGE = 12  # mesures valides pour fixer la posture habituelle
DUREE_DETOURNE = 3.0  # secondes de regard détourné avant de relever un événement
DUREE_ABSENT = 3.0
DUREE_PLUSIEURS = 2.0
PAUSE_MAX = 1.0  # un trou plus long entre deux images (connexion coupée) n'est pas compté comme du temps observé

ETATS = ("attentif", "regard_detourne", "visage_absent", "plusieurs_visages")


@dataclass(frozen=True)
class Mesure:
    visages: int
    lacet: float | None = None  # degrés ; positif = tête tournée vers sa droite
    tangage: float | None = None  # degrés ; positif = tête baissée
    regard_x: float | None = None  # -1 à 1 ; positif = yeux vers sa droite
    regard_y: float | None = None  # -1 à 1 ; positif = yeux vers le haut

    def en_dict(self) -> dict[str, Any]:
        return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in self.__dict__.items()}


# --- Analyse d'une image ---------------------------------------------------------------------------------


class AnalyseurVisage:
    def __init__(self, chemin: Path) -> None:
        self.chemin = chemin
        self._detecteur = None
        self._lock = threading.Lock()

    def disponible(self) -> bool:
        return self.chemin.is_file()

    def _charger(self):
        if self._detecteur is not None:
            return self._detecteur
        if not self.chemin.is_file():
            raise Indisponible("Le modèle d'analyse du regard est absent. Lancez : python -m backend.ia.telecharger_modele")
        try:
            from mediapipe.tasks.python import BaseOptions, vision
        except ImportError:
            raise Indisponible("MediaPipe n'est pas installé : pip install -r requirements-ia.txt") from None
        options = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(self.chemin)),
            running_mode=vision.RunningMode.IMAGE,
            num_faces=2,  # deux suffisent pour savoir s'il y en a plusieurs
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
        )
        self._detecteur = vision.FaceLandmarker.create_from_options(options)
        return self._detecteur

    def analyser(self, jpeg: bytes) -> Mesure:
        try:
            import cv2
            import mediapipe as mp
            import numpy as np
        except ImportError:
            raise Indisponible("OpenCV et MediaPipe ne sont pas installés : pip install -r requirements-ia.txt") from None
        with self._lock:  # le détecteur n'est pas conçu pour des appels simultanés
            detecteur = self._charger()  # d'abord : un modèle absent se dit avant une image illisible
            image = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError("Image illisible.")
            rgb = np.ascontiguousarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            resultat = detecteur.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
        visages = len(resultat.face_landmarks)
        if visages == 0:
            return Mesure(0)
        lacet = tangage = None
        if resultat.facial_transformation_matrixes:
            lacet, tangage = angles_tete(np.asarray(resultat.facial_transformation_matrixes[0]))
        regard_x = regard_y = None
        if resultat.face_blendshapes:
            regard_x, regard_y = direction_regard({c.category_name: c.score for c in resultat.face_blendshapes[0]})
        return Mesure(visages, lacet, tangage, regard_x, regard_y)

    def fermer(self) -> None:
        with self._lock:
            if self._detecteur is not None:
                self._detecteur.close()
                self._detecteur = None


def angles_tete(matrice) -> tuple[float, float]:
    """Lacet et tangage (degrés) depuis la matrice de pose 4x4 de MediaPipe. R = Ry(lacet) · Rx(tangage)."""
    r = matrice[:3, :3]
    lacet = math.degrees(math.atan2(r[0][2], r[2][2]))
    tangage = math.degrees(math.asin(max(-1.0, min(1.0, -r[1][2]))))
    return lacet, tangage


def direction_regard(b: dict[str, float]) -> tuple[float, float]:
    """Direction des yeux (-1 à 1) depuis les blendshapes : vers sa droite / vers le haut sont positifs.

    Pour regarder à sa droite, l'œil droit va vers l'extérieur et l'œil gauche vers le nez, et inversement.
    """
    g = b.get
    x = (g("eyeLookOutRight", 0) + g("eyeLookInLeft", 0) - g("eyeLookInRight", 0) - g("eyeLookOutLeft", 0)) / 2
    y = (g("eyeLookUpLeft", 0) + g("eyeLookUpRight", 0) - g("eyeLookDownLeft", 0) - g("eyeLookDownRight", 0)) / 2
    return x, y


# --- Suivi d'un entretien ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Evenement:
    type: str  # regard_detourne | visage_absent | plusieurs_visages
    debut: float  # secondes depuis le début du suivi
    details: dict[str, Any]


class SuiviRegard:
    """Accumule les mesures d'un entretien. Le temps est fourni à chaque mesure (secondes, croissant)."""

    def __init__(self) -> None:
        self._origine: float | None = None
        self._precedent: float | None = None
        self._calibrage: list[Mesure] = []
        self._posture: dict[str, float] | None = None
        self._temps = {etat: 0.0 for etat in ETATS}
        self._depuis: dict[str, float | None] = {"regard_detourne": None, "visage_absent": None, "plusieurs_visages": None}
        self._signale: set[str] = set()
        self._mouvement = 0.0  # cumul des rotations de la tête (degrés)
        self._derniere_pose: tuple[float, float] | None = None
        self._evenements = 0
        self.etat = "attentif"

    def ajouter(self, mesure: Mesure, t: float) -> list[Evenement]:
        if self._origine is None:
            self._origine = t
        dt = 0.0 if self._precedent is None else min(max(t - self._precedent, 0.0), PAUSE_MAX)
        self._precedent = t
        self._etalonner(mesure)
        etat = self._classer(mesure)
        self.etat = etat
        self._temps[etat] += dt
        self._mesurer_mouvement(mesure)
        return self._relever(etat, mesure, t)

    def _etalonner(self, mesure: Mesure) -> None:
        """La posture habituelle (tête et yeux) vient des premières mesures : chacun regarde son écran un peu différemment."""
        if self._posture is not None or mesure.visages != 1 or mesure.lacet is None or mesure.regard_x is None:
            return
        self._calibrage.append(mesure)
        if len(self._calibrage) >= ECHANTILLONS_CALIBRAGE:
            def mediane(attribut: str) -> float:
                return statistics.median(getattr(m, attribut) for m in self._calibrage)

            self._posture = {a: mediane(a) for a in ("lacet", "tangage", "regard_x", "regard_y")}

    def _classer(self, mesure: Mesure) -> str:
        if mesure.visages == 0:
            return "visage_absent"
        if mesure.visages > 1:
            return "plusieurs_visages"
        if self._posture is None:
            return "attentif"  # pas encore de référence : on n'accuse pas
        return "regard_detourne" if self._ecarts(mesure) else "attentif"

    def _ecarts(self, m: Mesure) -> dict[str, float]:
        """Les écarts qui dépassent leur seuil (vide si le candidat est dans sa posture habituelle)."""
        p = self._posture or {}
        limites = (("lacet", ECART_LACET_MAX), ("tangage", ECART_TANGAGE_MAX), ("regard_x", ECART_REGARD_X_MAX), ("regard_y", ECART_REGARD_Y_MAX))
        depassements = {}
        for nom, limite in limites:
            valeur = getattr(m, nom)
            if valeur is not None and abs(valeur - p[nom]) > limite:
                depassements[nom] = round(valeur - p[nom], 2)
        return depassements

    def _mesurer_mouvement(self, mesure: Mesure) -> None:
        if mesure.visages != 1 or mesure.lacet is None or mesure.tangage is None:
            self._derniere_pose = None
            return
        if self._derniere_pose is not None:
            self._mouvement += math.hypot(mesure.lacet - self._derniere_pose[0], mesure.tangage - self._derniere_pose[1])
        self._derniere_pose = (mesure.lacet, mesure.tangage)

    def _relever(self, etat: str, mesure: Mesure, t: float) -> list[Evenement]:
        durees = {"regard_detourne": DUREE_DETOURNE, "visage_absent": DUREE_ABSENT, "plusieurs_visages": DUREE_PLUSIEURS}
        evenements = []
        for type_, duree in durees.items():
            if etat != type_:
                self._depuis[type_] = None
                self._signale.discard(type_)
                continue
            debut = self._depuis[type_] = self._depuis[type_] if self._depuis[type_] is not None else t
            if t - debut >= duree and type_ not in self._signale:
                self._signale.add(type_)  # un seul événement par épisode
                self._evenements += 1
                details = {"depuis_s": round(debut - (self._origine or 0), 1), "duree_minimale_s": duree}
                if type_ == "regard_detourne":
                    details["ecarts"] = self._ecarts(mesure)
                elif type_ == "plusieurs_visages":
                    details["visages"] = mesure.visages
                evenements.append(Evenement(type_, debut - (self._origine or 0), details))
        return evenements

    # --- Résultats ---

    @property
    def duree(self) -> float:
        return sum(self._temps.values())

    def score(self) -> float | None:
        """Part du temps observé où le candidat est face à l'écran (0 à 100). None tant qu'il n'y a rien d'observé."""
        return round(100 * self._temps["attentif"] / self.duree, 1) if self.duree > 0 else None

    def bilan(self) -> dict[str, Any]:
        duree = self.duree
        part = lambda etat: round(100 * self._temps[etat] / duree, 1) if duree > 0 else 0.0  # noqa: E731
        return {
            "duree_observee_s": round(duree, 1),
            "part_attentif": part("attentif"),
            "part_regard_detourne": part("regard_detourne"),
            "part_visage_absent": part("visage_absent"),
            "part_plusieurs_visages": part("plusieurs_visages"),
            "agitation_tete_deg_par_min": round(60 * self._mouvement / duree, 1) if duree > 0 else 0.0,
            "evenements": self._evenements,
            "calibre": self._posture is not None,
        }


def telecharger_modele_visage(dossier: Path) -> Path:
    """Télécharge le modèle Face Landmarker (environ 4 Mo) dans le dossier des modèles."""
    from urllib.request import urlretrieve

    dossier.mkdir(parents=True, exist_ok=True)
    cible = dossier / NOM_MODELE_VISAGE
    partiel = cible.with_suffix(".part")
    urlretrieve(URL_MODELE_VISAGE, partiel)
    partiel.replace(cible)
    return cible
