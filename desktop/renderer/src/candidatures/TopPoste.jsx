// Les 10 meilleures candidatures d'un poste, avec le détail par critère et la décision du recruteur.
// Le filtre par décision montre toutes les candidatures du poste ayant cette décision, à leur rang d'origine.
import { ChevronDown, ChevronUp, Trophy } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api.js';
import { Alerte, Carte, Chargement } from '../components/ui.jsx';
import { BadgeDecision, CRITERES, DECISIONS, DetailScore, MODES_ASSIGNATION, PastilleScore, formaterExperience } from './elements.jsx';

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

  if (!top) return <Carte>{erreur ? <Alerte>{erreur}</Alerte> : <Chargement />}</Carte>;

  return (
    <Carte>
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="flex items-center gap-2 font-semibold text-navy-900">
          <Trophy className="size-4 text-brand-700" aria-hidden /> Meilleurs profils
        </h2>
        <p className="text-sm text-muted">
          {top.total_rattachees} candidature{top.total_rattachees > 1 ? 's' : ''} rattachée{top.total_rattachees > 1 ? 's' : ''} à ce poste
          {top.total_rattachees > top.taille && ` · ${top.taille} premières affichées`}
        </p>
      </div>

      {top.total_rattachees > 0 && (
        <div className="mb-4 flex flex-wrap items-center gap-2" role="group" aria-label="Filtrer par décision">
          {[['', 'Meilleurs profils'], ...Object.entries(DECISIONS)].map(([cle, libelle]) => (
            <button
              key={cle || 'tous'}
              type="button"
              aria-pressed={decision === cle}
              onClick={() => setDecision(cle)}
              className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                decision === cle ? 'border-navy-900 bg-navy-900 text-white' : 'border-line bg-white text-navy-800 hover:border-navy-200'
              }`}
            >
              {libelle}
              {cle && <span className={decision === cle ? 'text-white/80' : 'text-muted'}>{top.par_decision?.[cle] ?? 0}</span>}
            </button>
          ))}
        </div>
      )}

      {top.elements.length === 0 && decision ? (
        <p className="rounded-lg bg-mist px-4 py-6 text-center text-sm text-muted">Aucune candidature « {DECISIONS[decision]} » pour ce poste.</p>
      ) : top.elements.length === 0 ? (
        <p className="rounded-lg bg-mist px-4 py-6 text-center text-sm text-muted">
          {actif
            ? "Aucune candidature rattachée pour l'instant. Les CV reçus seront classés ici automatiquement."
            : 'Ce poste n’est pas actif : les nouvelles candidatures ne lui sont pas rattachées automatiquement.'}
        </p>
      ) : (
        <ol className="flex flex-col divide-y divide-line">
          {top.elements.map((c) => (
            <li key={c.id} className="py-3">
              <div className="flex items-center gap-4">
                <span className="w-6 text-center text-sm font-semibold text-muted" title="Rang dans le classement du poste">{c.rang}</span>
                <PastilleScore score={c.score} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link
                      to={`/candidatures/${c.id}`}
                      state={{ retour: { chemin: `/postes/${posteId}`, libelle: 'Classement du poste' } }}
                      className="truncate font-medium text-navy-900 hover:text-brand-700"
                    >
                      {c.nom || c.email || c.nom_fichier_cv}
                    </Link>
                    <BadgeDecision decision={c.decision} />
                  </div>
                  <p className="text-xs text-muted">
                    {c.diplome_niveau || 'Diplôme non trouvé'} · {formaterExperience(c.experience_mois)} d'expérience · {MODES_ASSIGNATION[c.mode_assignation] || ''}
                  </p>
                </div>
                <div className="hidden w-64 grid-cols-2 gap-x-4 gap-y-1 md:grid">
                  {Object.keys(CRITERES).map((nom) => (
                    <div key={nom} className="text-[11px]">
                      <BarreCritereMini nom={nom} critere={c.detail.criteres[nom]} />
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => setOuvert(ouvert === c.id ? null : c.id)}
                  className="rounded-lg p-1.5 text-muted hover:bg-navy-50 hover:text-navy-900"
                  aria-label={ouvert === c.id ? 'Masquer le détail' : 'Voir le détail du score'}
                  aria-expanded={ouvert === c.id}
                >
                  {ouvert === c.id ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
                </button>
              </div>
              {ouvert === c.id && (
                <div className="mt-3 ml-10 rounded-lg bg-mist p-4">
                  <DetailScore detail={c.detail} />
                </div>
              )}
            </li>
          ))}
        </ol>
      )}
    </Carte>
  );
}

function BarreCritereMini({ nom, critere }) {
  return (
    <div title={`${CRITERES[nom]} : ${critere.score === null ? 'non calculé' : `${Math.round(critere.score)} %`}`}>
      <div className="flex justify-between text-muted">
        <span>{CRITERES[nom]}</span>
        <span>{critere.score === null ? '—' : Math.round(critere.score)}</span>
      </div>
      <div className="mt-0.5 h-1 overflow-hidden rounded-full bg-navy-50">
        {critere.score !== null && <div className="h-full rounded-full bg-brand-500" style={{ width: `${critere.score}%` }} />}
      </div>
    </div>
  );
}

