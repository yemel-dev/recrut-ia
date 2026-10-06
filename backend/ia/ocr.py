"""Reconnaissance de caractères (OCR) pour les CV scannés, hors ligne.

- RapidOCR (modèles PP-OCRv6 multilingues, fournis avec le paquet : aucun téléchargement) sur onnxruntime.
- Les pages du PDF sont rendues en images par pypdfium2, puis lues dans l'ordre (haut en bas).
- Moteur absent ou en panne : `disponible` vaut False avec un motif, et le scan reste « illisible » comme avant.
- Le moteur est chargé une seule fois, à la première utilisation (quelques secondes).
"""
from __future__ import annotations

import logging
import threading
from typing import Any

log = logging.getLogger("injara.ia.ocr")

PAGES_MAX = 4  # un CV dépasse rarement 4 pages ; au-delà, le temps de lecture n'en vaut pas la peine
RESOLUTION_DPI = 200
SCORE_MIN = 0.5  # lignes reconnues avec une confiance plus faible : ignorées


class MoteurOCR:
    def __init__(self) -> None:
        self._moteur = None
        self._essaye = False
        self.motif_indisponible: str | None = None
        self._lock = threading.Lock()

    @property
    def disponible(self) -> bool:
        self._charger()
        return self._moteur is not None

    def statut(self) -> dict[str, Any]:
        """État pour l'interface, sans déclencher le chargement."""
        return {"disponible": self._moteur is not None, "essaye": self._essaye, "motif": self.motif_indisponible}

    def _charger(self) -> None:
        with self._lock:
            if self._essaye:
                return
            self._essaye = True
            try:
                import pypdfium2  # noqa: F401
                from rapidocr import RapidOCR
            except ImportError:
                self.motif_indisponible = "bibliothèques rapidocr, onnxruntime ou pypdfium2 absentes (voir requirements.txt)"
                log.warning("OCR désactivé : %s", self.motif_indisponible)
                return
            except Exception as exc:  # DLL native manquante, version incompatible…
                self.motif_indisponible = f"moteur impossible à charger : {exc}"
                log.exception("Import de RapidOCR impossible")
                return
            try:
                self._moteur = RapidOCR(params={"Global.log_level": "error"})
                log.info("OCR chargé")
            except Exception as exc:
                self.motif_indisponible = f"moteur impossible à démarrer : {exc}"
                log.exception("Démarrage de RapidOCR impossible")

    def lire_pdf(self, contenu: bytes, nom: str = "") -> str:
        """Texte reconnu dans les premières pages du PDF ; chaîne vide si rien n'a pu être lu."""
        if not self.disponible:
            return ""
        import pypdfium2

        lignes: list[str] = []
        try:
            document = pypdfium2.PdfDocument(contenu)
        except Exception as exc:  # PDF endommagé ou protégé
            log.warning("OCR : PDF illisible %s : %s", nom, exc)
            return ""
        try:
            for numero in range(min(len(document), PAGES_MAX)):
                page = document[numero]
                image = page.render(scale=RESOLUTION_DPI / 72).to_pil()
                page.close()
                with self._lock:  # le moteur n'est pas prévu pour plusieurs fils à la fois
                    resultat = self._moteur(image)
                lignes += [t for t, s in zip(resultat.txts or (), resultat.scores or ()) if s >= SCORE_MIN]
        except Exception as exc:
            log.warning("OCR interrompu sur %s : %s", nom, exc)
        finally:
            document.close()
        log.info("OCR : %d ligne(s) reconnue(s) dans %s", len(lignes), nom)
        return "\n".join(lignes)
