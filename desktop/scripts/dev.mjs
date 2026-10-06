// Développement : serveur Vite (rechargement à chaud de l'interface) + Electron qui le charge.
// Electron lance lui-même le backend Python (voir main/backend.js).

import path from 'node:path';
import { createServer } from 'vite';
import { lancerElectron, racine } from './electron.mjs';

const serveur = await createServer({ configFile: path.join(racine, 'vite.config.mjs') });
await serveur.listen();
const url = serveur.resolvedUrls.local[0];
console.log(`Interface servie sur ${url}`);

lancerElectron({ INJARA_DEV_URL: url }).on('exit', async (code) => {
  await serveur.close();
  process.exit(code ?? 0);
});
