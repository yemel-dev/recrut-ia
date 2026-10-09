// Polices embarquées (aucun chargement réseau) : sous-ensembles latin et latin étendu, graisses utiles seulement.
import '@fontsource/paytone-one/latin-400.css';
import '@fontsource/paytone-one/latin-ext-400.css';
import '@fontsource/pt-sans/latin-400.css';
import '@fontsource/pt-sans/latin-ext-400.css';
import '@fontsource/pt-sans/latin-400-italic.css';
import '@fontsource/pt-sans/latin-ext-400-italic.css';
import '@fontsource/pt-sans/latin-700.css';
import '@fontsource/pt-sans/latin-ext-700.css';
import '@fontsource/pt-sans/latin-700-italic.css';
import '@fontsource/pt-sans/latin-ext-700-italic.css';
import '@fontsource/satisfy/latin-400.css';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { LucideProvider } from 'lucide-react';
import { LazyMotion, MotionConfig, domMax } from 'motion/react';
import App from './App.jsx';
import { appliquerTheme } from './theme.js';
import './styles.css';

appliquerTheme(); // avant le premier rendu : pas d'éclair de mauvais thème

createRoot(document.getElementById('racine')).render(
  <StrictMode>
    <LazyMotion features={domMax} strict>
      <MotionConfig reducedMotion="user">
        {/* Icônes : une seule bibliothèque (lucide-react) et un seul trait dans toute l'application. */}
        <LucideProvider strokeWidth={1.75}>
          <App />
        </LucideProvider>
      </MotionConfig>
    </LazyMotion>
  </StrictMode>,
);
