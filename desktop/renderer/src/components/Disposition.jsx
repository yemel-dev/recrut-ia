// Cadre de l'application connectée : barre de titre, barre latérale, zone de contenu (seule à défiler), barre d'état.
// Raccourcis clavier globaux et palette de commandes. Désactivés dans la salle d'entretien (on ne la quitte pas par erreur).
import { m } from 'motion/react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, Outlet, useLocation, useMatch, useNavigate } from 'react-router-dom';
import { api } from '../api.js';
import { FournisseurAgent, useAgent } from '../agent/ContexteAgent.jsx';
import { avecModificateur, dansUnChamp, lancerCommande } from '../commandes.js';
import { useSession } from '../session.jsx';
import { useTheme } from '../theme.js';
import { entreeEcran } from './mouvement.js';
import AideRaccourcis from './shell/AideRaccourcis.jsx';
import BarreEtat from './shell/BarreEtat.jsx';
import BarreLaterale, { NAVIGATION } from './shell/BarreLaterale.jsx';
import { useOptionsTitre } from './shell/Fenetre.jsx';
import Notifications from './shell/Notifications.jsx';
import Palette from './shell/Palette.jsx';
import { Alerte } from './ui.jsx';

const CLE_REPLI = 'injara-barre-repliee';

const lireRepli = () => {
  try {
    return localStorage.getItem(CLE_REPLI) === '1';
  } catch {
    return false;
  }
};

/** Mise en page des écrans connectés. */
export default function Disposition() {
  return (
    <FournisseurAgent>
      <Cadre />
    </FournisseurAgent>
  );
}

/** État de l'envoi des mails : relu au démarrage et à chaque réglage (événement injara:reglages-mails). */
function useEnvoiMails() {
  const [envoi, setEnvoi] = useState(null);
  useEffect(() => {
    const charger = () => api.get('/mails/autorisation').then(setEnvoi, () => {});
    charger();
    window.addEventListener('injara:reglages-mails', charger);
    return () => window.removeEventListener('injara:reglages-mails', charger);
  }, []);
  return envoi;
}

function Cadre() {
  const { email, deconnecter } = useSession();
  const { statut, reconnexionConseillee, oublierErreursSync } = useAgent();
  const envoi = useEnvoiMails();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const salle = useMatch('/entretiens/:id'); // la salle d'entretien occupe toute la zone de contenu
  const { choix } = useTheme();
  const [replieeChoix, setReplieeChoix] = useState(lireRepli);
  const [palette, setPalette] = useState(false);
  const [aide, setAide] = useState(false);
  const zone = useRef(null);
  const repliee = replieeChoix || Boolean(salle);

  const replier = useCallback(() => {
    setReplieeChoix((r) => {
      try {
        localStorage.setItem(CLE_REPLI, r ? '0' : '1');
      } catch {
        // préférence non conservée
      }
      return !r;
    });
  }, []);

  const sortir = useCallback(() => {
    deconnecter();
  }, [deconnecter]);

  const ouvrirPalette = useCallback(() => setPalette(true), []);
  useOptionsTitre({ onPalette: salle ? undefined : ouvrirPalette, demo: statut?.mode === 'fake' });

  // Chaque écran s'ouvre en haut de la zone de contenu.
  useEffect(() => {
    zone.current?.scrollTo({ top: 0 });
  }, [pathname]);

  useEffect(() => {
    const auClavier = (e) => {
      if (e.defaultPrevented || salle) return;
      if (avecModificateur(e) && !e.shiftKey) {
        const touche = e.key.toLowerCase();
        const ecran = NAVIGATION[Number(e.key) - 1];
        if (touche === 'k') {
          e.preventDefault();
          setPalette((p) => !p);
        } else if (ecran) {
          e.preventDefault();
          setPalette(false);
          navigate(ecran.vers);
        } else if (touche === 'n') {
          e.preventDefault();
          navigate('/postes/nouveau');
        } else if (touche === 'i') {
          e.preventDefault();
          navigate('/candidatures');
          lancerCommande('importer-cv');
        } else if (touche === 'b') {
          e.preventDefault();
          replier();
        }
      } else if (e.key === '?' && !dansUnChamp(e) && !palette) {
        e.preventDefault();
        setAide(true);
      }
    };
    window.addEventListener('keydown', auClavier);
    return () => window.removeEventListener('keydown', auClavier);
  }, [navigate, salle, replier, palette]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <a
        href="#contenu"
        onClick={(e) => {
          e.preventDefault();
          zone.current?.focus();
        }}
        className="sr-only z-[100] rounded-md bg-accent px-3 py-2 font-semibold text-sur-accent focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        Aller au contenu
      </a>

      <div className="flex min-h-0 flex-1">
        <BarreLaterale
          repliee={repliee}
          onReplier={replier}
          totalCV={statut?.total_cvs}
          email={email}
          onDeconnecter={sortir}
          onRaccourcis={() => setAide(true)}
          choixTheme={choix}
        />

        {/* Zone de travail : une surface posée dans le cadre, seule partie qui défile. */}
        <main
          id="contenu"
          ref={zone}
          tabIndex={-1}
          className="contenu-selectionnable relative mr-2 flex min-w-0 flex-1 flex-col overflow-y-auto rounded-t-2xl border border-b-0 border-trait bg-fond outline-none [scrollbar-gutter:stable]"
        >
          {reconnexionConseillee && statut?.connected && (
            <div className="sticky top-0 z-20 border-b border-trait bg-fond/95 px-8 py-2.5 backdrop-blur">
              <Alerte
                titre="Les dernières vérifications de la boîte mail ont échoué."
                action={
                  <Link to="/boite-mail" onClick={oublierErreursSync} className="shrink-0 self-center text-sm font-semibold text-fort underline underline-offset-4">
                    Reconnecter le compte
                  </Link>
                }
              >
                Le mot de passe ou l'autorisation a peut-être changé.
              </Alerte>
            </div>
          )}
          {!salle && envoi?.reconnexion && (
            <div className="sticky top-0 z-20 flex flex-col gap-2 border-b border-trait bg-fond/95 px-8 py-2.5 backdrop-blur">
              <Alerte
                titre="L'envoi des mails aux candidats doit être reconnecté."
                action={<Link to="/parametres/mails" className="shrink-0 self-center text-sm font-semibold text-fort underline underline-offset-4">Reconnecter</Link>}
              >
                {envoi.motif}
              </Alerte>
            </div>
          )}
          {salle ? (
            <div className="flex min-h-[34rem] w-full flex-1 flex-col">
              <Outlet />
            </div>
          ) : (
            <m.div key={pathname} {...entreeEcran} className="mx-auto w-full max-w-[1180px] px-10 pt-8 pb-16">
              <Outlet />
            </m.div>
          )}
        </main>
      </div>

      <BarreEtat statut={statut} reconnexionConseillee={reconnexionConseillee} />
      <Notifications />
      <Palette ouverte={palette} onFermer={() => setPalette(false)} onRaccourcis={() => setAide(true)} onDeconnecter={sortir} />
      <AideRaccourcis ouverte={aide} onFermer={() => setAide(false)} />
    </div>
  );
}
