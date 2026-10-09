// Commandes globales (palette Ctrl+K, raccourcis clavier) qui déclenchent une action d'un écran.
// L'écran s'abonne avec useCommande ; si la commande arrive avant qu'il soit affiché (ex. « Importer des CV »
// depuis le tableau de bord), elle attend et l'écran l'exécute dès son ouverture.
import { useEffect, useRef } from 'react';

const EVENEMENT = 'injara:commande';
const enAttente = new Set();

export function lancerCommande(nom) {
  const evenement = new CustomEvent(EVENEMENT, { detail: nom, cancelable: true });
  // dispatchEvent renvoie false si un écran a pris la commande (preventDefault)
  if (window.dispatchEvent(evenement)) enAttente.add(nom);
}

/** L'écran exécute `action` quand la commande `nom` est lancée, y compris juste avant son ouverture. */
export function useCommande(nom, action) {
  const ref = useRef(action);
  useEffect(() => {
    ref.current = action;
  });
  useEffect(() => {
    if (enAttente.delete(nom)) ref.current();
    const ecouter = (e) => {
      if (e.detail !== nom) return;
      e.preventDefault();
      ref.current();
    };
    window.addEventListener(EVENEMENT, ecouter);
    return () => window.removeEventListener(EVENEMENT, ecouter);
  }, [nom]);
}

/** Ctrl sur Windows et Linux, Cmd sur macOS. */
export const MAC = window.injara?.fenetre?.plateforme === 'darwin';
export const MODIFICATEUR = MAC ? '⌘' : 'Ctrl';
export const avecModificateur = (e) => (MAC ? e.metaKey : e.ctrlKey) && !e.altKey;

/** Vrai quand la frappe vise un champ de saisie (les raccourcis à une touche ne doivent pas s'y déclencher). */
export const dansUnChamp = (e) => {
  const cible = e.target;
  return cible instanceof HTMLElement && (cible.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(cible.tagName));
};

/** Recherche tolérante : sans accents, sans casse. */
export const normaliser = (texte) =>
  (texte || '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase();
