// Développement : serveur Vite (rechargement à chaud de l'interface) + Electron qui le charge.
// Electron lance lui-même le backend Python (voir main/backend.js).

import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';

const racine = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
const electron = require('electron'); // chemin du binaire Electron

const serveur = await createServer({ configFile: path.join(racine, 'vite.config.mjs') });
await serveur.listen();
const url = serveur.resolvedUrls.local[0];
console.log(`Interface servie sur ${url}`);

const processus = spawn(electron, ['.'], {
  cwd: racine,
  stdio: 'inherit',
  env: { ...process.env, INJARA_DEV_URL: url },
});
processus.on('exit', async (code) => {
  await serveur.close();
  process.exit(code ?? 0);
});
