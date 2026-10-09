// Barre latérale : navigation principale (Ctrl+1 à 6), compte et préférences. Repliable (Ctrl+B).
import { Briefcase, Building2, ChevronsUpDown, FileText, Keyboard, LayoutDashboard, LogOut, Mail, Monitor, Moon, PanelLeftClose, PanelLeftOpen, Send, Sun } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { MODIFICATEUR } from '../../commandes.js';
import { choisirTheme } from '../../theme.js';
import Infobulle from '../Infobulle.jsx';
import { MenuDeroulant } from '../Menu.jsx';
import { cx } from '../ui.jsx';

export const NAVIGATION = [
  { vers: '/', libelle: 'Tableau de bord', icone: LayoutDashboard, exact: true, geste: 'grandir' },
  { vers: '/candidatures', libelle: 'Candidatures', icone: FileText, compteur: true, geste: 'soulever' },
  { vers: '/postes', libelle: 'Postes', icone: Briefcase, geste: 'soulever' },
  { vers: '/boite-mail', libelle: 'Boîte mail', icone: Mail, geste: 'incliner' },
  { vers: '/entreprise', libelle: 'Profil entreprise', icone: Building2, geste: 'soulever' },
  { vers: '/parametres/mails', libelle: 'Mails aux candidats', icone: Send, geste: 'avancer' },
];

export default function BarreLaterale({ repliee, onReplier, totalCV, email, onDeconnecter, onRaccourcis, choixTheme }) {
  const Replier = repliee ? PanelLeftOpen : PanelLeftClose;
  return (
    <aside
      className={cx(
        'flex shrink-0 flex-col bg-chrome pb-2', // repli instantané : action au clavier, pas d'animation de largeur
        repliee ? 'w-[var(--largeur-barre-repliee)]' : 'w-[var(--largeur-barre)]',
      )}
      aria-label="Barre latérale"
    >
      <nav className="flex flex-1 flex-col gap-0.5 px-2 pt-2" aria-label="Navigation principale">
        {NAVIGATION.map(({ vers, libelle, icone: Icone, exact, compteur, geste }, i) => (
          <Infobulle key={vers} texte={`${libelle}  ·  ${MODIFICATEUR}+${i + 1}`} cote="droite" actif={repliee} className="flex">
            <NavLink
              to={vers}
              end={exact}
              aria-label={repliee ? libelle : undefined}
              className={({ isActive }) =>
                cx(
                  'geste-hote relative flex h-9 w-full items-center gap-3 rounded-md px-2.5 text-base font-medium transition-colors',
                  isActive ? 'bg-survol-fort text-fort' : 'text-doux hover:bg-survol hover:text-fort',
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && <span className="absolute top-2 bottom-2 -left-2 w-[3px] rounded-r-full bg-accent" aria-hidden />}
                  <Icone className={cx('size-[18px] shrink-0', isActive && 'text-accent-texte')} aria-hidden data-geste={geste} />
                  {!repliee && <span className="flex-1 truncate">{libelle}</span>}
                  {!repliee && compteur && totalCV > 0 && (
                    <span className="rounded-sm bg-survol-fort px-1.5 text-xs text-doux tabular-nums">{totalCV}</span>
                  )}
                  {repliee && compteur && totalCV > 0 && (
                    <span className="absolute top-1.5 right-2 size-1.5 rounded-full bg-accent" aria-hidden />
                  )}
                </>
              )}
            </NavLink>
          </Infobulle>
        ))}
      </nav>

      <div className="flex flex-col gap-0.5 px-2">
        <MenuDeroulant
          libelle="Compte et préférences"
          cote="haut"
          elements={[
            { libelle: 'Thème sombre', icone: Moon, action: () => choisirTheme('sombre'), raccourci: choixTheme === 'sombre' ? 'Actif' : undefined },
            { libelle: 'Thème clair', icone: Sun, action: () => choisirTheme('clair'), raccourci: choixTheme === 'clair' ? 'Actif' : undefined },
            { libelle: 'Comme le système', icone: Monitor, action: () => choisirTheme('systeme'), raccourci: choixTheme === 'systeme' ? 'Actif' : undefined },
            null,
            { libelle: 'Raccourcis clavier', icone: Keyboard, action: onRaccourcis, raccourci: '?' },
            null,
            { libelle: 'Se déconnecter', icone: LogOut, action: onDeconnecter, danger: true },
          ]}
          declencheur={(props) => (
            <Infobulle texte={email} cote="droite" actif={repliee} className="flex">
              <button
                type="button"
                {...props}
                aria-label={repliee ? `Compte : ${email}` : undefined}
                className="flex h-11 w-full items-center gap-2.5 rounded-md px-1.5 text-left transition-colors hover:bg-survol aria-expanded:bg-survol-fort"
              >
                <span className="grid size-7 shrink-0 place-items-center rounded-full bg-accent-doux font-affichage text-xs font-semibold text-accent-texte ring-1 ring-accent-trait">
                  {(email || '?').charAt(0).toUpperCase()}
                </span>
                {!repliee && (
                  <>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-fort">{email}</span>
                      <span className="block text-xs text-doux">Compte et préférences</span>
                    </span>
                    <ChevronsUpDown className="size-3.5 shrink-0 text-tenu" aria-hidden />
                  </>
                )}
              </button>
            </Infobulle>
          )}
        />
        <Infobulle texte={`Déplier  ·  ${MODIFICATEUR}+B`} cote="droite" actif={repliee} className="flex">
          <button
            type="button"
            onClick={onReplier}
            aria-label={repliee ? 'Déplier la barre latérale' : 'Replier la barre latérale'}
            aria-keyshortcuts="Control+B"
            className="geste-hote flex h-8 w-full items-center gap-3 rounded-md px-2.5 text-sm text-tenu transition-colors hover:bg-survol hover:text-doux"
          >
            <Replier className="size-4 shrink-0" aria-hidden data-geste={repliee ? 'avancer' : 'reculer'} />
            {!repliee && <span>Replier</span>}
          </button>
        </Infobulle>
      </div>
    </aside>
  );
}
