// Lancement et arrêt du backend Python.
//
// - Jeton aléatoire généré à chaque lancement, transmis par variable d'environnement.
// - Le backend choisit lui-même un port libre sur 127.0.0.1 et l'annonce sur stdout (« INJARA_PORT=12345 »).
// - stdin reste ouvert : quand Electron s'arrête (même en plantant), le backend le voit et se termine.

const { spawn } = require('node:child_process');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const REPO_ROOT = path.resolve(__dirname, '..', '..');
const DELAI_DEMARRAGE_MS = 30_000;
const DELAI_ARRET_MS = 3_000;

function trouverPython() {
  if (process.env.INJARA_PYTHON) return process.env.INJARA_PYTHON;
  const venv = process.platform === 'win32'
    ? path.join(REPO_ROOT, '.venv', 'Scripts', 'python.exe')
    : path.join(REPO_ROOT, '.venv', 'bin', 'python');
  if (fs.existsSync(venv)) return venv;
  return process.platform === 'win32' ? 'python' : 'python3';
}

class Backend {
  constructor({ dataDir }) {
    this.dataDir = dataDir;
    this.token = crypto.randomBytes(32).toString('base64url');
    this.port = null;
    this.process = null;
  }

  get baseUrl() {
    return `http://127.0.0.1:${this.port}`;
  }

  demarrer() {
    const python = trouverPython();
    return new Promise((resolve, reject) => {
      const child = spawn(python, ['-m', 'backend'], {
        cwd: REPO_ROOT,
        env: {
          ...process.env,
          INJARA_TOKEN: this.token,
          INJARA_DATA_DIR: this.dataDir,
          PYTHONUNBUFFERED: '1',
          PYTHONUTF8: '1',
          PYTHONIOENCODING: 'utf-8',
        },
        stdio: ['pipe', 'pipe', 'pipe'],
        windowsHide: true,
      });
      this.process = child;

      let sortie = '';
      let erreurs = '';
      const echec = (message) => {
        clearTimeout(minuteur);
        reject(new Error(`${message}\n\nPython utilisé : ${python}\n${erreurs.trim()}`.trim()));
      };
      const minuteur = setTimeout(() => {
        echec('Le moteur INJARA ne répond pas.');
        this.arreter();
      }, DELAI_DEMARRAGE_MS);

      child.stdout.setEncoding('utf8');
      child.stdout.on('data', (morceau) => {
        if (this.port) return;
        sortie += morceau;
        const trouve = sortie.match(/INJARA_PORT=(\d+)/);
        if (trouve) {
          this.port = Number(trouve[1]);
          clearTimeout(minuteur);
          resolve();
        }
      });
      child.stderr.setEncoding('utf8');
      child.stderr.on('data', (morceau) => {
        erreurs = (erreurs + morceau).slice(-4000);
        process.stderr.write(morceau);
      });
      child.on('error', (err) => echec(`Impossible de lancer Python : ${err.message}`));
      child.on('exit', (code) => {
        this.process = null;
        if (!this.port) echec(`Le moteur INJARA s'est arrêté au démarrage (code ${code}).`);
      });
    });
  }

  arreter() {
    const child = this.process;
    if (!child) return Promise.resolve();
    return new Promise((resolve) => {
      const forcer = setTimeout(() => {
        child.kill();
        resolve();
      }, DELAI_ARRET_MS);
      child.once('exit', () => {
        clearTimeout(forcer);
        resolve();
      });
      // Fermer stdin suffit : le backend s'arrête de lui-même.
      child.stdin.end();
    });
  }
}

module.exports = { Backend };
