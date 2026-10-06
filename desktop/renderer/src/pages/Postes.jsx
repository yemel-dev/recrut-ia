import { Briefcase, CalendarClock, GraduationCap, MapPin, Pencil, Plus, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api.js';
import SuppressionPoste from '../components/SuppressionPoste.jsx';
import { Alerte, BadgeStatut, Bouton, Chargement, EnTetePage } from '../components/ui.jsx';
import { STATUTS, TYPES_CONTRAT } from '../constantes.js';
import { experience, formaterDate } from '../format.js';

const FILTRES = [['', 'Tous'], ['actif', 'Actifs'], ['brouillon', 'Brouillons'], ['cloture', 'Clôturés']];

export default function Postes() {
  const navigate = useNavigate();
  const [parametres, setParametres] = useSearchParams();
  const statut = STATUTS[parametres.get('statut')] ? parametres.get('statut') : '';
  const [postes, setPostes] = useState(null);
  const [total, setTotal] = useState(0);
  const [erreur, setErreur] = useState('');
  const [aSupprimer, setASupprimer] = useState(null);

  const charger = useCallback(async () => {
    try {
      const [liste, synthese] = await Promise.all([
        api.get(statut ? `/postes?statut=${statut}` : '/postes'),
        api.get('/tableau-de-bord'),
      ]);
      setPostes(liste);
      setTotal(synthese.postes.total);
    } catch (err) {
      setErreur(err.message);
    }
  }, [statut]);

  useEffect(() => {
    charger();
  }, [charger]);

  const boutonCreer = <Bouton icone={Plus} onClick={() => navigate('/postes/nouveau')}>Nouveau poste</Bouton>;

  if (erreur) return <Alerte>{erreur}</Alerte>;
  if (!postes) return <Chargement />;

  return (
    <>
      <EnTetePage
        titre="Postes"
        description="Les postes actifs serviront à classer les candidatures reçues."
        actions={total > 0 && boutonCreer}
      />

      {total === 0 ? (
        <EtatVide action={boutonCreer} />
      ) : (
        <>
          <div className="mb-4 flex gap-1 rounded-lg border border-line bg-white p-1" role="tablist" aria-label="Filtrer par statut">
            {FILTRES.map(([valeur, libelle]) => (
              <button
                key={valeur}
                type="button"
                role="tab"
                aria-selected={statut === valeur}
                onClick={() => setParametres(valeur ? { statut: valeur } : {})}
                className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  statut === valeur ? 'bg-navy-900 text-white' : 'text-muted hover:bg-navy-50 hover:text-navy-900'
                }`}
              >
                {libelle}
              </button>
            ))}
          </div>

          {postes.length === 0 ? (
            <p className="rounded-xl border border-dashed border-line bg-white px-6 py-12 text-center text-sm text-muted">
              Aucun poste {STATUTS[statut]?.toLowerCase()} pour le moment.
            </p>
          ) : (
            <ul className="flex flex-col gap-3">
              {postes.map((poste) => (
                <LignePoste key={poste.id} poste={poste} onSupprimer={() => setASupprimer(poste)} />
              ))}
            </ul>
          )}
        </>
      )}

      <SuppressionPoste
        poste={aSupprimer}
        onAnnuler={() => setASupprimer(null)}
        onSupprime={() => {
          setASupprimer(null);
          charger();
        }}
      />
    </>
  );
}

function LignePoste({ poste, onSupprimer }) {
  const navigate = useNavigate();
  const details = [
    poste.lieu && { icone: MapPin, texte: poste.lieu },
    poste.type_contrat && { icone: Briefcase, texte: TYPES_CONTRAT[poste.type_contrat] },
    { icone: GraduationCap, texte: `${poste.niveau_formation} · ${experience(poste.experience_min_annees)}` },
    poste.date_limite && { icone: CalendarClock, texte: `Jusqu'au ${formaterDate(poste.date_limite)}` },
  ].filter(Boolean);

  return (
    <li className="group flex items-center gap-4 rounded-xl border border-line bg-white p-5 transition-colors hover:border-navy-200">
      <Link to={`/postes/${poste.id}`} className="min-w-0 flex-1">
        <div className="flex items-center gap-3">
          <h2 className="truncate font-semibold text-navy-900 group-hover:text-brand-700">{poste.intitule}</h2>
          <BadgeStatut statut={poste.statut} />
          {poste.reference_interne && <span className="text-xs text-muted">{poste.reference_interne}</span>}
        </div>
        <p className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted">
          {details.map(({ icone: Icone, texte }) => (
            <span key={texte} className="inline-flex items-center gap-1.5">
              <Icone className="size-3.5" aria-hidden /> {texte}
            </span>
          ))}
        </p>
      </Link>
      <div className="flex shrink-0 gap-1">
        <Bouton variante="discret" icone={Pencil} onClick={() => navigate(`/postes/${poste.id}/modifier`)} aria-label={`Modifier ${poste.intitule}`} />
        <Bouton variante="discret" icone={Trash2} onClick={onSupprimer} aria-label={`Supprimer ${poste.intitule}`} className="hover:text-danger" />
      </div>
    </li>
  );
}

function EtatVide({ action }) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-dashed border-navy-100 bg-white px-8 py-16 text-center">
      <div className="relative mb-6">
        <span className="flex size-16 items-center justify-center rounded-2xl bg-brand-50 text-brand-700">
          <Briefcase className="size-8" aria-hidden />
        </span>
        <span className="absolute -right-2 -bottom-2 flex size-7 items-center justify-center rounded-full border-4 border-white bg-brand-600 text-white">
          <Plus className="size-3.5" aria-hidden />
        </span>
      </div>
      <h2 className="text-lg font-semibold text-navy-900">Aucun poste pour le moment</h2>
      <p className="mt-2 max-w-md text-sm text-muted">
        Décrivez les postes que vous cherchez à pourvoir : missions, compétences, expérience et formation attendues.
        INJARA s'appuiera sur les postes actifs pour classer les candidatures reçues.
      </p>
      <ol className="mt-6 mb-8 flex flex-col gap-2 text-left text-sm text-navy-800 sm:flex-row sm:gap-6">
        {['Créez le poste en brouillon', 'Complétez les exigences', 'Passez-le en actif'].map((etape, i) => (
          <li key={etape} className="flex items-center gap-2">
            <span className="flex size-6 items-center justify-center rounded-full bg-navy-50 text-xs font-semibold text-navy-700">{i + 1}</span>
            {etape}
          </li>
        ))}
      </ol>
      {action}
    </div>
  );
}
