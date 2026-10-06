// Lance Electron sur le dossier desktop/.
// ELECTRON_RUN_AS_NODE (posé par VS Code et d'autres outils basés sur Electron) ferait tourner Electron
// comme un simple Node : on le retire de l'environnement transmis.

import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const racine = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const electron = createRequire(import.meta.url)('electron'); // chemin du binaire

export function lancerElectron(envSupplementaire = {}) {
  const env = { ...process.env, ...envSupplementaire };
  delete env.ELECTRON_RUN_AS_NODE;
  return spawn(electron, ['.'], { cwd: racine, stdio: 'inherit', env });
}

// Utilisation directe : node scripts/electron.mjs (version compilée de l'interface)
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  lancerElectron().on('exit', (code) => process.exit(code ?? 0));
}
