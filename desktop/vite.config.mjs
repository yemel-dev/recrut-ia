import path from 'node:path';
import { fileURLToPath } from 'node:url';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

const racine = path.dirname(fileURLToPath(import.meta.url));

// Politique de sécurité du contenu, ajoutée uniquement au build (Vite a besoin de scripts en ligne en dev).
// L'interface ne parle qu'au processus principal par IPC : aucune connexion réseau n'est autorisée.
const CSP = [
  "default-src 'none'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  "font-src 'self'",
  "connect-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
].join('; ');

const csp = {
  name: 'injara-csp',
  apply: 'build',
  transformIndexHtml: (html) =>
    html.replace('<meta charset="UTF-8" />', `<meta charset="UTF-8" />\n    <meta http-equiv="Content-Security-Policy" content="${CSP}" />`),
};

export default defineConfig({
  root: path.join(racine, 'renderer'),
  base: './',
  plugins: [react(), tailwindcss(), csp],
  server: { host: '127.0.0.1', port: 5199 },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    // Polices toujours en fichiers (jamais en data:) : la CSP n'autorise que font-src 'self'.
    assetsInlineLimit: (fichier) => (fichier.endsWith('.woff2') ? false : undefined),
  },
});
