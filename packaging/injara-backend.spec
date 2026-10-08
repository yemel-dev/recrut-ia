# -*- mode: python -*-
# Backend INJARA en exécutable autonome (dossier dist/injara-backend), embarqué par l'installeur Electron.
#
#   python -m PyInstaller packaging/injara-backend.spec --noconfirm --distpath dist --workpath build/pyinstaller
#
# Les modèles d'IA ne sont pas dedans : l'installeur les copie à part (resources/modeles), voir desktop/package.json.
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules, copy_metadata

racine = Path(SPECPATH).parent

datas, binaries, hiddenimports = [], [], []

# Bibliothèques à chargement dynamique : on prend tout (modules, données, bibliothèques natives).
for paquet in ("sentence_transformers", "transformers", "tokenizers", "rapidocr", "onnxruntime", "uvicorn", "websockets"):
    d, b, h = collect_all(paquet)
    datas += d
    binaries += b
    hiddenimports += h

# transformers vérifie les versions installées via les métadonnées des paquets.
for paquet in (
    "torch", "transformers", "tokenizers", "huggingface_hub", "safetensors", "sentence_transformers", "tqdm",
    "regex", "requests", "packaging", "filelock", "numpy", "pyyaml", "scikit-learn", "scipy", "pillow",
):
    try:
        datas += copy_metadata(paquet)
    except Exception:  # paquet absent de cet environnement : rien à copier
        pass

datas += [(str(racine / "backend" / "web"), "backend/web")]  # page web du candidat (entretien vidéo)
datas += collect_data_files("docx")  # modèle de document de python-docx
datas += collect_data_files("googleapiclient", includes=["discovery_cache/documents/gmail.v1.json"])
hiddenimports += collect_submodules("backend")
hiddenimports += collect_submodules("keyring.backends")

a = Analysis(
    [str(racine / "packaging" / "lancer_backend.py")],
    pathex=[str(racine)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "mediapipe"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="injara-backend",
    console=True,  # Electron lit stdout/stderr ; la fenêtre est masquée par windowsHide
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="injara-backend", upx=False)
