// Phase de la salle, déduite uniquement de l'état réel (statut de l'entretien, salle, présence, connexion WebRTC, image reçue).

/** fermee | ouverture | attente | negociation | connecte | interrompue | terminee | annulee */
export function phaseSalle({ entretien, salle, imageRecue }) {
  if (entretien.statut === 'termine') return 'terminee';
  if (entretien.statut === 'annule') return 'annulee';
  if (salle.etat === 'ouverture') return 'ouverture';
  if (salle.etat !== 'ouverte') return 'fermee';
  if (!salle.candidatPresent) return 'attente';
  if (['failed', 'disconnected', 'closed'].includes(salle.etatConnexion)) return 'interrompue';
  if (salle.candidatConnecte && imageRecue) return 'connecte';
  return 'negociation';
}

/** Indicateur de connexion de la barre supérieure : [libellé, couleur du voyant]. */
export const INDICATEURS = {
  fermee: ['Salle fermée', 'bg-white/40'],
  ouverture: ['Ouverture…', 'bg-amber-400'],
  attente: ['En attente du candidat', 'bg-amber-400'],
  negociation: ['Connexion en cours', 'bg-amber-400'],
  connecte: ['Connexion établie', 'bg-brand-500'],
  interrompue: ['Connexion interrompue', 'bg-red-500'],
  terminee: ['Entretien terminé', 'bg-white/40'],
  annulee: ['Entretien annulé', 'bg-white/40'],
};

/** « 2026-10-09T10:00:00+00:00 » → secondes écoulées (le serveur donne de l'UTC ; sans fuseau, on le suppose). */
export function secondesDepuis(iso, maintenant = Date.now()) {
  if (!iso) return 0;
  const brut = /(Z|[+-]\d\d:?\d\d)$/.test(iso) ? iso : `${iso}Z`;
  return Math.max(0, Math.floor((maintenant - new Date(brut).getTime()) / 1000));
}

export function formaterDuree(secondes) {
  const h = Math.floor(secondes / 3600);
  const m = String(Math.floor((secondes % 3600) / 60)).padStart(2, '0');
  const s = String(secondes % 60).padStart(2, '0');
  return h > 0 ? `${h}:${m}:${s}` : `${m}:${s}`;
}

export const initiales = (nom) =>
  (nom || '?').split(/[\s@._-]+/).filter(Boolean).slice(0, 2).map((m) => m[0].toUpperCase()).join('') || '?';
