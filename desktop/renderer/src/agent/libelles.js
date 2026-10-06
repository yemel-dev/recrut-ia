// Libellés de l'agent mail (sans jargon technique : ni « IMAP » ni « OAuth » à l'écran).

export const FOURNISSEURS = {
  gmail_oauth: 'Gmail / Google Workspace',
  imap: 'Messagerie',
  fake: 'Boîte de démonstration',
};

export const REGLES_IGNORE = {
  automatic: 'Email automatique',
  sender: 'Expéditeur ignoré',
  extension: 'Type de fichier désactivé',
  size: 'Fichier trop lourd',
};

export const MODES_PERIODE = {
  last_days: 'Les N derniers jours',
  since_date: 'Depuis une date',
  new_only: 'Seulement les nouveaux emails',
  all: "Tout l'historique",
};

export const ISSUES_APERCU = {
  to_import: 'À importer',
  already_imported: 'Déjà importé',
  ignored: 'Ignoré',
};

/** Résumé d'une vérification (SyncResult) : « 3 nouveaux CV · 1 doublon · 2 ignorés ». */
export function resumeSynchro(r) {
  const n = r.new_cvs.length;
  const morceaux = [n === 0 ? 'Aucun nouveau CV' : `${n} nouveau${n > 1 ? 'x' : ''} CV`];
  if (r.duplicates_skipped) morceaux.push(`${r.duplicates_skipped} doublon${r.duplicates_skipped > 1 ? 's' : ''}`);
  if (r.ignored_count) morceaux.push(`${r.ignored_count} ignoré${r.ignored_count > 1 ? 's' : ''}`);
  if (r.errors.length) morceaux.push(`${r.errors.length} erreur${r.errors.length > 1 ? 's' : ''}`);
  return morceaux.join(' · ');
}
