// Éléments d'affichage des candidatures traitées : statut, score, détail par critère.
import { Check, Info, X } from 'lucide-react';

export const STATUTS_CLASSEMENT = {
  a_traiter: 'En cours de traitement',
  classe: 'Classée',
  a_verifier: 'À vérifier',
  non_classe: 'Non classée',
};

export const MODES_ASSIGNATION = {
  reference: 'Poste cité dans le mail',
  automatique: 'Classement automatique',
  manuel: 'Choix du recruteur',
};

export const CRITERES = {
  competences: 'Compétences',
  experience: 'Expérience',
  formation: 'Formation',
  adequation: 'Adéquation globale',
};

const COULEURS_STATUT = {
  a_traiter: 'bg-navy-50 text-navy-700 ring-navy-100',
  classe: 'bg-brand-50 text-brand-700 ring-brand-100',
  a_verifier: 'bg-amber-50 text-amber-800 ring-amber-200',
  non_classe: 'bg-white text-muted ring-line',
  illisible: 'bg-danger-50 text-danger ring-danger/20',
};

export function BadgeStatutCandidature({ candidature }) {
  const cle = candidature.statut_lecture === 'illisible' ? 'illisible' : candidature.statut_lecture === 'en_attente' ? 'a_traiter' : candidature.statut_classement;
  const libelle = cle === 'illisible' ? 'CV illisible' : STATUTS_CLASSEMENT[cle] || cle;
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap ring-1 ring-inset ${COULEURS_STATUT[cle]}`}>
      {libelle}
    </span>
  );
}

/** Score sur 100. Un indicateur : les couleurs restent neutres, aucune notion de rejet. */
export function PastilleScore({ score, taille = 'normale' }) {
  if (score === null || score === undefined) return <span className="text-sm text-muted">—</span>;
  const couleur = score >= 70 ? 'bg-brand-600 text-white' : score >= 40 ? 'bg-navy-700 text-white' : 'bg-navy-100 text-navy-800';
  const dimensions = taille === 'grande' ? 'size-16 text-xl' : 'size-10 text-sm';
  return (
    <span className={`inline-flex shrink-0 items-center justify-center rounded-full font-bold ${dimensions} ${couleur}`} title="Score sur 100">
      {Math.round(score)}
    </span>
  );
}

export function BarreCritere({ nom, critere }) {
  const ignore = critere.score === null;
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-medium text-navy-900">{CRITERES[nom]}</span>
        <span className="text-muted">
          {ignore ? 'non calculé' : `${Math.round(critere.score)} %`} · poids {Math.round(critere.poids)}
        </span>
      </div>
      <div className="mt-1 h-2 overflow-hidden rounded-full bg-navy-50">
        {!ignore && <div className="h-full rounded-full bg-brand-500" style={{ width: `${critere.score}%` }} />}
      </div>
    </div>
  );
}

/** Détail complet du calcul d'un score (fiche candidature, top 10). */
export function DetailScore({ detail, compact = false }) {
  const criteres = detail?.criteres;
  if (!criteres) return null;
  const competences = criteres.competences.detail;
  return (
    <div className="flex flex-col gap-4">
      {detail.adequation_ignoree && (
        <p className="flex items-start gap-2 rounded-lg bg-mist px-3 py-2 text-xs text-muted">
          <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          Adéquation globale non calculée (moteur d'analyse indisponible) : le score repose sur les trois autres critères, poids recalculés.
        </p>
      )}
      {Object.keys(CRITERES).map((nom) => (
        <div key={nom} className="flex flex-col gap-1.5">
          <BarreCritere nom={nom} critere={criteres[nom]} />
          {!compact && <p className="text-xs text-muted">{criteres[nom].detail.message}</p>}
          {nom === 'competences' && (competences.trouvees.length > 0 || competences.manquantes.length > 0) && (
            <ul className="flex flex-wrap gap-1.5">
              {competences.trouvees.map((t) => (
                <li key={t.competence} className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-2 py-0.5 text-xs text-brand-700" title={`Trouvée sous la forme « ${t.trouvee_sous} »`}>
                  <Check className="size-3" aria-hidden /> {t.competence}
                </li>
              ))}
              {competences.manquantes.map((m) => (
                <li key={m} className="inline-flex items-center gap-1 rounded-full bg-mist px-2 py-0.5 text-xs text-muted">
                  <X className="size-3" aria-hidden /> {m}
                </li>
              ))}
            </ul>
          )}
          {!compact && nom === 'formation' && criteres.formation.detail.ligne && (
            <p className="text-xs text-navy-700">Diplôme lu : « {criteres.formation.detail.ligne} »</p>
          )}
        </div>
      ))}
    </div>
  );
}

export const formaterExperience = (mois) => {
  if (mois === null || mois === undefined) return '—';
  if (mois < 12) return `${mois} mois`;
  const annees = Math.floor(mois / 12);
  const reste = mois % 12;
  return `${annees} an${annees > 1 ? 's' : ''}${reste ? ` ${reste} mois` : ''}`;
};
