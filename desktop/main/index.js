// Processus principal d'Electron : fenêtre, cycle de vie du backend Python, pont API.

const { app, BrowserWindow, Menu, dialog, ipcMain, session } = require('electron');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

const { Backend } = require('./backend');
const { installerPontApi, viderCVOuverts } = require('./api');

const URL_DEV = process.env.INJARA_DEV_URL || null;
const PAGE = path.join(__dirname, '..', 'renderer', 'dist', 'index.html');
const URL_PAGE = pathToFileURL(PAGE).href;

let fenetre = null;

// Barre de titre dessinée par l'interface (fenêtre sans cadre natif), aux couleurs du thème.
const HAUTEUR_TITRE = 40;
const COULEURS_THEME = {
  sombre: { fond: '#010d1f', symboles: '#c9d8ec' },
  clair: { fond: '#e9eff7', symboles: '#031e40' },
};
// Boutons natifs par-dessus la page (Window Controls Overlay) sous Windows seulement : sous Linux (Wayland), Electron
// plante avec cette surcouche ; l'interface y dessine ses propres boutons (canal injara:fenetre). macOS garde ses pastilles.
const SURCOUCHE_NATIVE = process.platform === 'win32';
const surcoucheTitre = (theme) => ({ color: COULEURS_THEME[theme].fond, symbolColor: COULEURS_THEME[theme].symboles, height: HAUTEUR_TITRE });
let backend = null;
let arretEnCours = false;

function origineAutorisee(url) {
  if (!url) return false;
  if (URL_DEV) return url.startsWith(URL_DEV);
  return url.split('#')[0] === URL_PAGE;
}

function creerFenetre() {
  fenetre = new BrowserWindow({
    width: 1360,
    height: 860,
    minWidth: 1100,
    minHeight: 680,
    show: false,
    title: 'INJARA',
    backgroundColor: COULEURS_THEME.sombre.fond,
    titleBarStyle: 'hidden',
    ...(SURCOUCHE_NATIVE && { titleBarOverlay: surcoucheTitre('sombre') }),
    icon: path.join(__dirname, '..', 'renderer', 'public', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, '..', 'preload', 'index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      spellcheck: true,
      backgroundThrottling: false, // un entretien enregistré continue même si la fenêtre est réduite
    },
  });

  // Aucune navigation hors de l'application, aucune nouvelle fenêtre.
  fenetre.webContents.on('will-navigate', (event, url) => {
    if (!origineAutorisee(url)) event.preventDefault();
  });
  fenetre.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  fenetre.once('ready-to-show', () => fenetre.show());
  const signalerEtat = () => fenetre?.webContents.send('injara:fenetre-etat', { agrandie: fenetre.isMaximized() });
  fenetre.on('maximize', signalerEtat);
  fenetre.on('unmaximize', signalerEtat);
  fenetre.on('closed', () => {
    fenetre = null;
  });

  if (URL_DEV) fenetre.loadURL(URL_DEV);
  else fenetre.loadFile(PAGE);
}

async function demarrer() {
  // Permis : la copie dans le presse-papiers (clé de récupération, lien du candidat) et, pour l'interface d'INJARA
  // seulement, la caméra et le micro de l'entretien vidéo (jamais l'écran). Tout le reste est refusé.
  const PERMISSIONS = new Set(['clipboard-sanitized-write']);
  const autorise = (wc, permission, details) => {
    if (PERMISSIONS.has(permission)) return true;
    if (permission !== 'media' || !wc || !origineAutorisee(wc.getURL())) return false;
    const types = details?.mediaTypes;
    return !types || types.every((t) => t === 'video' || t === 'audio');
  };
  session.defaultSession.setPermissionRequestHandler((wc, permission, callback, details) => callback(autorise(wc, permission, details)));
  session.defaultSession.setPermissionCheckHandler((wc, permission, _origine, details) => autorise(wc, permission, details));
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
  installerPontApi({ backend, origineAutorisee, fenetre: () => fenetre });
  ipcMain.on('injara:theme', (event, theme) => {
    if (!fenetre || !COULEURS_THEME[theme] || !origineAutorisee(event.senderFrame?.url)) return;
    fenetre.setBackgroundColor(COULEURS_THEME[theme].fond);
    if (SURCOUCHE_NATIVE) fenetre.setTitleBarOverlay(surcoucheTitre(theme));
  });
  ipcMain.on('injara:fenetre', (event, action) => {
    if (!fenetre || !origineAutorisee(event.senderFrame?.url)) return;
    if (action === 'reduire') fenetre.minimize();
    else if (action === 'agrandir') fenetre.isMaximized() ? fenetre.unmaximize() : fenetre.maximize();
    else if (action === 'fermer') fenetre.close();
  });
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
    Promise.all([backend.arreter(), viderCVOuverts()]).finally(() => app.quit());
  });
}
