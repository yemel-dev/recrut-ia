// Menus flottants : menu déroulant (ancré sur un bouton) et menu contextuel (clic droit, à la position du pointeur).
// Clavier : flèches, Début/Fin, Entrée, Échap (le focus revient au déclencheur). Clic à l'extérieur : fermeture.
import { AnimatePresence, m } from 'motion/react';
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { cx } from './ui.jsx';
import { flottant } from './mouvement.js';

/**
 * elements : [{ libelle, icone, action, danger, raccourci, desactive }] ; `null` = séparateur.
 * position : { x, y } en pixels (coin d'ancrage) ; alignement : 'debut' | 'fin' (bord droit du menu sur x).
 */
function PanneauMenu({ elements, position, alignement = 'debut', onFermer, retourFocus, libelle }) {
  const ref = useRef(null);
  const [place, setPlace] = useState({ left: position.x, top: position.y, origine: 'top left' });

  // Garder le menu dans la fenêtre (il s'ouvre vers le haut ou la gauche s'il manque de place).
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const { width, height } = el.getBoundingClientRect();
    let left = alignement === 'fin' ? position.x - width : position.x;
    let top = position.y;
    let vertical = 'top';
    if (position.versLeHaut || top + height > window.innerHeight - 8) {
      top = Math.max(8, (position.yHaut ?? position.y) - height);
      vertical = 'bottom';
    }
    left = Math.min(Math.max(8, left), window.innerWidth - width - 8);
    setPlace({ left, top, origine: `${vertical} ${alignement === 'fin' ? 'right' : 'left'}` });
    el.querySelector('[role="menuitem"]:not([disabled])')?.focus();
  }, [position, alignement]);

  useEffect(() => {
    const exterieur = (e) => {
      if (!ref.current?.contains(e.target)) onFermer();
    };
    const fermerSurAutre = () => onFermer();
    document.addEventListener('pointerdown', exterieur, true);
    window.addEventListener('blur', fermerSurAutre);
    window.addEventListener('resize', fermerSurAutre);
    return () => {
      document.removeEventListener('pointerdown', exterieur, true);
      window.removeEventListener('blur', fermerSurAutre);
      window.removeEventListener('resize', fermerSurAutre);
    };
  }, [onFermer]);

  const fermerEtRendre = () => {
    onFermer();
    retourFocus?.focus?.();
  };

  const auClavier = (e) => {
    const items = [...ref.current.querySelectorAll('[role="menuitem"]:not([disabled])')];
    const i = items.indexOf(document.activeElement);
    const cible = { ArrowDown: i + 1, ArrowUp: i - 1, Home: 0, End: items.length - 1 }[e.key];
    if (cible !== undefined) {
      e.preventDefault();
      items[(cible + items.length) % items.length]?.focus();
    } else if (e.key === 'Escape' || e.key === 'Tab') {
      e.preventDefault();
      fermerEtRendre();
    }
  };

  return (
    <m.div
      ref={ref}
      role="menu"
      aria-label={libelle}
      onKeyDown={auClavier}
      onContextMenu={(e) => e.preventDefault()}
      style={{ left: place.left, top: place.top, transformOrigin: place.origine }}
      className="fixed z-[70] min-w-52 rounded-lg border border-trait-fort bg-surface-2 p-1 shadow-flottante"
      {...flottant}
    >
      {elements.map((el, i) =>
        el === null ? (
          <div key={`sep-${i}`} role="separator" className="mx-2 my-1 h-px bg-trait" />
        ) : (
          <button
            key={el.libelle}
            type="button"
            role="menuitem"
            disabled={el.desactive}
            onClick={() => {
              onFermer();
              retourFocus?.focus?.();
              el.action();
            }}
            className={cx(
              'geste-hote flex h-8 w-full items-center gap-2.5 rounded-md px-2.5 text-left text-base outline-none transition-colors disabled:opacity-45',
              el.danger ? 'text-danger hover:bg-danger-doux focus-visible:bg-danger-doux' : 'text-texte hover:bg-survol-fort hover:text-fort focus-visible:bg-survol-fort focus-visible:text-fort',
            )}
          >
            {el.icone && <el.icone className={cx('size-4 shrink-0', !el.danger && 'text-doux')} aria-hidden data-geste={el.geste} />}
            <span className="flex-1 truncate">{el.libelle}</span>
            {el.raccourci && <span className="text-xs text-tenu">{el.raccourci}</span>}
          </button>
        ),
      )}
    </m.div>
  );
}

/** Menu contextuel : `ouvrir(evenement, elements)` sur onContextMenu ; afficher `{menu}` dans le rendu. */
export function useMenuContextuel(libelle = 'Actions') {
  const [etat, setEtat] = useState(null);
  const fermer = useCallback(() => setEtat(null), []);
  const ouvrir = useCallback((e, elements) => {
    e.preventDefault();
    const clavier = e.clientX === 0 && e.clientY === 0; // touche Menu ou Maj+F10 : position de l'élément
    const rect = e.currentTarget.getBoundingClientRect();
    setEtat({
      elements,
      retour: e.currentTarget,
      position: clavier ? { x: rect.left + 24, y: rect.bottom - 4 } : { x: e.clientX, y: e.clientY },
    });
  }, []);
  const menu = createPortal(
    <AnimatePresence>
      {etat && <PanneauMenu key="menu" libelle={libelle} elements={etat.elements} position={etat.position} retourFocus={etat.retour} onFermer={fermer} />}
    </AnimatePresence>,
    document.body,
  );
  return { ouvrir, menu };
}

/** Bouton qui ouvre un menu déroulant. `declencheur(props)` rend le bouton. */
export function MenuDeroulant({ elements, declencheur, alignement = 'debut', cote = 'bas', libelle }) {
  const [position, setPosition] = useState(null);
  const bouton = useRef(null);
  const basculer = () => {
    if (position) return setPosition(null);
    const r = bouton.current.getBoundingClientRect();
    return setPosition(
      cote === 'haut'
        ? { x: alignement === 'fin' ? r.right : r.left, y: r.top - 6, yHaut: r.top - 6, versLeHaut: true }
        : { x: alignement === 'fin' ? r.right : r.left, y: r.bottom + 6, yHaut: r.top - 6 },
    );
  };
  return (
    <>
      {declencheur({
        ref: bouton,
        onClick: basculer,
        'aria-haspopup': 'menu',
        'aria-expanded': Boolean(position),
        onKeyDown: (e) => {
          if (e.key === 'ArrowDown' && !position) {
            e.preventDefault();
            basculer();
          }
        },
      })}
      {createPortal(
        <AnimatePresence>
          {position && (
            <PanneauMenu
              key="menu"
              libelle={libelle}
              elements={elements}
              position={position}
              alignement={alignement}
              retourFocus={bouton.current}
              onFermer={() => setPosition(null)}
            />
          )}
        </AnimatePresence>,
        document.body,
      )}
    </>
  );
}
