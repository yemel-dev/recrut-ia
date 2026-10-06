import { LONGUEUR_MIN_MOT_DE_PASSE } from './constantes.js';

export function verifierMotDePasse(motDePasse, confirmation) {
  const erreurs = {};
  if (motDePasse.length < LONGUEUR_MIN_MOT_DE_PASSE) {
    erreurs.mot_de_passe = `Le mot de passe doit contenir au moins ${LONGUEUR_MIN_MOT_DE_PASSE} caractères.`;
  } else if (!motDePasse.trim()) {
    erreurs.mot_de_passe = "Le mot de passe ne peut pas être composé uniquement d'espaces.";
  }
  if (confirmation !== motDePasse) erreurs.confirmation = 'Les deux mots de passe ne correspondent pas.';
  return erreurs;
}

export function aideMotDePasse(motDePasse) {
  const n = motDePasse.length;
  return n >= LONGUEUR_MIN_MOT_DE_PASSE
    ? `${n} caractères : longueur suffisante.`
    : `${LONGUEUR_MIN_MOT_DE_PASSE} caractères minimum (${n}/${LONGUEUR_MIN_MOT_DE_PASSE}). Une phrase de plusieurs mots est facile à retenir.`;
}
