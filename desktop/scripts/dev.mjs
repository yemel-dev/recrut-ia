// Développement : serveur Vite (rechargement à chaud de l'interface) + Electron qui le charge.
// Electron lance lui-même le backend Python (voir main/backend.js).
// --demo : boîte mail de démonstration (GMAIL_MODE=fake), quel que soit le terminal (PowerShell, cmd, bash).

import path from 'node:path';
import { createServer } from 'vite';
import { lancerElectron, racine } from './electron.mjs';

const serveur = await createServer({ configFile: path.join(racine, 'vite.config.mjs') });
await serveur.listen();
const url = serveur.resolvedUrls.local[0];
console.log(`Interface servie sur ${url}`);

const demo = process.argv.includes('--demo');
if (demo) console.log('Mode démo : la boîte mail est simulée.');

lancerElectron({ INJARA_DEV_URL: url, ...(demo && { GMAIL_MODE: 'fake' }) }).on('exit', async (code) => {
  await serveur.close();
  process.exit(code ?? 0);
});
