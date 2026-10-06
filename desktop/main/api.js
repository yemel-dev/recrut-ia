// Pont entre l'interface et le backend.
//
// L'interface n'appelle jamais le backend directement : elle passe par le processus principal (IPC),
// qui ajoute le jeton de lancement et le jeton de session. Aucun de ces deux secrets n'atteint l'interface.
// Les accès au disque (import de CV, ouverture d'un CV, identifiants Google) passent aussi par ici,
// avec des vérifications strictes sur les chemins.

const { dialog, ipcMain, shell } = require('electron');
const crypto = require('node:crypto');
const fs = require('node:fs/promises');
const http = require('node:http');
const path = require('node:path');

const METHODES = new Set(['GET', 'POST', 'PUT', 'DELETE']);
const CHEMIN_VALIDE = /^\/[a-z0-9\-/]*(\?[a-z0-9_=&\-.%@+]*)?$/i;
const EXTENSIONS_IMPORT = new Set(['.pdf', '.docx', '.zip']);
const EXTENSIONS_CV = new Set(['.pdf', '.docx']);
const TAILLE_MAX_IMPORT = 200 * 1024 * 1024; // comme l'agent : 200 Mo par archive
const TAILLE_MAX_IDENTIFIANTS = 64 * 1024;

function installerPontApi({ backend, origineAutorisee, dossierCV, fenetre }) {
  let jetonSession = null;

  // Requête HTTP vers le backend, sans délai maximal : la liaison Gmail attend que l'utilisateur
  // ait fini dans son navigateur.
  function envoyer(methode, chemin, corps, typeContenu) {
    return new Promise((resolve) => {
      const enTetes = { 'X-Injara-Token': backend.token };
      if (jetonSession) enTetes['X-Injara-Session'] = jetonSession;
      if (corps !== undefined) {
        enTetes['Content-Type'] = typeContenu;
        enTetes['Content-Length'] = corps.length;
      }
      const requete = http.request({ host: '127.0.0.1', port: backend.port, path: chemin, method: methode, headers: enTetes }, (reponse) => {
        const morceaux = [];
        reponse.on('data', (m) => morceaux.push(m));
        reponse.on('end', () => resolve(interpreter(chemin, reponse.statusCode, Buffer.concat(morceaux).toString('utf8'))));
      });
      requete.on('error', () =>
        resolve({ ok: false, statut: 0, donnees: { detail: "Le moteur INJARA ne répond plus. Redémarrez l'application." } }),
      );
      if (corps !== undefined) requete.write(corps);
      requete.end();
    });
  }

  function interpreter(chemin, statut, texte) {
    let donnees = null;
    try {
      donnees = texte ? JSON.parse(texte) : null;
    } catch {
      donnees = { detail: texte };
    }
    const ok = statut >= 200 && statut < 300;
    // La session est gérée ici et jamais transmise à l'interface.
    if (ok && chemin === '/auth/connexion' && donnees?.jeton_session) {
      jetonSession = donnees.jeton_session;
      delete donnees.jeton_session;
    }
    const finDeSession = ok && (chemin === '/auth/deconnexion' || chemin === '/auth/recuperation');
    // Seul un 401 marqué « session_requise » signifie que la session est perdue (pas un mot de passe de messagerie refusé).
    const sessionRefusee = statut === 401 && donnees?.code === 'session_requise';
    if (finDeSession || sessionRefusee) jetonSession = null;
    return { ok, statut, donnees };
  }

  function verifierOrigine(event) {
    if (!origineAutorisee(event.senderFrame?.url)) throw new Error('Origine non autorisée.');
  }

  // --- Appels JSON -------------------------------------------------------------------------

  ipcMain.handle('injara:requete', async (event, { methode, chemin, corps } = {}) => {
    verifierOrigine(event);
    methode = String(methode || '').toUpperCase();
    if (!METHODES.has(methode) || typeof chemin !== 'string' || !CHEMIN_VALIDE.test(chemin) || chemin.includes('//')) {
      throw new Error('Requête invalide.');
    }
    const donnees = corps === undefined ? undefined : Buffer.from(JSON.stringify(corps), 'utf8');
    return envoyer(methode, chemin, donnees, 'application/json');
  });

  // --- Import de CV ------------------------------------------------------------------------

  ipcMain.handle('injara:choisir-cv', async (event) => {
    verifierOrigine(event);
    const { canceled, filePaths } = await dialog.showOpenDialog(fenetre(), {
      title: 'Importer des CV',
      properties: ['openFile', 'multiSelections'],
      filters: [{ name: 'CV (PDF, DOCX ou ZIP)', extensions: ['pdf', 'docx', 'zip'] }],
    });
    return canceled ? [] : filePaths;
  });

  ipcMain.handle('injara:importer-cv', async (event, chemins) => {
    verifierOrigine(event);
    if (!Array.isArray(chemins) || chemins.length === 0 || chemins.length > 1000) throw new Error('Requête invalide.');

    const fichiers = [];
    const refuses = [];
    for (const chemin of chemins) {
      const nom = typeof chemin === 'string' ? path.basename(chemin) : '?';
      const raison = await verifierFichierAImporter(chemin);
      if (raison) refuses.push({ filename: nom, reason: raison });
      else fichiers.push({ nom, contenu: await fs.readFile(chemin) });
    }
    if (fichiers.length === 0) {
      return { ok: true, statut: 200, donnees: { imported: [], duplicates_skipped: 0, rejected: refuses } };
    }
    const { corps, type } = multipart(fichiers);
    const reponse = await envoyer('POST', '/gmail/cvs/upload', corps, type);
    if (reponse.ok) reponse.donnees.rejected = [...refuses, ...reponse.donnees.rejected];
    return reponse;
  });

  // --- Ouverture d'un CV ---------------------------------------------------------------------

  ipcMain.handle('injara:ouvrir-cv', async (event, chemin) => {
    verifierOrigine(event);
    if (typeof chemin !== 'string') throw new Error('Requête invalide.');
    const absolu = path.resolve(chemin);
    const relatif = path.relative(path.resolve(dossierCV), absolu);
    if (!relatif || relatif.startsWith('..') || path.isAbsolute(relatif) || !EXTENSIONS_CV.has(path.extname(absolu).toLowerCase())) {
      return "Ce fichier n'est pas un CV d'INJARA.";
    }
    try {
      await fs.access(absolu);
    } catch {
      return 'Fichier introuvable : il a peut-être été déplacé ou supprimé.';
    }
    const erreur = await shell.openPath(absolu);
    return erreur ? `Impossible d'ouvrir le fichier : ${erreur}` : '';
  });

  // --- Identifiants Google (credentials.json) --------------------------------------------------

  ipcMain.handle('injara:importer-identifiants-google', async (event) => {
    verifierOrigine(event);
    const { canceled, filePaths } = await dialog.showOpenDialog(fenetre(), {
      title: 'Fichier d’identifiants Google (credentials.json)',
      properties: ['openFile'],
      filters: [{ name: 'Fichier JSON', extensions: ['json'] }],
    });
    if (canceled || !filePaths.length) return { annule: true };
    const infos = await fs.stat(filePaths[0]);
    if (!infos.isFile() || infos.size > TAILLE_MAX_IDENTIFIANTS) {
      return { ok: false, statut: 422, donnees: { detail: "Ce fichier n'est pas un fichier d'identifiants Google valide." } };
    }
    const contenu = await fs.readFile(filePaths[0], 'utf8');
    return envoyer('POST', '/agent/identifiants-google', Buffer.from(JSON.stringify({ contenu }), 'utf8'), 'application/json');
  });
}

async function verifierFichierAImporter(chemin) {
  if (typeof chemin !== 'string' || !path.isAbsolute(chemin)) return 'fichier introuvable';
  if (!EXTENSIONS_IMPORT.has(path.extname(chemin).toLowerCase())) return 'format non pris en charge (PDF, DOCX ou ZIP uniquement)';
  try {
    const infos = await fs.stat(chemin);
    if (!infos.isFile()) return "ce n'est pas un fichier";
    if (infos.size > TAILLE_MAX_IMPORT) return 'fichier trop volumineux (max 200 Mo)';
  } catch {
    return 'fichier introuvable';
  }
  return null;
}

function multipart(fichiers) {
  const frontiere = `----injara${crypto.randomBytes(12).toString('hex')}`;
  const parties = [];
  for (const { nom, contenu } of fichiers) {
    const nomSur = nom.replace(/["\r\n]/g, '_');
    parties.push(
      Buffer.from(
        // Nom en UTF-8 brut, comme le font les navigateurs.
        `--${frontiere}\r\nContent-Disposition: form-data; name="files"; filename="${nomSur}"\r\n` +
          'Content-Type: application/octet-stream\r\n\r\n',
        'utf8',
      ),
      contenu,
      Buffer.from('\r\n', 'utf8'),
    );
  }
  parties.push(Buffer.from(`--${frontiere}--\r\n`, 'utf8'));
  return { corps: Buffer.concat(parties), type: `multipart/form-data; boundary=${frontiere}` };
}

module.exports = { installerPontApi };
