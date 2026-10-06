# Documentation INJARA

`sources/` contient les documents de cadrage d'origine, copiés sans modification.
Ils portent encore l'ancien nom du produit, **RecrutIA** : le produit s'appelle désormais **INJARA**.

| Document | Contenu |
|---|---|
| `sources/RecrutIA_Cahier_Charges_Technique.docx` | Vision, six modules fonctionnels, schéma de base, dépendances, feuille de route |
| `sources/RecrutIA_Rapport_Reunion_19092026.docx` | Réunion de cadrage : agent mail, scénario profil de poste → tri, choix Python + Electron |
| `sources/RecrutIA_Repartition_Taches.docx` | Rôles de l'équipe et planning |
| `sources/guide_fiche_poste_ats_recrutement.pdf` | Guide de rédaction d'une fiche de poste |

## Décisions qui remplacent les documents

Les documents sont antérieurs à ces décisions ; en cas de contradiction, ce qui suit l'emporte.

- **Interface : Electron + React (Vite) + Tailwind CSS**, en JavaScript. La recommandation PyQt6 / PySide6 du cahier
  des charges est annulée. Next.js n'est pas utilisé : il fait double emploi avec Vite comme outil de build, et
  une application Electron n'a pas besoin de rendu serveur.
- **Backend : Python, FastAPI, SQLAlchemy, SQLite**, lancé et arrêté par Electron, joignable uniquement sur
  `127.0.0.1` avec un jeton généré à chaque lancement.
- **Une seule entreprise et un seul compte par installation.** Le mot de passe de démarrage en clair
  (`APP_PASSWORD`) et la clé de chiffrement dans `.env` (`ENCRYPTION_KEY`) de l'ancienne configuration sont
  remplacés par un compte protégé par argon2 et une clé de données chiffrée (voir `docs/securite.md`).
- **Dépendances séparées** : `requirements.txt` (socle, installation rapide) et `requirements-ia.txt`
  (spaCy, sentence-transformers, mediapipe… plusieurs Go).
- **Hors périmètre du socle actuel** : application ou portail candidat, classement et scoring, NLP, entretiens
  vidéo, analyse du regard, anti-triche, installeur. Les tables correspondantes du cahier des charges
  (`candidats`, `analyses_cv`, `entretiens`, `alertes_triche`) seront recréées avec leurs modules.
