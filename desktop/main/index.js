// Processus principal d'Electron : fenêtre, cycle de vie du backend Python, pont API.

const { app, BrowserWindow, Menu, dialog, session } = require('electron');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

const { Backend } = require('./backend');
const { installerPontApi } = require('./api');

const URL_DEV = process.env.INJARA_DEV_URL || null;
const PAGE = path.join(__dirname, '..', 'renderer', 'dist', 'index.html');
const URL_PAGE = pathToFileURL(PAGE).href;

let fenetre = null;
let backend = null;
let arretEnCours = false;

function origineAutorisee(url) {
  if (!url) return false;
  if (URL_DEV) return url.startsWith(URL_DEV);
  return url.split('#')[0] === URL_PAGE;
}

function creerFenetre() {
  fenetre = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 960,
    minHeight: 640,
    show: false,
    title: 'INJARA',
    backgroundColor: '#f4f7fa',
    icon: path.join(__dirname, '..', 'renderer', 'public', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, '..', 'preload', 'index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      spellcheck: true,
    },
  });

  // Aucune navigation hors de l'application, aucune nouvelle fenêtre.
  fenetre.webContents.on('will-navigate', (event, url) => {
    if (!origineAutorisee(url)) event.preventDefault();
  });
  fenetre.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  fenetre.once('ready-to-show', () => fenetre.show());
  fenetre.on('closed', () => {
    fenetre = null;
  });

  if (URL_DEV) fenetre.loadURL(URL_DEV);
  else fenetre.loadFile(PAGE);
}

async function demarrer() {
  // Seule la copie dans le presse-papiers (clé de récupération) est permise ; caméra, micro, etc. sont refusés.
  const PERMISSIONS = new Set(['clipboard-sanitized-write']);
  session.defaultSession.setPermissionRequestHandler((_wc, permission, callback) => callback(PERMISSIONS.has(permission)));
  session.defaultSession.setPermissionCheckHandler((_wc, permission) => PERMISSIONS.has(permission));
  if (!URL_DEV) Menu.setApplicationMenu(null);

  // INJARA_DATA_DIR permet d'utiliser un autre dossier de données (tests, démonstration).
  const dataDir = process.env.INJARA_DATA_DIR || path.join(app.getPath('userData'), 'donnees');
  backend = new Backend({ dataDir });
  try {
    await backend.demarrer();
  } catch (err) {
    dialog.showErrorBox('INJARA ne peut pas démarrer', err.message);
    app.exit(1);
    return;
  }
  installerPontApi({ backend, origineAutorisee });
  creerFenetre();
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (!fenetre) return;
    if (fenetre.isMinimized()) fenetre.restore();
    fenetre.focus();
  });

  app.whenReady().then(demarrer);

  app.on('window-all-closed', () => app.quit());

  // Arrêter le backend avant de quitter. Sa session en mémoire disparaît avec lui : fermer = se déconnecter.
  app.on('before-quit', (event) => {
    if (arretEnCours || !backend) return;
    event.preventDefault();
    arretEnCours = true;
    backend.arreter().finally(() => app.quit());
  });
}
