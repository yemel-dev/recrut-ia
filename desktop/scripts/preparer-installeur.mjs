// Prépare tout ce que l'installeur embarque, avant electron-builder (npm run dist).
//
// 1. Vérifie que les modèles d'IA sont téléchargés (modeles/ à la racine du dépôt).
// 2. Fige le backend Python en exécutable autonome avec PyInstaller (dist/injara-backend).
// 3. Windows : télécharge vc_redist.x64.exe (runtime Visual C++, requis par torch) et vérifie sa signature Microsoft.
//
// Plusieurs centaines de Mo sont produits ou téléchargés : à lancer sur une bonne connexion, ou en CI.

import { execFileSync, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { racine } from './electron.mjs';

const DEPOT = path.resolve(racine, '..');
const MODELES = path.join(DEPOT, 'modeles');
const VC_REDIST_URL = 'https://aka.ms/vs/17/release/vc_redist.x64.exe';
const VC_REDIST = path.join(racine, 'packaging', 'vc_redist.x64.exe');

function etape(message) {
  console.log(`\n▶ ${message}`);
}

function arreter(message) {
  console.error(`\n✖ ${message}`);
  process.exit(1);
}

function python() {
  const venv = process.platform === 'win32'
    ? path.join(DEPOT, '.venv', 'Scripts', 'python.exe')
    : path.join(DEPOT, '.venv', 'bin', 'python');
  return process.env.INJARA_PYTHON || (fs.existsSync(venv) ? venv : 'python');
}

function verifierModeles() {
  etape('Modèles d\'IA');
  // Les modèles de l'OCR sont fournis avec le paquet rapidocr : PyInstaller les embarque avec lui.
  const attendus = [
    ['paraphrase-multilingual-MiniLM-L12-v2/model.safetensors', 'python -m backend.ia.telecharger_modele'],
  ];
  for (const [chemin, commande] of attendus) {
    if (!fs.existsSync(path.join(MODELES, chemin))) arreter(`modeles/${chemin} manquant. Lancez d'abord : ${commande}`);
    console.log(`  modeles/${chemin}`);
  }
}

function figerBackend() {
  etape('Backend Python figé (PyInstaller)');
  const resultat = spawnSync(
    python(),
    ['-m', 'PyInstaller', 'packaging/injara-backend.spec', '--noconfirm', '--distpath', 'dist', '--workpath', 'build/pyinstaller'],
    { cwd: DEPOT, stdio: 'inherit' },
  );
  if (resultat.status !== 0) arreter('PyInstaller a échoué (pip install -r requirements-build.txt ?).');
  const exe = path.join(DEPOT, 'dist', 'injara-backend', process.platform === 'win32' ? 'injara-backend.exe' : 'injara-backend');
  if (!fs.existsSync(exe)) arreter(`${exe} introuvable après PyInstaller.`);
  console.log(`  ${exe}`);
}

async function preparerVcRedist() {
  etape('Runtime Microsoft Visual C++ (vc_redist.x64.exe)');
  if (!fs.existsSync(VC_REDIST)) {
    console.log(`  téléchargement depuis ${VC_REDIST_URL}`);
    const reponse = await fetch(VC_REDIST_URL);
    if (!reponse.ok) arreter(`téléchargement impossible (HTTP ${reponse.status}).`);
    fs.writeFileSync(VC_REDIST, Buffer.from(await reponse.arrayBuffer()));
  }
  // Signature Authenticode valide et émise pour Microsoft : sinon on refuse de l'embarquer.
  const verification = execFileSync('powershell.exe', [
    '-NoProfile', '-Command',
    `$s = Get-AuthenticodeSignature -LiteralPath '${VC_REDIST}'; "$($s.Status)|$($s.SignerCertificate.Subject)"`,
  ], { encoding: 'utf8' }).trim();
  const [statut, signataire = ''] = verification.split('|');
  if (statut !== 'Valid' || !signataire.includes('O=Microsoft Corporation')) {
    fs.rmSync(VC_REDIST, { force: true });
    arreter(`signature de vc_redist.x64.exe refusée (${verification}). Fichier supprimé.`);
  }
  console.log(`  signature valide : ${signataire}`);
}

verifierModeles();
figerBackend();
if (process.platform === 'win32') await preparerVcRedist();
console.log('\n✔ Prêt pour electron-builder.');
