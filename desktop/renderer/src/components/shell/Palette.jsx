// Palette de commandes (Ctrl/Cmd+K) : aller à un écran, ouvrir un candidat ou un poste, lancer une action.
// Pas d'animation d'ouverture : elle sert des dizaines de fois par jour, au clavier (skill « animate »).
import { Briefcase, CornerDownLeft, FileUp, Keyboard, LogOut, Monitor, Moon, Plus, RefreshCw, Search, Sun, UserRound } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api.js';
import { MODIFICATEUR, lancerCommande, normaliser } from '../../commandes.js';
import { choisirTheme } from '../../theme.js';
import { BadgeStatut, cx } from '../ui.jsx';
import { NAVIGATION } from './BarreLaterale.jsx';

const MAX_PAR_GROUPE = 6;

export default function Palette({ ouverte, onFermer, onRaccourcis, onDeconnecter }) {
  const navigate = useNavigate();
  const [requete, setRequete] = useState('');
  const [actif, setActif] = useState(0);
  const [donnees, setDonnees] = useState({ candidatures: [], postes: [] });
  const champ = useRef(null);
  const liste = useRef(null);
  const focusPrecedent = useRef(null);

  // À chaque ouverture : on relit les candidatures et les postes (appels locaux) pour la recherche.
  useEffect(() => {
    if (!ouverte) return;
    focusPrecedent.current = document.activeElement;
    setRequete('');
    setActif(0);
    let actuel = true;
    Promise.all([api.get('/candidatures?limite=200').catch(() => null), api.get('/postes').catch(() => null)]).then(([c, p]) => {
      if (actuel) setDonnees({ candidatures: c?.elements || [], postes: p || [] });
    });
    requestAnimationFrame(() => champ.current?.focus());
    return () => {
      actuel = false;
    };
  }, [ouverte]);

  const fermer = () => {
    onFermer();
    focusPrecedent.current?.focus?.();
  };

  const groupes = useMemo(() => {
    const q = normaliser(requete.trim());
    const correspond = (...textes) => !q || textes.some((t) => normaliser(t).includes(q));
    const actions = [
      { id: 'nouveau-poste', libelle: 'Créer un poste', icone: Plus, raccourci: `${MODIFICATEUR} N`, faire: () => navigate('/postes/nouveau') },
      { id: 'importer', libelle: 'Importer des CV', icone: FileUp, raccourci: `${MODIFICATEUR} I`, faire: () => { navigate('/candidatures'); lancerCommande('importer-cv'); } },
      { id: 'verifier', libelle: 'Vérifier la boîte mail maintenant', icone: RefreshCw, faire: () => { navigate('/candidatures'); lancerCommande('verifier-boite'); } },
      { id: 'theme-sombre', libelle: 'Thème sombre', icone: Moon, faire: () => choisirTheme('sombre') },
      { id: 'theme-clair', libelle: 'Thème clair', icone: Sun, faire: () => choisirTheme('clair') },
      { id: 'theme-systeme', libelle: 'Thème comme le système', icone: Monitor, faire: () => choisirTheme('systeme') },
      { id: 'raccourcis', libelle: 'Raccourcis clavier', icone: Keyboard, raccourci: '?', faire: onRaccourcis },
      { id: 'deconnexion', libelle: 'Se déconnecter', icone: LogOut, faire: onDeconnecter },
    ].filter((a) => correspond(a.libelle));
    const ecrans = NAVIGATION.map((n, i) => ({
      id: `ecran-${n.vers}`,
      libelle: n.libelle,
      icone: n.icone,
      raccourci: `${MODIFICATEUR} ${i + 1}`,
      faire: () => navigate(n.vers),
    })).filter((e) => correspond(e.libelle));
    const candidats = q
      ? donnees.candidatures
          .filter((c) => correspond(c.nom, c.email, c.nom_fichier_cv, c.poste_intitule))
          .slice(0, MAX_PAR_GROUPE)
          .map((c) => ({
            id: `candidat-${c.id}`,
            libelle: c.nom || c.email || c.nom_fichier_cv,
            detail: [c.poste_intitule, c.score != null ? `${Math.round(c.score)}/100` : null].filter(Boolean).join(' · '),
            icone: UserRound,
            faire: () => navigate(`/candidatures/${c.id}`),
          }))
      : [];
    const postes = q
      ? donnees.postes
          .filter((p) => correspond(p.intitule, p.reference_interne, p.lieu))
          .slice(0, MAX_PAR_GROUPE)
          .map((p) => ({ id: `poste-${p.id}`, libelle: p.intitule, statut: p.statut, icone: Briefcase, faire: () => navigate(`/postes/${p.id}`) }))
      : [];
    return [
      { titre: 'Candidats', elements: candidats },
      { titre: 'Postes', elements: postes },
      { titre: 'Actions', elements: actions },
      { titre: 'Aller à', elements: ecrans },
    ].filter((g) => g.elements.length);
  }, [requete, donnees, navigate, onRaccourcis, onDeconnecter]);

  const plats = groupes.flatMap((g) => g.elements);
  const courant = Math.min(actif, Math.max(0, plats.length - 1));

  useEffect(() => {
    liste.current?.querySelector(`[data-index="${courant}"]`)?.scrollIntoView({ block: 'nearest' });
  }, [courant]);

  const executer = (element) => {
    onFermer();
    element.faire();
  };

  const auClavier = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActif((courant + 1) % Math.max(1, plats.length));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActif((courant - 1 + plats.length) % Math.max(1, plats.length));
    } else if (e.key === 'Enter' && plats[courant]) {
      e.preventDefault();
      executer(plats[courant]);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      fermer();
    }
  };

  if (!ouverte) return null;
  let index = -1;
  return createPortal(
    <div className="fixed inset-0 z-[90] flex justify-center bg-voile pt-[12vh]" onPointerDown={(e) => e.target === e.currentTarget && fermer()}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Palette de commandes"
        onKeyDown={auClavier}
        className="flex h-fit max-h-[min(560px,72vh)] w-full max-w-xl flex-col overflow-hidden rounded-xl border border-trait-fort bg-surface-2 shadow-flottante"
      >
        <div className="flex items-center gap-3 border-b border-trait px-4">
          <Search className="size-4 shrink-0 text-doux" aria-hidden />
          <input
            ref={champ}
            value={requete}
            onChange={(e) => {
              setRequete(e.target.value);
              setActif(0);
            }}
            placeholder="Rechercher un candidat, un poste, une action…"
            aria-label="Rechercher"
            role="combobox"
            aria-expanded="true"
            aria-controls="palette-liste"
            aria-activedescendant={plats[courant] ? `palette-${plats[courant].id}` : undefined}
            spellCheck={false}
            autoComplete="off"
            className="h-12 flex-1 bg-transparent text-lg text-fort outline-none placeholder:text-tenu focus-visible:outline-none"
          />
        </div>
        <ul id="palette-liste" ref={liste} role="listbox" aria-label="Résultats" className="min-h-0 flex-1 overflow-y-auto p-1.5">
          {plats.length === 0 && <li className="px-3 py-8 text-center text-base text-doux">Aucun résultat pour « {requete} ».</li>}
          {groupes.map((g) => (
            <li key={g.titre} role="presentation">
              <p className="px-2.5 pt-2.5 pb-1 text-xs font-medium text-tenu">{g.titre}</p>
              <ul role="presentation">
                {g.elements.map((el) => {
                  index += 1;
                  const i = index;
                  const choisi = i === courant;
                  return (
                    <li
                      key={el.id}
                      id={`palette-${el.id}`}
                      role="option"
                      aria-selected={choisi}
                      data-index={i}
                      onPointerMove={() => actif !== i && setActif(i)}
                      onClick={() => executer(el)}
                      className={cx('flex h-10 items-center gap-3 rounded-md px-2.5 text-base', choisi ? 'bg-survol-fort text-fort' : 'text-texte')}
                    >
                      <el.icone className={cx('size-4 shrink-0', choisi ? 'text-accent-texte' : 'text-doux')} aria-hidden />
                      <span className="min-w-0 flex-1 truncate">
                        {el.libelle}
                        {el.detail && <span className="ml-2 text-sm text-doux">{el.detail}</span>}
                      </span>
                      {el.statut && <BadgeStatut statut={el.statut} />}
                      {el.raccourci && <span className="text-xs text-tenu">{el.raccourci}</span>}
                      {choisi && <CornerDownLeft className="size-3.5 text-doux" aria-hidden />}
                    </li>
                  );
                })}
              </ul>
            </li>
          ))}
        </ul>
        <p className="flex items-center gap-4 border-t border-trait px-4 py-2 text-xs text-tenu">
          <span>↑ ↓ pour choisir</span>
          <span>Entrée pour ouvrir</span>
          <span>Échap pour fermer</span>
        </p>
      </div>
    </div>,
    document.body,
  );
}
