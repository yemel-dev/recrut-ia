import { Briefcase, Building2, LayoutDashboard, LogOut } from 'lucide-react';
import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useSession } from '../session.jsx';

const NAVIGATION = [
  { vers: '/', libelle: 'Tableau de bord', icone: LayoutDashboard, exact: true },
  { vers: '/postes', libelle: 'Postes', icone: Briefcase },
  { vers: '/entreprise', libelle: 'Profil entreprise', icone: Building2 },
];

/** Mise en page des écrans connectés : barre latérale + contenu. */
export default function Disposition() {
  const { email, deconnecter } = useSession();
  const [sortie, setSortie] = useState(false);

  return (
    <div className="flex h-full">
      <aside className="flex w-64 shrink-0 flex-col bg-navy-900 text-navy-100">
        <div className="flex items-center gap-2.5 px-6 py-6">
          <img src="./symbol-green.webp" alt="" className="size-8" />
          <span className="text-lg font-bold tracking-wide text-white">INJARA</span>
        </div>
        <nav className="flex flex-1 flex-col gap-1 px-3" aria-label="Navigation principale">
          {NAVIGATION.map(({ vers, libelle, icone: Icone, exact }) => (
            <NavLink
              key={vers}
              to={vers}
              end={exact}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                  isActive ? 'bg-navy-800 text-white' : 'hover:bg-navy-800/60 hover:text-white'
                }`
              }
            >
              <Icone className="size-4" aria-hidden />
              {libelle}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-navy-800 p-3">
          <p className="truncate px-3 pb-2 text-xs text-navy-200" title={email}>{email}</p>
          <button
            type="button"
            disabled={sortie}
            onClick={async () => {
              setSortie(true);
              await deconnecter();
            }}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium hover:bg-navy-800/60 hover:text-white"
          >
            <LogOut className="size-4" aria-hidden />
            Se déconnecter
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-5xl px-8 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
