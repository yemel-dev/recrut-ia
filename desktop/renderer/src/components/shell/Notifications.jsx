// Notifications (toasts) : en bas à droite, au-dessus de la barre d'état. Même API qu'avant : notifier(message, type).
// Entrée par le bas et sortie par le même chemin ; Motion les rend interruptibles quand elles s'empilent.
import { CircleAlert, CircleCheck, Info, X } from 'lucide-react';
import { AnimatePresence, m } from 'motion/react';
import { useAgent } from '../../agent/ContexteAgent.jsx';
import { cx } from '../ui.jsx';

const TYPES = {
  succes: { icone: CircleCheck, couleur: 'text-accent-texte', lisere: 'before:bg-accent' },
  erreur: { icone: CircleAlert, couleur: 'text-danger', lisere: 'before:bg-danger' },
  info: { icone: Info, couleur: 'text-info', lisere: 'before:bg-info' },
};

export default function Notifications() {
  const { notifications, fermerNotification } = useAgent();
  return (
    <ol className="pointer-events-none fixed right-4 bottom-[calc(var(--hauteur-etat)+12px)] z-[60] flex w-[22rem] flex-col gap-2" aria-live="polite" aria-label="Notifications">
      <AnimatePresence initial={false}>
        {notifications.map(({ id, message, type }) => {
          const { icone: Icone, couleur, lisere } = TYPES[type] || TYPES.info;
          return (
            <m.li
              key={id}
              initial={{ opacity: 0, transform: 'translateY(100%)' }}
              animate={{ opacity: 1, transform: 'translateY(0%)' }}
              exit={{ opacity: 0, transform: 'translateY(40%)', transition: { duration: 0.18 } }}
              transition={{ duration: 0.32, ease: [0.23, 1, 0.32, 1] }}
              role={type === 'erreur' ? 'alert' : 'status'}
              className={cx(
                'pointer-events-auto relative flex items-start gap-3 overflow-hidden rounded-lg border border-trait-fort bg-surface-2 py-3 pr-3 pl-4 shadow-flottante',
                'before:absolute before:inset-y-0 before:left-0 before:w-[3px]',
                lisere,
              )}
            >
              <Icone className={cx('mt-0.5 size-4 shrink-0', couleur)} aria-hidden />
              <p className="contenu-selectionnable min-w-0 flex-1 text-base break-words text-fort">{message}</p>
              <button
                type="button"
                onClick={() => fermerNotification(id)}
                className="-m-1 grid size-6 shrink-0 place-items-center rounded-sm text-doux transition-colors hover:bg-survol-fort hover:text-fort"
                aria-label="Fermer la notification"
              >
                <X className="size-3.5" aria-hidden />
              </button>
            </m.li>
          );
        })}
      </AnimatePresence>
    </ol>
  );
}
