// Appels au backend via le pont exposé par le preload (window.injara).

export class ErreurApi extends Error {
  constructor(statut, donnees) {
    super(donnees?.detail || 'Une erreur inattendue est survenue.');
    this.statut = statut;
    this.champs = donnees?.champs || {};
  }
}

export const EVENEMENT_SESSION_EXPIREE = 'injara:session-expiree';

async function appeler(methode, chemin, corps) {
  const reponse = await window.injara.api[methode](chemin, corps);
  if (!reponse.ok) {
    if (reponse.statut === 401 && reponse.donnees?.code === 'session_requise') {
      window.dispatchEvent(new Event(EVENEMENT_SESSION_EXPIREE));
    }
    throw new ErreurApi(reponse.statut, reponse.donnees);
  }
  return reponse.donnees;
}

export const api = {
  get: (chemin) => appeler('get', chemin),
  post: (chemin, corps = {}) => appeler('post', chemin, corps),
  put: (chemin, corps = {}) => appeler('put', chemin, corps),
  delete: (chemin) => appeler('delete', chemin),
};
