/** « 2026-12-31 » → « 31 décembre 2026 ». */
export const formaterDate = (iso) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });

/** Exigence d'expérience lisible : « Débutant accepté », « 1 an », « 3 ans ». */
export const experience = (annees) => (annees === 0 ? 'Débutant accepté' : `${pluriel(annees, 'an')} d'expérience min.`);

export const pluriel = (n, mot) => `${n} ${mot}${n > 1 ? 's' : ''}`;
