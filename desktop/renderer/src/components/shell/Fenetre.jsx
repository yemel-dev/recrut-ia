// Cadre de la fenêtre, commun à tous les écrans (connexion comprise) : barre de titre en haut, écran en dessous.
// Les écrans connectés y ajoutent la recherche et le badge « Mode démo » (useOptionsTitre).
import { createContext, useContext, useEffect, useState } from 'react';
import { useTheme } from '../../theme.js';
import BarreTitre from './BarreTitre.jsx';

const ContexteTitre = createContext(() => {});

export default function Fenetre({ children }) {
  const [options, setOptions] = useState({});
  const { theme } = useTheme();
  return (
    <ContexteTitre.Provider value={setOptions}>
      <div className="flex h-full flex-col bg-chrome">
        <BarreTitre {...options} theme={theme} />
        <div className="relative flex min-h-0 flex-1 flex-col">{children}</div>
      </div>
    </ContexteTitre.Provider>
  );
}

/** Options de la barre de titre pour l'écran courant (retirées quand il disparaît). */
export function useOptionsTitre({ onPalette, demo }) {
  const definir = useContext(ContexteTitre);
  useEffect(() => {
    definir({ onPalette, demo });
    return () => definir({});
  }, [definir, onPalette, demo]);
}
