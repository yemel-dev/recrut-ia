import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { EVENEMENT_SESSION_EXPIREE, api } from './api.js';

const ContexteSession = createContext(null);

export function FournisseurSession({ children }) {
  const [etat, setEtat] = useState({ charge: false, compteExiste: false, connecte: false, email: null, erreur: null });

  const rafraichir = useCallback(async () => {
    try {
      const e = await api.get('/auth/etat');
      setEtat({ charge: true, compteExiste: e.compte_existe, connecte: e.connecte, email: e.email, erreur: null });
    } catch (err) {
      setEtat((s) => ({ ...s, charge: true, erreur: err.message }));
    }
  }, []);

  const connecter = useCallback(
    async (email, motDePasse) => {
      await api.post('/auth/connexion', { email, mot_de_passe: motDePasse });
      await rafraichir();
    },
    [rafraichir],
  );

  const deconnecter = useCallback(async () => {
    try {
      await api.post('/auth/deconnexion');
    } finally {
      await rafraichir();
    }
  }, [rafraichir]);

  useEffect(() => {
    rafraichir();
    window.addEventListener(EVENEMENT_SESSION_EXPIREE, rafraichir);
    return () => window.removeEventListener(EVENEMENT_SESSION_EXPIREE, rafraichir);
  }, [rafraichir]);

  return (
    <ContexteSession.Provider value={{ ...etat, rafraichir, connecter, deconnecter }}>{children}</ContexteSession.Provider>
  );
}

export function useSession() {
  return useContext(ContexteSession);
}
