import { Briefcase, Building2, CheckCircle2, CircleAlert, FileText, Info, LayoutDashboard, LogOut, Mail, X } from 'lucide-react';
import { useState } from 'react';
import { Link, NavLink, Outlet, useMatch } from 'react-router-dom';
import { FournisseurAgent, useAgent } from '../agent/ContexteAgent.jsx';
import { useSession } from '../session.jsx';

const NAVIGATION = [
  { vers: '/', libelle: 'Tableau de bord', icone: LayoutDashboard, exact: true },
  { vers: '/candidatures', libelle: 'Candidatures', icone: FileText, compteur: true },
  { vers: '/postes', libelle: 'Postes', icone: Briefcase },
  { vers: '/boite-mail', libelle: 'Boîte mail', icone: Mail },
  { vers: '/entreprise', libelle: 'Profil entreprise', icone: Building2 },
];

/** Mise en page des écrans connectés : barre latérale + contenu. */
export default function Disposition() {
  return (
    <FournisseurAgent>
      <Cadre />
    </FournisseurAgent>
  );
}

function Cadre() {
  const { email, deconnecter } = useSession();
  const { statut, reconnexionConseillee, oublierErreursSync } = useAgent();
  const [sortie, setSortie] = useState(false);
  const salle = useMatch('/entretiens/:id'); // la salle d'entretien occupe toute la zone de contenu

  return (
    <div className="flex h-full">
      <aside className={`${salle ? 'hidden xl:flex' : 'flex'} w-64 shrink-0 flex-col bg-navy-900 text-navy-100`}>
        <div className="flex items-center gap-2.5 px-6 py-6">
          <img src="./symbol-green.webp" alt="" className="size-8" />
          <span className="text-lg font-bold tracking-wide text-white">INJARA</span>
        </div>
        <nav className="flex flex-1 flex-col gap-1 px-3" aria-label="Navigation principale">
          {NAVIGATION.map(({ vers, libelle, icone: Icone, exact, compteur }) => (
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
              <span className="flex-1">{libelle}</span>
              {compteur && statut?.total_cvs > 0 && (
                <span className="rounded-full bg-navy-700 px-2 py-0.5 text-xs text-navy-100">{statut.total_cvs}</span>
              )}
            </NavLink>
          ))}
        </nav>
        {statut && (
          <div className="mx-3 mb-3 rounded-lg bg-navy-800/60 px-3 py-2.5 text-xs">
            <p className="flex items-center gap-2 font-medium text-white">
              <span
                className={`size-2 rounded-full ${statut.connected ? (statut.watching ? 'bg-brand-500' : 'bg-amber-400') : 'bg-navy-200'}`}
                aria-hidden
              />
              {statut.connected ? (statut.watching ? 'Surveillance active' : 'Surveillance en pause') : 'Aucune boîte mail liée'}
            </p>
            {statut.connected && statut.account_email && <p className="mt-0.5 truncate text-navy-200">{statut.account_email}</p>}
          </div>
        )}
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
      <main className="flex flex-1 flex-col overflow-y-auto">
        {statut?.mode === 'fake' && (
          <div className="bg-amber-100 px-8 py-2 text-center text-sm font-semibold text-amber-900">
            MODE DÉMO : la boîte mail est simulée, les candidatures sont des exemples.
          </div>
        )}
        {reconnexionConseillee && statut?.connected && (
          <div role="alert" className="flex items-center justify-center gap-3 bg-danger-50 px-8 py-2 text-sm text-danger">
            <CircleAlert className="size-4" aria-hidden />
            Les dernières vérifications de la boîte mail ont échoué. Le mot de passe ou l'autorisation a peut-être changé.
            <Link to="/boite-mail" onClick={oublierErreursSync} className="font-semibold underline">Reconnecter le compte</Link>
          </div>
        )}
        <div className={salle ? 'flex min-h-[34rem] w-full flex-1 flex-col' : 'mx-auto w-full max-w-5xl px-8 py-8'}>
          <Outlet />
        </div>
      </main>
      <Notifications />
    </div>
  );
}

const ICONES = { succes: CheckCircle2, erreur: CircleAlert, info: Info };
const COULEURS = {
  succes: 'border-brand-100 text-brand-700',
  erreur: 'border-danger/20 text-danger',
  info: 'border-line text-navy-800',
};

function Notifications() {
  const { notifications, fermerNotification } = useAgent();
  return (
    <div className="pointer-events-none fixed right-6 bottom-6 z-50 flex w-80 flex-col gap-2" aria-live="polite">
      {notifications.map(({ id, message, type }) => {
        const Icone = ICONES[type] || Info;
        return (
          <div key={id} className={`pointer-events-auto flex items-start gap-3 rounded-xl border bg-white p-4 shadow-lg ${COULEURS[type]}`}>
            <Icone className="mt-0.5 size-4 shrink-0" aria-hidden />
            <p className="flex-1 text-sm font-medium">{message}</p>
            <button type="button" onClick={() => fermerNotification(id)} className="text-muted hover:text-navy-900" aria-label="Fermer">
              <X className="size-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
