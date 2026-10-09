import { Briefcase, CalendarClock, Ellipsis, Eye, GraduationCap, MapPin, Pencil, Plus, SearchX, Trash2 } from 'lucide-react';
import { m } from 'motion/react';
import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../api.js';
import SuppressionPoste from '../components/SuppressionPoste.jsx';
import EtatVide from '../components/EtatVide.jsx';
import { MenuDeroulant, useMenuContextuel } from '../components/Menu.jsx';
import { cascade } from '../components/mouvement.js';
import { Alerte, BadgeStatut, Bouton, EnTetePage, Segments } from '../components/ui.jsx';
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

  const boutonCreer = (
    <Bouton icone={Plus} geste="pivoter" onClick={() => navigate('/postes/nouveau')} aria-keyshortcuts="Control+N">
      Nouveau poste
    </Bouton>
  );
  const { ouvrir: ouvrirMenu, menu } = useMenuContextuel('Actions sur le poste');
  const actions = (poste) => [
    { libelle: 'Voir le poste et son classement', icone: Eye, action: () => navigate(`/postes/${poste.id}`) },
    { libelle: 'Modifier', icone: Pencil, action: () => navigate(`/postes/${poste.id}/modifier`) },
    null,
    { libelle: 'Supprimer…', icone: Trash2, action: () => setASupprimer(poste), danger: true },
  ];

  if (erreur) return <Alerte>{erreur}</Alerte>;
  if (!postes) return <SqueletteListe />;

  return (
    <>
      <EnTetePage
        titre="Postes"
        description="Les postes actifs servent à classer les candidatures reçues."
        actions={total > 0 && boutonCreer}
      />

      {total === 0 ? (
        <EtatVidePostes action={boutonCreer} />
      ) : (
        <>
          <Segments
            libelle="Filtrer par statut"
            className="mb-4"
            valeur={statut}
            onChange={(valeur) => setParametres(valeur ? { statut: valeur } : {})}
            options={FILTRES.map(([valeur, libelle]) => ({ valeur, libelle }))}
          />

          {postes.length === 0 ? (
            <EtatVide icone={SearchX} titre={`Aucun poste ${STATUTS[statut]?.toLowerCase()} pour le moment`} compact>
              Choisissez un autre filtre pour voir les autres postes.
            </EtatVide>
          ) : (
            <m.ul key={statut} className="overflow-hidden rounded-lg border border-trait bg-surface shadow-carte" initial="initial" animate="animate" variants={cascade.parent}>
              {postes.map((poste) => (
                <LignePoste key={poste.id} poste={poste} actions={actions(poste)} onMenu={(e) => ouvrirMenu(e, actions(poste))} />
              ))}
            </m.ul>
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
      {menu}
    </>
  );
}

function LignePoste({ poste, actions, onMenu }) {
  const details = [
    poste.lieu && { icone: MapPin, texte: poste.lieu },
    poste.type_contrat && { icone: Briefcase, texte: TYPES_CONTRAT[poste.type_contrat] },
    { icone: GraduationCap, texte: `${poste.niveau_formation} · ${experience(poste.experience_min_annees)}` },
    poste.date_limite && { icone: CalendarClock, texte: `Jusqu'au ${formaterDate(poste.date_limite)}` },
  ].filter(Boolean);

  return (
    <m.li variants={cascade.enfant} onContextMenu={onMenu} className="group relative flex items-center gap-4 border-b border-trait px-5 py-4 transition-colors last:border-b-0 hover:bg-survol">
      <span className={`grid size-9 shrink-0 place-items-center rounded-md border ${poste.statut === 'actif' ? 'border-accent-trait bg-accent-doux text-accent-texte' : 'border-trait bg-survol text-doux'}`}>
        <Briefcase className="size-4" aria-hidden />
      </span>
      <Link to={`/postes/${poste.id}`} className="min-w-0 flex-1 after:absolute after:inset-0 focus-visible:outline-none focus-visible:after:rounded-md focus-visible:after:ring-2 focus-visible:after:ring-accent">
        <div className="flex items-center gap-3">
          <h2 className="truncate text-lg font-semibold text-fort">{poste.intitule}</h2>
          <BadgeStatut statut={poste.statut} />
          {poste.reference_interne && <span className="text-sm text-tenu tabular-nums">{poste.reference_interne}</span>}
        </div>
        <p className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm text-doux">
          {details.map(({ icone: Icone, texte }) => (
            <span key={texte} className="inline-flex items-center gap-1.5">
              <Icone className="size-3.5" aria-hidden /> {texte}
            </span>
          ))}
        </p>
      </Link>
      <div className="relative z-10 flex shrink-0 gap-1 opacity-70 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
        <MenuDeroulant
          libelle={`Actions sur ${poste.intitule}`}
          alignement="fin"
          elements={actions}
          declencheur={(props) => <Bouton variante="discret" icone={Ellipsis} aria-label={`Actions sur ${poste.intitule}`} {...props} />}
        />
      </div>
    </m.li>
  );
}

function EtatVidePostes({ action }) {
  return (
    <EtatVide icone={Briefcase} titre="Aucun poste pour le moment" action={action}>
      <p>
        Décrivez les postes que vous cherchez à pourvoir : missions, compétences, expérience et formation attendues.
        INJARA s'appuiera sur les postes actifs pour classer les candidatures reçues.
      </p>
      <ol className="mt-6 flex flex-col gap-3 text-left text-base text-texte sm:flex-row sm:gap-6">
        {['Créez le poste en brouillon', 'Complétez les exigences', 'Passez-le en actif'].map((etape, i) => (
          <li key={etape} className="flex items-center gap-2">
            <span className="grid size-6 place-items-center rounded-full border border-accent-trait text-xs font-bold text-accent-texte">{i + 1}</span>
            {etape}
          </li>
        ))}
      </ol>
    </EtatVide>
  );
}

function SqueletteListe() {
  return (
    <div aria-busy="true" aria-label="Chargement des postes">
      <div className="squelette mb-3 h-8 w-40" />
      <div className="squelette mb-7 h-4 w-96" />
      <div className="squelette mb-4 h-8 w-80 rounded-md" />
      <div className="overflow-hidden rounded-lg border border-trait">
        {[0, 1, 2].map((i) => (
          <div key={i} className="flex items-center gap-4 border-b border-trait px-5 py-4 last:border-b-0">
            <div className="squelette size-9 rounded-md" />
            <div className="flex-1"><div className="squelette mb-2 h-4 w-64" /><div className="squelette h-3 w-96" /></div>
          </div>
        ))}
      </div>
    </div>
  );
}
