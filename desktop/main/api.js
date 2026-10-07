// Pont entre l'interface et le backend.
//
// L'interface n'appelle jamais le backend directement : elle passe par le processus principal (IPC),
// qui ajoute le jeton de lancement et le jeton de session. Aucun de ces deux secrets n'atteint l'interface.
// Les accès au disque (import de CV, ouverture d'un CV, identifiants Google) passent aussi par ici,
// avec des vérifications strictes sur les chemins.
//
// Les CV sont chiffrés sur le disque. Pour en ouvrir un, le backend le renvoie déchiffré : il est posé dans un
// dossier temporaire privé (DOSSIER_OUVERTS), vidé à la déconnexion, à la fermeture et au lancement suivant.

const { app, dialog, ipcMain, shell } = require('electron');
const crypto = require('node:crypto');
const fsFlux = require('node:fs');
const fs = require('node:fs/promises');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');
const { pipeline } = require('node:stream/promises');
const { gabaritRapport, genererPdf, nomDeFichier } = require('./rapport');

const METHODES = new Set(['GET', 'POST', 'PUT', 'DELETE']);
const CHEMIN_VALIDE = /^\/[a-z0-9_\-/]*(\?[a-z0-9_=&\-.%@+]*)?$/i;
const EXTENSIONS_IMPORT = new Set(['.pdf', '.docx', '.zip']);
const EXTENSIONS_CV = new Set(['.pdf', '.docx']);
const TAILLE_MAX_IMPORT = 200 * 1024 * 1024; // comme l'agent : 200 Mo par archive
const TAILLE_MAX_IDENTIFIANTS = 64 * 1024;
const TAILLE_MAX_MORCEAU = 16 * 1024 * 1024; // comme le backend
const TAILLE_MAX_SIGNAL = 64 * 1024;
const TAILLE_MAX_IMAGE = 512 * 1024; // comme le backend
const TAILLE_MAX_EXTRAIT = 30 * 16000 * 4; // 30 s de son 16 kHz en flottants 32 bits, comme le backend
const LOCUTEURS = ['recruteur', 'candidat'];
const DOSSIER_OUVERTS = path.join(os.tmpdir(), 'injara-cv-ouverts');

/** Efface les CV déchiffrés pour consultation. Un fichier encore ouvert dans un logiciel (verrouillé sous Windows)
 * reste en place jusqu'au prochain nettoyage. */
async function viderCVOuverts() {
  let noms = [];
  try {
    noms = await fs.readdir(DOSSIER_OUVERTS);
  } catch {
    return;
  }
  await Promise.all(noms.map((nom) => fs.rm(path.join(DOSSIER_OUVERTS, nom), { force: true, recursive: true }).catch(() => {})));
}

function installerPontApi({ backend, origineAutorisee, fenetre }) {
  let jetonSession = null;
  let salle = null; // connexion de signalisation de l'entretien en cours : { ws }
  viderCVOuverts();

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
        reponse.on('end', () => {
          const tampon = Buffer.concat(morceaux);
          const binaire = reponse.statusCode === 200 && reponse.headers['content-type'] === 'application/octet-stream';
          resolve(binaire ? { ok: true, statut: 200, tampon, enTetes: reponse.headers } : interpreter(chemin, reponse.statusCode, tampon.toString('utf8')));
        });
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
    if (finDeSession || sessionRefusee) {
      jetonSession = null;
      fermerSalle();
      viderCVOuverts();
    }
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

  ipcMain.handle('injara:ouvrir-cv', async (event, candidatureId) => {
    verifierOrigine(event);
    if (!Number.isSafeInteger(candidatureId) || candidatureId <= 0) throw new Error('Requête invalide.');
    const reponse = await envoyer('GET', `/candidatures/${candidatureId}/cv`);
    if (!reponse.tampon) return reponse.donnees?.detail || "Impossible d'ouvrir le CV.";
    let nom;
    try {
      nom = path.basename(decodeURIComponent(reponse.enTetes['x-injara-nom-fichier'] || ''));
    } catch {
      nom = '';
    }
    const extension = path.extname(nom).toLowerCase();
    if (!EXTENSIONS_CV.has(extension)) return "Ce fichier n'est pas un CV d'INJARA.";
    // Un sous-dossier par ouverture : deux CV de même nom ne s'écrasent pas.
    await fs.mkdir(DOSSIER_OUVERTS, { recursive: true, mode: 0o700 });
    const dossier = await fs.mkdtemp(path.join(DOSSIER_OUVERTS, `${candidatureId}-`));
    const fichier = path.join(dossier, nom.replace(/[<>:"/\\|?*\u0000-\u001f]/g, '_'));
    await fs.writeFile(fichier, reponse.tampon, { mode: 0o600 });
    const erreur = await shell.openPath(fichier);
    return erreur ? `Impossible d'ouvrir le fichier : ${erreur}` : '';
  });

  // --- Rapport PDF d'un candidat ------------------------------------------------------------------

  ipcMain.handle('injara:exporter-rapport', async (event, candidatureId) => {
    verifierOrigine(event);
    if (!Number.isSafeInteger(candidatureId) || candidatureId <= 0) throw new Error('Requête invalide.');
    const reponse = await envoyer('GET', `/candidatures/${candidatureId}/rapport`);
    if (!reponse.ok) return { ok: false, message: reponse.donnees?.detail || 'Rapport indisponible.' };
    const donnees = reponse.donnees;
    const { canceled, filePath } = await dialog.showSaveDialog(fenetre(), {
      title: 'Exporter le rapport',
      defaultPath: path.join(app.getPath('documents'), nomDeFichier(donnees)),
      filters: [{ name: 'Document PDF', extensions: ['pdf'] }],
    });
    if (canceled || !filePath) return { annule: true };
    try {
      await fs.writeFile(filePath, await genererPdf(gabaritRapport(donnees)));
    } catch (err) {
      return { ok: false, message: `Le rapport n'a pas pu être enregistré : ${err.message}` };
    }
    return { ok: true, chemin: filePath };
  });

  // --- Salle de visio (entretien vidéo) ---------------------------------------------------------------------
  // La signalisation WebRTC passe par ici : l'interface n'a ni le port du backend, ni le droit d'ouvrir un réseau.

  function fermerSalle() {
    if (!salle) return;
    const { ws } = salle;
    salle = null;
    try {
      ws.close();
    } catch {
      // déjà fermée
    }
  }

  const idValide = (id) => Number.isSafeInteger(id) && id > 0;

  ipcMain.handle('injara:salle-ouvrir', async (event, entretienId) => {
    verifierOrigine(event);
    if (!idValide(entretienId)) throw new Error('Requête invalide.');
    fermerSalle();
    const reponse = await envoyer('POST', `/entretiens/${entretienId}/salle`, Buffer.from('{}', 'utf8'), 'application/json');
    if (!reponse.ok) return reponse;
    const { ticket, ice } = reponse.donnees;
    const emetteur = event.sender;
    const ws = new WebSocket(`ws://127.0.0.1:${backend.port}/public/ws/recruteur?ticket=${encodeURIComponent(ticket)}`);
    salle = { ws };
    const actif = () => salle?.ws === ws && !emetteur.isDestroyed();
    ws.addEventListener('message', (e) => {
      if (actif()) emetteur.send('injara:salle-message', String(e.data));
    });
    ws.addEventListener('close', (e) => {
      const etaitActive = actif();
      if (salle?.ws === ws) salle = null;
      if (etaitActive) emetteur.send('injara:salle-fermee', { code: e.code });
    });
    try {
      await new Promise((resolve, reject) => {
        ws.addEventListener('open', resolve, { once: true });
        ws.addEventListener('error', () => reject(new Error('connexion refusée')), { once: true });
      });
    } catch {
      if (salle?.ws === ws) salle = null;
      return { ok: false, statut: 0, donnees: { detail: "La salle d'entretien n'a pas pu être ouverte." } };
    }
    return { ok: true, statut: 200, donnees: { ice } };
  });

  ipcMain.handle('injara:salle-envoyer', (event, texte) => {
    verifierOrigine(event);
    if (typeof texte !== 'string' || texte.length > TAILLE_MAX_SIGNAL) throw new Error('Requête invalide.');
    if (salle?.ws.readyState === WebSocket.OPEN) salle.ws.send(texte);
  });

  ipcMain.handle('injara:salle-fermer', (event) => {
    verifierOrigine(event);
    fermerSalle();
  });

  // --- Enregistrement de l'entretien -------------------------------------------------------------------------

  ipcMain.handle('injara:enregistrement-morceau', async (event, entretienId, morceau) => {
    verifierOrigine(event);
    const tampon = ArrayBuffer.isView(morceau)
      ? Buffer.from(morceau.buffer, morceau.byteOffset, morceau.byteLength)
      : morceau instanceof ArrayBuffer
        ? Buffer.from(morceau)
        : null;
    if (!idValide(entretienId) || !tampon || tampon.length === 0 || tampon.length > TAILLE_MAX_MORCEAU) throw new Error('Requête invalide.');
    return envoyer('PUT', `/entretiens/${entretienId}/enregistrement`, tampon, 'application/octet-stream');
  });

  // Analyse du regard : une image (JPEG) du candidat, envoyée au backend local qui renvoie l'état du moment.
  ipcMain.handle('injara:regard-image', (event, entretienId, image) => {
    verifierOrigine(event);
    const tampon = ArrayBuffer.isView(image) ? Buffer.from(image.buffer, image.byteOffset, image.byteLength) : image instanceof ArrayBuffer ? Buffer.from(image) : null;
    if (!idValide(entretienId) || !tampon || tampon.length === 0 || tampon.length > TAILLE_MAX_IMAGE) throw new Error('Requête invalide.');
    return envoyer('PUT', `/entretiens/${entretienId}/regard`, tampon, 'image/jpeg');
  });

  // Sous-titres : un extrait de son (flottants 32 bits, mono, 16 kHz) ; le backend renvoie les phrases reconnues.
  ipcMain.handle('injara:sous-titres-audio', (event, entretienId, locuteur, debut, audio) => {
    verifierOrigine(event);
    const tampon = audio instanceof ArrayBuffer ? Buffer.from(audio) : ArrayBuffer.isView(audio) ? Buffer.from(audio.buffer, audio.byteOffset, audio.byteLength) : null;
    if (!idValide(entretienId) || !LOCUTEURS.includes(locuteur) || !Number.isFinite(debut) || debut < 0 || !tampon || tampon.length === 0 || tampon.length > TAILLE_MAX_EXTRAIT) {
      throw new Error('Requête invalide.');
    }
    return envoyer('PUT', `/entretiens/${entretienId}/sous-titres?locuteur=${locuteur}&debut=${debut.toFixed(1)}`, tampon, 'application/octet-stream');
  });

  // Le fichier est déchiffré par le backend et écrit en flux : une heure d'entretien ne passe jamais entière en mémoire.
  ipcMain.handle('injara:exporter-enregistrement', async (event, entretienId) => {
    verifierOrigine(event);
    if (!idValide(entretienId)) throw new Error('Requête invalide.');
    const { canceled, filePath } = await dialog.showSaveDialog(fenetre(), {
      title: "Enregistrer l'entretien",
      defaultPath: path.join(app.getPath('videos'), `entretien-${entretienId}.webm`),
      filters: [{ name: 'Vidéo WebM', extensions: ['webm'] }],
    });
    if (canceled || !filePath) return { annule: true };
    return telecharger(`/entretiens/${entretienId}/enregistrement`, filePath);
  });

  function telecharger(chemin, destination) {
    const partiel = `${destination}.part`;
    const enTetes = { 'X-Injara-Token': backend.token };
    if (jetonSession) enTetes['X-Injara-Session'] = jetonSession;
    return new Promise((resolve) => {
      const echec = (message) => fs.rm(partiel, { force: true }).finally(() => resolve({ ok: false, message }));
      http
        .get({ host: '127.0.0.1', port: backend.port, path: chemin, headers: enTetes }, async (reponse) => {
          if (reponse.statusCode !== 200) {
            const morceaux = [];
            reponse.on('data', (m) => morceaux.push(m));
            reponse.on('end', () => {
              const { donnees } = interpreter(chemin, reponse.statusCode, Buffer.concat(morceaux).toString('utf8'));
              resolve({ ok: false, message: donnees?.detail || "L'enregistrement est indisponible." });
            });
            return;
          }
          try {
            await pipeline(reponse, fsFlux.createWriteStream(partiel, { mode: 0o600 }));
            await fs.rename(partiel, destination);
            resolve({ ok: true, chemin: destination });
          } catch (err) {
            echec(`L'enregistrement n'a pas pu être écrit : ${err.message}`);
          }
        })
        .on('error', () => echec("Le moteur INJARA ne répond plus. Redémarrez l'application."));
    });
  }

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

module.exports = { installerPontApi, viderCVOuverts };
