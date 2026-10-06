/** « 2026-12-31 » → « 31 décembre 2026 ». */
export const formaterDate = (iso) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });

/** Exigence d'expérience lisible : « Débutant accepté », « 1 an », « 3 ans ». */
export const experience = (annees) => (annees === 0 ? 'Débutant accepté' : `${pluriel(annees, 'an')} d'expérience min.`);

export const pluriel = (n, mot) => `${n} ${mot}${n > 1 ? 's' : ''}`;

/** Date et heure ISO (UTC) → heure locale : « 6 oct. 2026, 10:24 ». */
export const formaterDateHeure = (iso) =>
  iso
    ? new Date(iso).toLocaleString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    : '—';

/** Taille de fichier lisible : « 245 Ko », « 1,2 Mo ». */
export const formaterTaille = (octets) =>
  octets < 1024 * 1024 ? `${Math.max(1, Math.round(octets / 1024))} Ko` : `${(octets / 1024 / 1024).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} Mo`;
