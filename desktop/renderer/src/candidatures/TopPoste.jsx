// Les 10 meilleures candidatures d'un poste, avec le détail par critère et la décision du recruteur.
// Le filtre par décision montre toutes les candidatures du poste ayant cette décision, à leur rang d'origine.
import { ChevronDown, Gauge, ListOrdered } from 'lucide-react';
import { AnimatePresence, m } from 'motion/react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api.js';
import { COURBE_SORTIE } from '../components/mouvement.js';
import { Alerte, Carte, Segments, cx } from '../components/ui.jsx';
import { BadgeDecision, BadgePotentiel, CRITERES, DECISIONS, DetailScore, MODES_ASSIGNATION, PastilleScore, formaterExperience } from './elements.jsx';

export default function TopPoste({ posteId, actif }) {
  const [top, setTop] = useState(null);
  const [erreur, setErreur] = useState('');
  const [ouvert, setOuvert] = useState(null);
  const [decision, setDecision] = useState('');

  useEffect(() => {
    const filtre = decision ? `?decision=${decision}` : '';
    const charger = () => api.get(`/postes/${posteId}/classement${filtre}`).then(setTop, (err) => setErreur(err.message));
    charger();
    const minuteur = setInterval(charger, 10000);
    return () => clearInterval(minuteur);
  }, [posteId, decision]);

  if (!top) return erreur ? <Alerte>{erreur}</Alerte> : <div className="squelette h-64 rounded-lg" />;

  return (
    <Carte sansMarge>
      <div className="flex flex-wrap items-end justify-between gap-3 px-5 pt-5 pb-4">
        <div>
          <h2 className="titre-section flex items-center gap-2">
            <ListOrdered className="size-4 text-accent-texte" aria-hidden /> Meilleurs profils
          </h2>
          <p className="mt-0.5 text-sm text-doux">
            {top.total_rattachees} candidature{top.total_rattachees > 1 ? 's' : ''} rattachée{top.total_rattachees > 1 ? 's' : ''} à ce poste
            {top.total_rattachees > top.taille && ` · ${top.taille} premières affichées`}
          </p>
        </div>
        {top.total_rattachees > 0 && (
          <Segments
            libelle="Filtrer par décision"
            valeur={decision}
            onChange={setDecision}
            options={[
              { valeur: '', libelle: 'Classement' },
              ...Object.entries(DECISIONS).map(([cle, libelle]) => ({ valeur: cle, libelle, compteur: top.par_decision?.[cle] ?? 0 })),
            ]}
          />
        )}
      </div>

      {top.elements.length === 0 && decision ? (
        <p className="border-t border-trait px-5 py-8 text-center text-base text-doux">Aucune candidature « {DECISIONS[decision]} » pour ce poste.</p>
      ) : top.elements.length === 0 ? (
        <p className="border-t border-trait px-5 py-8 text-center text-base text-doux">
          {actif
            ? "Aucune candidature rattachée pour l'instant. Les CV reçus seront classés ici automatiquement."
            : 'Ce poste n’est pas actif : les nouvelles candidatures ne lui sont pas rattachées automatiquement.'}
        </p>
      ) : (
        <ol>
          {top.elements.map((c) => {
            const deplie = ouvert === c.id;
            return (
              <li key={c.id} className="border-t border-trait">
                <div className={cx('flex items-center gap-4 px-5 py-3 transition-colors', deplie && 'bg-survol')}>
                  <span
                    className={cx('w-6 text-center text-sm font-bold tabular-nums', c.rang <= 3 ? 'text-accent-texte' : 'text-tenu')}
                    title="Rang dans le classement du poste"
                  >
                    {c.rang}
                  </span>
                  <PastilleScore score={c.score} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        to={`/candidatures/${c.id}`}
                        state={{ retour: { chemin: `/postes/${posteId}`, libelle: 'Classement du poste' } }}
                        className="truncate text-base font-semibold text-fort hover:text-accent-texte hover:underline"
                      >
                        {c.nom || c.email || c.nom_fichier_cv}
                      </Link>
                      <BadgeDecision decision={c.decision} />
                      <BadgePotentiel niveau={c.potentiel_niveau} />
                    </div>
                    <p className="mt-0.5 text-sm text-doux">
                      {c.diplome_niveau || 'Diplôme non trouvé'} · {formaterExperience(c.experience_mois)} d'expérience · {MODES_ASSIGNATION[c.mode_assignation] || ''}
                    </p>
                  </div>
                  <div className="hidden w-64 grid-cols-2 gap-x-4 gap-y-1.5 lg:grid">
                    {Object.keys(CRITERES).map((nom) => (
                      <BarreCritereMini key={nom} nom={nom} critere={c.detail.criteres[nom]} />
                    ))}
                  </div>
                  <button
                    type="button"
                    onClick={() => setOuvert(deplie ? null : c.id)}
                    className="grid size-8 shrink-0 place-items-center rounded-md text-doux transition-colors hover:bg-survol-fort hover:text-fort"
                    aria-label={deplie ? 'Masquer le détail' : 'Voir le détail du score'}
                    aria-expanded={deplie}
                  >
                    <ChevronDown className={cx('size-4 transition-transform duration-200', deplie && 'rotate-180')} aria-hidden />
                  </button>
                </div>
                <AnimatePresence initial={false}>
                  {deplie && (
                    <m.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2, ease: COURBE_SORTIE }}
                      className="overflow-hidden bg-survol"
                    >
                      <div className="mx-5 mb-4 ml-[86px] rounded-md border border-accent-trait/60 bg-surface p-4">
                        <p className="etiquette mb-3 flex items-center gap-1.5"><Gauge className="size-3.5 text-accent-texte" aria-hidden /> Détail du score</p>
                        <DetailScore detail={c.detail} />
                      </div>
                    </m.div>
                  )}
                </AnimatePresence>
              </li>
            );
          })}
        </ol>
      )}
    </Carte>
  );
}

function BarreCritereMini({ nom, critere }) {
  return (
    <div className="text-[11px]" title={`${CRITERES[nom]} : ${critere.score === null ? 'non calculé' : `${Math.round(critere.score)} %`}`}>
      <div className="flex justify-between text-doux">
        <span className="truncate">{CRITERES[nom]}</span>
        <span className="tabular-nums">{critere.score === null ? '—' : Math.round(critere.score)}</span>
      </div>
      <div className="mt-0.5 h-1 overflow-hidden rounded-full bg-survol-fort">
        {critere.score !== null && <div className="h-full rounded-full bg-accent" style={{ width: `${critere.score}%` }} />}
      </div>
    </div>
  );
}
