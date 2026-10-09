// Éléments d'affichage des candidatures traitées : statut, score, détail par critère.
import { Check, Info, X } from 'lucide-react';
import { m } from 'motion/react';
import { Badge, cx } from '../components/ui.jsx';
import { COURBE_SORTIE } from '../components/mouvement.js';

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

const TONS_STATUT = {
  a_traiter: 'info',
  classe: 'accent',
  a_verifier: 'alerte',
  non_classe: 'neutre',
  illisible: 'danger',
};

export function BadgeStatutCandidature({ candidature }) {
  const cle = candidature.statut_lecture === 'illisible' ? 'illisible' : candidature.statut_lecture === 'en_attente' ? 'a_traiter' : candidature.statut_classement;
  const libelle = cle === 'illisible' ? 'CV illisible' : STATUTS_CLASSEMENT[cle] || cle;
  return (
    <Badge ton={TONS_STATUT[cle]} point>
      {cle === 'a_traiter' && <span className="sr-only">L'IA analyse ce CV : </span>}
      {libelle}
    </Badge>
  );
}

/** Décision du recruteur. Elle ne change ni le score ni le classement ; un candidat écarté reste affiché. */
export const DECISIONS = {
  a_examiner: 'À examiner',
  retenu: 'Retenu',
  en_attente: 'En attente',
  ecarte: 'Écarté',
};

const TONS_DECISION = { a_examiner: 'neutre', retenu: 'accent', en_attente: 'alerte', ecarte: 'info' };

export function BadgeDecision({ decision }) {
  const cle = decision || 'a_examiner';
  return <Badge ton={TONS_DECISION[cle]}>{DECISIONS[cle]}</Badge>;
}

/** Indicateur de potentiel : affiché à côté du score, il ne le modifie jamais. */
const TONS_POTENTIEL = { Faible: 'neutre', Moyen: 'info', Élevé: 'accent', Exceptionnel: 'plein', 'Non évaluable': 'neutre' };

export const MENTION_POTENTIEL = 'Indicateur fondé sur des règles, à apprécier par le recruteur.';

export function BadgePotentiel({ niveau }) {
  if (!niveau) return null;
  return (
    <Badge ton={TONS_POTENTIEL[niveau] || 'neutre'} title={`Potentiel : ${niveau}. ${MENTION_POTENTIEL}`}>
      Potentiel {niveau.toLowerCase()}
    </Badge>
  );
}

// « Progression : passé de… » : le nom du signal est déjà affiché au-dessus.
const sansPrefixe = (phrase) => {
  const reste = phrase.replace(/^[^:]+ : /, '');
  return reste.charAt(0).toUpperCase() + reste.slice(1);
};

function NoteSignal({ note }) {
  if (note === null || note === undefined) return <span className="text-xs whitespace-nowrap text-tenu">non évaluable</span>;
  return (
    <span className="flex gap-1" aria-label={`${note} sur 2`} title={`${note} sur 2`}>
      {[0, 1].map((i) => (
        <span key={i} className={cx('h-1.5 w-4 rounded-full', i < note ? 'bg-accent' : 'bg-survol-fort')} />
      ))}
    </span>
  );
}

export function DetailPotentiel({ potentiel }) {
  return (
    <div className="flex flex-col gap-3">
      <ul className="flex flex-col gap-3">
        {potentiel.signaux.map((s) => (
          <li key={s.cle} className={s.evaluable ? '' : 'opacity-70'}>
            <div className="flex items-center justify-between gap-3">
              <span className="text-base font-medium text-fort">{s.nom}</span>
              <NoteSignal note={s.note} />
            </div>
            <p className="mt-0.5 text-sm text-doux">{sansPrefixe(s.phrase)}</p>
          </li>
        ))}
      </ul>
      {potentiel.recommandation && (
        <p className="rounded-md border border-accent-trait bg-accent-doux px-3 py-2 text-base text-texte">{potentiel.recommandation}</p>
      )}
    </div>
  );
}

/** Couleur d'un score : un indicateur, jamais un verdict. Vert au-delà de 70, sinon neutre. */
const tonScore = (score) => (score >= 70 ? 'fort' : score >= 40 ? 'moyen' : 'faible');
const COULEURS_ANNEAU = { fort: 'stroke-accent', moyen: 'stroke-[var(--info)]', faible: 'stroke-[var(--texte-tenu)]' };

const TAILLES_JAUGE = {
  petite: { cote: 36, trait: 3, texte: 'text-xs', texteCent: 'text-[10px]' },
  normale: { cote: 44, trait: 3.5, texte: 'text-sm', texteCent: 'text-xs' },
  grande: { cote: 88, trait: 5, texte: 'text-2xl', texteCent: 'text-xl' },
};

/**
 * Score sur 100, en jauge circulaire. `anime` : l'anneau se remplit à l'apparition (fiche, tableau de bord) ;
 * jamais dans les listes parcourues souvent.
 */
export function PastilleScore({ score, taille = 'normale', anime = false }) {
  const t = TAILLES_JAUGE[taille === 'grande' ? 'grande' : taille === 'petite' ? 'petite' : 'normale'];
  if (score === null || score === undefined) {
    return (
      <span className="inline-grid shrink-0 place-items-center text-sm text-tenu" style={{ width: t.cote, height: t.cote }} title="Pas de score">
        —
      </span>
    );
  }
  const r = (t.cote - t.trait) / 2;
  const fraction = Math.max(0, Math.min(1, score / 100));
  const ton = tonScore(score);
  const Cercle = anime ? m.circle : 'circle';
  return (
    <span
      className="relative inline-grid shrink-0 place-items-center"
      style={{ width: t.cote, height: t.cote }}
      role="img"
      aria-label={`Score ${Math.round(score)} sur 100`}
      title="Score sur 100 : un indicateur d'aide à la décision"
    >
      <svg viewBox={`0 0 ${t.cote} ${t.cote}`} className="absolute inset-0 -rotate-90" aria-hidden>
        <circle cx={t.cote / 2} cy={t.cote / 2} r={r} fill="none" strokeWidth={t.trait} className="stroke-[var(--survol-fort)]" />
        <Cercle
          cx={t.cote / 2}
          cy={t.cote / 2}
          r={r}
          fill="none"
          strokeWidth={t.trait}
          strokeLinecap="round"
          className={COULEURS_ANNEAU[ton]}
          {...(anime
            ? { initial: { pathLength: 0 }, animate: { pathLength: fraction }, transition: { duration: 0.9, ease: COURBE_SORTIE, delay: 0.15 } }
            : { pathLength: 1, strokeDasharray: `${fraction} 1` })}
        />
      </svg>
      <span className={cx('chiffre', Math.round(score) >= 100 ? t.texteCent : t.texte, ton === 'fort' ? 'text-fort' : 'text-texte')}>{Math.round(score)}</span>
    </span>
  );
}

export function BarreCritere({ nom, critere }) {
  const ignore = critere.score === null;
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3 text-base">
        <span className="font-medium text-fort">{CRITERES[nom]}</span>
        <span className="text-sm text-doux tabular-nums">
          {ignore ? 'non calculé' : <><span className="font-semibold text-texte">{Math.round(critere.score)} %</span> · poids {Math.round(critere.poids)}</>}
        </span>
      </div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-survol-fort">
        {!ignore && (
          <m.div
            className="h-full origin-left rounded-full bg-accent"
            style={{ width: `${critere.score}%` }}
            initial={{ transform: 'scaleX(0)' }}
            animate={{ transform: 'scaleX(1)' }}
            transition={{ duration: 0.5, ease: COURBE_SORTIE }}
          />
        )}
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
        <p className="flex items-start gap-2 rounded-md border border-trait bg-survol px-3 py-2 text-sm text-doux">
          <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          Adéquation globale non calculée (moteur d'analyse indisponible) : le score repose sur les trois autres critères, poids recalculés.
        </p>
      )}
      {Object.keys(CRITERES).map((nom) => (
        <div key={nom} className="flex flex-col gap-1.5">
          <BarreCritere nom={nom} critere={criteres[nom]} />
          {!compact && <p className="text-sm text-doux">{criteres[nom].detail.message}</p>}
          {nom === 'competences' && (competences.trouvees.length > 0 || competences.manquantes.length > 0) && (
            <ul className="flex flex-wrap gap-1.5" aria-label="Compétences">
              {competences.trouvees.map((t) => (
                <li
                  key={t.competence}
                  className="inline-flex items-center gap-1 rounded-sm border border-accent-trait bg-accent-doux px-1.5 py-0.5 text-xs font-medium text-accent-texte"
                  title={`Trouvée sous la forme « ${t.trouvee_sous} »`}
                >
                  <Check className="size-3" aria-hidden /> <span className="sr-only">Trouvée : </span>{t.competence}
                </li>
              ))}
              {competences.manquantes.map((mq) => (
                <li key={mq} className="inline-flex items-center gap-1 rounded-sm border border-trait px-1.5 py-0.5 text-xs text-doux">
                  <X className="size-3" aria-hidden /> <span className="sr-only">Absente : </span>{mq}
                </li>
              ))}
            </ul>
          )}
          {!compact && nom === 'formation' && criteres.formation.detail.ligne && (
            <p className="text-sm text-texte">Diplôme lu : « {criteres.formation.detail.ligne} »</p>
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
