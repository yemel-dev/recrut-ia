# backend/ia — NLP et scoring

Vide pour l'instant. Dépendances : `requirements-ia.txt` (séparées du socle).

Repères issus du cahier des charges (`docs/sources/`) :

- Extraction : PyMuPDF (PDF), python-docx (DOCX), spaCy `fr_core_news_lg`.
- Similarité : Sentence-BERT `paraphrase-multilingual-MiniLM-L12-v2`.
- Score d'un CV pour un poste : compétences 40 %, expérience 25 %, formation 20 %, adéquation globale 15 %.
- Seuls les postes au statut `actif` participent au classement.
