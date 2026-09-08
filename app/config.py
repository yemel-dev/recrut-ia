import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Chemins principaux
BASE_DIR     = Path(__file__).parent.parent
DATA_DIR     = BASE_DIR / "data"
CVS_DIR      = DATA_DIR / "cvs"
MODELS_DIR   = DATA_DIR / "models"
DATABASE_URL = f"sqlite:///{BASE_DIR}/recrut_ia.db"

# Gmail
GMAIL_CHECK_INTERVAL = int(os.getenv("GMAIL_CHECK_INTERVAL", 5))

# Sécurité
APP_PASSWORD    = os.getenv("APP_PASSWORD", "recrut2026")
ENCRYPTION_KEY  = os.getenv("ENCRYPTION_KEY", "")

# Scoring — poids de l'algorithme
POIDS_COMPETENCES  = 0.40
POIDS_EXPERIENCE   = 0.25
POIDS_FORMATION    = 0.20
POIDS_ADEQUATION   = 0.15

# Anti-triche — applications suspectes
APPS_SUSPECTES = [
    "chrome", "firefox", "msedge", "opera",
    "chatgpt", "brave", "safari", "iexplore"
]
