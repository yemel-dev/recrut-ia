// Mouvement : valeurs communes aux animations Motion (mêmes courbes que les tokens CSS de styles/tokens.css).
// Règles (skill « animate ») : transform et opacity seulement, < 300 ms, rien sur les actions au clavier
// fréquentes, mouvement réduit respecté par <MotionConfig reducedMotion="user"> (main.jsx).

export const COURBE_SORTIE = [0.23, 1, 0.32, 1];
export const COURBE_DEPLACEMENT = [0.77, 0, 0.175, 1];
export const COURBE_TIROIR = [0.32, 0.72, 0, 1];

export const DUREE = { rapide: 0.15, normale: 0.22, lente: 0.3 };

/** Entrée d'un écran : léger fondu et montée de 6 px. Pas de sortie animée (la navigation doit rester vive). */
export const entreeEcran = {
  initial: { opacity: 0, transform: 'translateY(6px)' },
  animate: { opacity: 1, transform: 'translateY(0px)' },
  transition: { duration: DUREE.normale, ease: COURBE_SORTIE },
};

/** Modale : centrée, part de 96 %. */
export const modale = {
  initial: { opacity: 0, transform: 'scale(0.96)' },
  animate: { opacity: 1, transform: 'scale(1)' },
  exit: { opacity: 0, transform: 'scale(0.98)', transition: { duration: DUREE.rapide, ease: COURBE_SORTIE } },
  transition: { duration: DUREE.normale, ease: COURBE_SORTIE },
};

export const voile = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
  transition: { duration: DUREE.normale, ease: COURBE_SORTIE },
};

/** Tiroir latéral droit. */
export const tiroir = {
  initial: { transform: 'translateX(100%)' },
  animate: { transform: 'translateX(0%)' },
  exit: { transform: 'translateX(100%)', transition: { duration: DUREE.normale, ease: COURBE_SORTIE } },
  transition: { duration: DUREE.lente, ease: COURBE_TIROIR },
};

/** Menu ou bulle ancrés sur leur déclencheur (origine fournie par l'appelant). */
export const flottant = {
  initial: { opacity: 0, transform: 'scale(0.96)' },
  animate: { opacity: 1, transform: 'scale(1)' },
  exit: { opacity: 0, transform: 'scale(0.98)', transition: { duration: 0.1 } },
  transition: { duration: DUREE.rapide, ease: COURBE_SORTIE },
};

/** Liste qui apparaît en cascade (40 ms entre deux éléments, plafonnée pour ne jamais traîner). */
export const cascade = {
  parent: { animate: { transition: { staggerChildren: 0.04, delayChildren: 0.02 } } },
  enfant: {
    initial: { opacity: 0, transform: 'translateY(6px)' },
    animate: { opacity: 1, transform: 'translateY(0px)', transition: { duration: DUREE.normale, ease: COURBE_SORTIE } },
  },
};

/** Délai de cascade d'un élément d'index i (pour les tableaux, où les variantes parent/enfant ne s'appliquent pas). */
export const delaiCascade = (i) => Math.min(i, 12) * 0.03;
