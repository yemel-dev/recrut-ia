// État vide : une invitation à agir, jamais un écran mort. Le symbole INJARA en filigrane derrière l'icône.
import { cx } from './ui.jsx';

export default function EtatVide({ icone: Icone, titre, children, action, compact = false, className }) {
  return (
    <div
      className={cx(
        'relative flex flex-col items-center overflow-hidden rounded-lg border border-dashed border-trait-fort text-center',
        compact ? 'px-6 py-10' : 'px-8 py-16',
        className,
      )}
    >
      <div className="relative mb-5 grid size-16 place-items-center">
        <img src="./marque/symbole-vert-192.webp" alt="" width="64" height="64" className="absolute inset-0 size-16 opacity-15" />
        <span className="relative grid size-10 place-items-center rounded-lg border border-accent-trait bg-surface-2 text-accent-texte shadow-halo">
          <Icone className="size-5" aria-hidden />
        </span>
      </div>
      <h2 className="titre-section">{titre}</h2>
      {children && <div className="mt-2 max-w-md text-base text-doux">{children}</div>}
      {action && <div className="mt-6 flex flex-wrap justify-center gap-2">{action}</div>}
    </div>
  );
}
