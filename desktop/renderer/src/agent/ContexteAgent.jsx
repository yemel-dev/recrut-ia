// État de l'agent mail partagé par tous les écrans connectés, et boucle des notifications.
import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { api } from '../api.js';

const Contexte = createContext(null);
const INTERVALLE_EVENEMENTS_MS = 5000;
const ERREURS_AVANT_RECONNEXION = 2;

export function FournisseurAgent({ children }) {
  const [statut, setStatut] = useState(null); // GmailStatus
  const [etat, setEtat] = useState(null); // { mode, surveillance_souhaitee, identifiants_google }
  const [erreur, setErreur] = useState('');
  const [notifications, setNotifications] = useState([]);
  const [erreursSync, setErreursSync] = useState(0);
  const [version, setVersion] = useState(0); // incrémentée quand de nouveaux CV arrivent
  const dernierId = useRef(null);

  const rafraichir = useCallback(async () => {
    try {
      const [s, e] = await Promise.all([api.get('/gmail/status'), api.get('/agent/etat')]);
      setStatut(s);
      setEtat(e);
      setErreur('');
      return s;
    } catch (err) {
      setErreur(err.message);
      return null;
    }
  }, []);

  const notifier = useCallback((message, type = 'info') => {
    const id = `${Date.now()}-${Math.random()}`;
    setNotifications((n) => [...n.slice(-3), { id, message, type }]);
    setTimeout(() => setNotifications((n) => n.filter((x) => x.id !== id)), 6000);
  }, []);

  const fermerNotification = useCallback((id) => setNotifications((n) => n.filter((x) => x.id !== id)), []);

  useEffect(() => {
    rafraichir();
  }, [rafraichir]);

  // Boucle des événements : au premier passage, on lit l'historique sans notifier (pas de notifications rejouées).
  useEffect(() => {
    let actif = true;
    const tour = async () => {
      try {
        const depuis = dernierId.current ?? 0;
        const evenements = await api.get(`/gmail/events?after_id=${depuis}`);
        if (!actif) return;
        const premierPassage = dernierId.current === null;
        if (evenements.length) dernierId.current = evenements.at(-1).id;
        else if (premierPassage) dernierId.current = 0;
        if (premierPassage) return;

        let changement = false;
        for (const e of evenements) {
          changement = true;
          if (e.type === 'new_cvs') {
            notifier(e.message, 'succes');
            setErreursSync(0);
            setVersion((v) => v + 1);
          } else if (e.type === 'sync_error') {
            notifier(e.message, 'erreur');
            setErreursSync((n) => n + 1);
          } else if (e.type === 'connected') {
            setErreursSync(0);
          }
        }
        if (changement) rafraichir();
      } catch {
        // Moteur momentanément indisponible : on réessaie au prochain tour.
      }
    };
    tour();
    const minuteur = setInterval(tour, INTERVALLE_EVENEMENTS_MS);
    return () => {
      actif = false;
      clearInterval(minuteur);
    };
  }, [notifier, rafraichir]);

  const valeur = {
    statut,
    etat,
    erreur,
    rafraichir,
    notifier,
    notifications,
    fermerNotification,
    version,
    signalerNouveauxCV: () => setVersion((v) => v + 1),
    reconnexionConseillee: erreursSync >= ERREURS_AVANT_RECONNEXION,
    oublierErreursSync: () => setErreursSync(0),
  };
  return <Contexte.Provider value={valeur}>{children}</Contexte.Provider>;
}

export function useAgent() {
  return useContext(Contexte);
}
