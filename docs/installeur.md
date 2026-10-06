# Installeur INJARA

L'application installée n'a besoin ni de Python ni de Node sur le poste du recruteur : le backend est figé en
exécutable autonome (PyInstaller), les modèles d'IA sont copiés à côté, et l'installeur Windows ajoute le runtime
Microsoft Visual C++ si besoin.

## Construire

À faire sur le système visé (un installeur Windows se construit sous Windows, un paquet Linux sous Linux), sur une
bonne connexion : la première construction télécharge plusieurs centaines de Mo (outils NSIS, Electron, vc_redist).

```bash
# À la racine du dépôt, dans l'environnement virtuel
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-build.txt
python -m backend.ia.telecharger_modele   # Sentence-BERT -> modeles/ (les modèles de l'OCR viennent avec rapidocr)

cd desktop
npm install
npm run dist          # Windows : desktop/out/INJARA-Setup-<version>.exe ; Linux : AppImage et .deb
```

`npm run dist` enchaîne :

1. `scripts/preparer-installeur.mjs` : vérifie les modèles, fige le backend (`packaging/injara-backend.spec` →
   `dist/injara-backend/`), et sous Windows télécharge `vc_redist.x64.exe` dans `desktop/packaging/` puis vérifie sa
   signature Authenticode (valide et émise pour Microsoft Corporation, sinon le fichier est supprimé et la
   construction s'arrête) ;
2. `vite build` : l'interface ;
3. `electron-builder` : l'installeur (configuration dans `desktop/package.json`, clé `build`).

## Ce que fait l'installeur Windows

- Installation pour tous les utilisateurs (`Program Files`, droits administrateur), dossier modifiable.
- Runtime Visual C++ 2015-2022 x64 : si la clé `HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64`
  (`Installed = 1`) est absente, `vc_redist.x64.exe /install /quiet /norestart` est lancé
  (`desktop/packaging/installer.nsh`). Codes acceptés : 0, 3010 (redémarrage conseillé), 1638 (version plus récente
  déjà présente). En cas d'échec, l'installation continue avec un message : seul le critère « adéquation globale »
  sera désactivé.
- Les données de l'utilisateur restent dans son profil (`%APPDATA%\INJARA\donnees`), hors du dossier d'installation :
  une désinstallation ou une mise à jour ne les efface pas.

## Disposition de l'application installée

```
resources/
  app.asar             interface et processus principal Electron
  backend/             injara-backend(.exe) et ses bibliothèques (PyInstaller)
  modeles/             paraphrase-multilingual-MiniLM-L12-v2/
```

Electron lance `resources/backend/injara-backend` avec `INJARA_MODELES_DIR=resources/modeles`
(`desktop/main/backend.js`). La sonde du moteur d'analyse appelle ce même exécutable avec
`--sonde-moteur-analyse` (`packaging/lancer_backend.py`).

## Ce qui a été vérifié

- Le backend figé (`dist/injara-backend`, 902 Mo, 18 minutes de construction sous Windows) a été lancé seul, comme le
  fait l'application installée, sans le Python du dépôt : démarrage en 3 s, sonde du moteur d'analyse, torch et
  Sentence-BERT chargés (adéquation comptée), CV scanné lu par OCR puis classé, aucun CV en clair sur le disque, arrêt
  à la fermeture du tube.
- **Pas encore vérifié** : la construction par electron-builder et l'installation elle-même (installeur NSIS,
  installation silencieuse de vc_redist sur un poste qui ne l'a pas, raccourcis, désinstallation). À tester sur une
  machine Windows « propre » (machine virtuelle sans Visual C++) avant toute diffusion.

## À savoir

- Taille : comptez environ 1,2 Go installé, dont torch (~400 Mo), le modèle Sentence-BERT (~470 Mo), et pour l'OCR
  onnxruntime, opencv et les modèles PP-OCRv6 (~150 Mo).
- Pas de signature de code : Windows SmartScreen avertira au premier lancement de l'installeur. Pour l'éviter, signer
  avec un certificat de signature de code (`win.certificateFile` / `CSC_LINK` d'electron-builder).
- Sous Linux, torch n'a pas besoin du runtime Visual C++ ; rien de plus n'est installé.
