// Thème de l'interface : « sombre » (identité d'INJARA, par défaut), « clair » ou « systeme ».
// La préférence est propre à ce poste (localStorage) ; la fenêtre (fond, boutons natifs) suit le thème appliqué.
import { useEffect, useState } from 'react';

const CLE = 'injara-theme';
const CHOIX = ['sombre', 'clair', 'systeme'];
const requeteSombre = window.matchMedia('(prefers-color-scheme: dark)');

export function lireChoixTheme() {
  try {
    const valeur = localStorage.getItem(CLE);
    return CHOIX.includes(valeur) ? valeur : 'sombre';
  } catch {
    return 'sombre';
  }
}

const resoudre = (choix) => (choix === 'systeme' ? (requeteSombre.matches ? 'sombre' : 'clair') : choix);

/** Applique le thème au document et à la fenêtre (couleur de fond, boutons de la barre de titre). */
export function appliquerTheme(choix = lireChoixTheme()) {
  const theme = resoudre(choix);
  document.documentElement.dataset.theme = theme;
  window.injara?.fenetre?.theme(theme);
  return theme;
}

export function choisirTheme(choix) {
  try {
    localStorage.setItem(CLE, choix);
  } catch {
    // Stockage indisponible : le thème vaut pour cette session seulement.
  }
  appliquerTheme(choix);
  window.dispatchEvent(new Event('injara-theme'));
}

/** Suit le thème du système quand l'utilisateur a choisi « systeme ». */
requeteSombre.addEventListener('change', () => {
  if (lireChoixTheme() === 'systeme') {
    appliquerTheme('systeme');
    window.dispatchEvent(new Event('injara-theme'));
  }
});

export const LIBELLES_THEME = { sombre: 'Sombre', clair: 'Clair', systeme: 'Comme le système' };

/** Choix et thème appliqué, mis à jour à chaque changement. */
export function useTheme() {
  const [etat, setEtat] = useState(() => ({ choix: lireChoixTheme(), theme: document.documentElement.dataset.theme }));
  useEffect(() => {
    const maj = () => setEtat({ choix: lireChoixTheme(), theme: document.documentElement.dataset.theme });
    window.addEventListener('injara-theme', maj);
    return () => window.removeEventListener('injara-theme', maj);
  }, []);
  return etat;
}
