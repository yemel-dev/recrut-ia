// Pont entre l'interface et le backend.
//
// L'interface n'appelle jamais le backend directement : elle passe par le processus principal (IPC),
// qui ajoute le jeton de lancement et le jeton de session. Aucun de ces deux secrets n'atteint l'interface.

const { ipcMain } = require('electron');

const METHODES = new Set(['GET', 'POST', 'PUT', 'DELETE']);
const CHEMIN_VALIDE = /^\/[a-z0-9\-/]*(\?[a-z0-9_=&\-]*)?$/i;

function installerPontApi({ backend, origineAutorisee }) {
  let jetonSession = null;

  ipcMain.handle('injara:requete', async (event, { methode, chemin, corps } = {}) => {
    if (!origineAutorisee(event.senderFrame?.url)) {
      throw new Error('Origine non autorisée.');
    }
    methode = String(methode || '').toUpperCase();
    if (!METHODES.has(methode) || typeof chemin !== 'string' || !CHEMIN_VALIDE.test(chemin) || chemin.includes('//')) {
      throw new Error('Requête invalide.');
    }

    const enTetes = { 'X-Injara-Token': backend.token };
    if (jetonSession) enTetes['X-Injara-Session'] = jetonSession;
    if (corps !== undefined) enTetes['Content-Type'] = 'application/json';

    let reponse;
    try {
      reponse = await fetch(backend.baseUrl + chemin, {
        method: methode,
        headers: enTetes,
        body: corps === undefined ? undefined : JSON.stringify(corps),
      });
    } catch {
      return { ok: false, statut: 0, donnees: { detail: 'Le moteur INJARA ne répond plus. Redémarrez l\'application.' } };
    }

    const texte = await reponse.text();
    let donnees = null;
    try {
      donnees = texte ? JSON.parse(texte) : null;
    } catch {
      donnees = { detail: texte };
    }

    // La session est gérée ici et jamais transmise à l'interface.
    if (reponse.ok && chemin === '/auth/connexion' && donnees?.jeton_session) {
      jetonSession = donnees.jeton_session;
      delete donnees.jeton_session;
    }
    const finDeSession = reponse.ok && (chemin === '/auth/deconnexion' || chemin === '/auth/recuperation');
    const sessionRefusee = reponse.status === 401 && chemin !== '/auth/connexion';
    if (finDeSession || sessionRefusee) jetonSession = null;

    return { ok: reponse.ok, statut: reponse.status, donnees };
  });
}

module.exports = { installerPontApi };
