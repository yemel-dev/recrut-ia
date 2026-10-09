// Infobulle : apparaît au survol (après un court délai) et au focus clavier. CSS seulement.
import { cx } from './ui.jsx';

const COTES = {
  droite: 'left-full top-1/2 ml-2 -translate-y-1/2 origin-left',
  haut: 'bottom-full left-1/2 mb-2 -translate-x-1/2 origin-bottom',
  bas: 'top-full left-1/2 mt-2 -translate-x-1/2 origin-top',
};

export default function Infobulle({ texte, cote = 'haut', actif = true, className, children }) {
  if (!actif || !texte) return children;
  return (
    <span className={cx('group/bulle relative inline-flex', className)}>
      {children}
      <span
        role="tooltip"
        className={cx(
          'pointer-events-none absolute z-[80] scale-97 rounded-md border border-trait-fort bg-surface-2 px-2 py-1 text-xs font-medium whitespace-nowrap text-fort opacity-0 shadow-flottante',
          'transition-[opacity,transform] duration-150 ease-out',
          'group-hover/bulle:scale-100 group-hover/bulle:opacity-100 group-hover/bulle:delay-300',
          'group-has-[:focus-visible]/bulle:scale-100 group-has-[:focus-visible]/bulle:opacity-100',
          COTES[cote],
        )}
      >
        {texte}
      </span>
    </span>
  );
}
