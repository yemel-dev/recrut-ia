import '@fontsource-variable/unbounded';
import '@fontsource-variable/instrument-sans/wdth.css';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { LazyMotion, MotionConfig, domMax } from 'motion/react';
import App from './App.jsx';
import { appliquerTheme } from './theme.js';
import './styles.css';

appliquerTheme(); // avant le premier rendu : pas d'éclair de mauvais thème

createRoot(document.getElementById('racine')).render(
  <StrictMode>
    <LazyMotion features={domMax} strict>
      <MotionConfig reducedMotion="user">
        <App />
      </MotionConfig>
    </LazyMotion>
  </StrictMode>,
);
