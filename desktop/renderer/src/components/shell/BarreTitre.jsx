// Barre de titre de la fenêtre (sans cadre natif) : marque, recherche / palette de commandes, mode démo, boutons de fenêtre.
// Windows : boutons natifs posés par-dessus (Window Controls Overlay), la barre leur laisse la place.
// macOS : pastilles natives à gauche. Linux : boutons dessinés ici (la surcouche native fait planter Electron sous Wayland).
import { Copy, Minus, Search, Square, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { MAC, MODIFICATEUR } from '../../commandes.js';
import { Touche, cx } from '../ui.jsx';

const fenetre = window.injara?.fenetre;
const BOUTONS_INTERFACE = Boolean(fenetre?.boutonsInterface);

function BoutonsFenetre() {
  const [agrandie, setAgrandie] = useState(false);
  useEffect(() => fenetre.surEtat((e) => setAgrandie(e.agrandie)), []);
  const classe = 'region-fixe grid h-full w-11 place-items-center text-doux transition-colors hover:bg-survol-fort hover:text-fort';
  return (
    <div className="flex h-full self-stretch" role="group" aria-label="Fenêtre">
      <button type="button" className={classe} onClick={() => fenetre.action('reduire')} aria-label="Réduire">
        <Minus className="size-4" aria-hidden />
      </button>
      <button type="button" className={classe} onClick={() => fenetre.action('agrandir')} aria-label={agrandie ? 'Restaurer' : 'Agrandir'}>
        {agrandie ? <Copy className="size-3.5 -scale-x-100" aria-hidden /> : <Square className="size-3.5" aria-hidden />}
      </button>
      <button
        type="button"
        className={cx(classe, 'hover:bg-danger-plein hover:text-white')}
        onClick={() => fenetre.action('fermer')}
        aria-label="Fermer INJARA"
      >
        <X className="size-4" aria-hidden />
      </button>
    </div>
  );
}

export default function BarreTitre({ onPalette, demo, theme }) {
  return (
    <header
      onDoubleClick={(e) => BOUTONS_INTERFACE && e.target === e.currentTarget && fenetre.action('agrandir')}
      className="region-glisser relative z-30 flex h-[var(--hauteur-titre)] shrink-0 items-center gap-3 bg-chrome select-none"
      style={{
        paddingLeft: MAC ? 84 : 16,
        // Windows : place des boutons natifs (zone hors de la surcouche). Linux : nos boutons sont collés au bord.
        paddingRight: BOUTONS_INTERFACE || MAC ? 0 : 'calc(100vw - env(titlebar-area-x, 0px) - env(titlebar-area-width, 100vw))',
      }}
    >
      <div className="pointer-events-none flex w-[calc(var(--largeur-barre)-16px)] shrink-0 items-center gap-2.5">
        <img src="./marque/symbole-vert-48.webp" alt="" width="20" height="20" className="size-5" />
        <img
          src={theme === 'clair' ? './marque/logotype-nuit-64.webp' : './marque/logotype-blanc-64.webp'}
          alt="Injara"
          height="14"
          className="h-3.5 w-auto"
        />
      </div>

      <div className="flex min-w-0 flex-1 justify-center">
        {onPalette && (
          <button
            type="button"
            onClick={onPalette}
            className="region-fixe flex h-7 w-full max-w-md items-center gap-2 rounded-md border border-trait bg-survol px-2.5 text-sm text-doux transition-colors hover:border-trait-fort hover:bg-survol-fort hover:text-texte"
            aria-label="Rechercher ou lancer une action"
            aria-keyshortcuts={MAC ? 'Meta+K' : 'Control+K'}
          >
            <Search className="size-3.5 shrink-0" aria-hidden />
            <span className="flex-1 truncate text-left">Rechercher un candidat, un poste, une action…</span>
            <span className="flex gap-0.5">
              <Touche>{MODIFICATEUR}</Touche>
              <Touche>K</Touche>
            </span>
          </button>
        )}
      </div>

      <div className="flex h-full shrink-0 items-center justify-end gap-3" style={{ minWidth: BOUTONS_INTERFACE ? undefined : 'calc(var(--largeur-barre) - 16px)' }}>
        {demo && (
          <span
            className="region-fixe inline-flex h-6 items-center gap-1.5 rounded-sm border border-alerte-trait bg-alerte-doux px-2 text-xs font-semibold text-alerte"
            title="La boîte mail est simulée : les candidatures sont des exemples."
          >
            <span className="size-1.5 rounded-full bg-current" aria-hidden />
            Mode démo
          </span>
        )}
        {BOUTONS_INTERFACE && <BoutonsFenetre />}
      </div>
    </header>
  );
}
