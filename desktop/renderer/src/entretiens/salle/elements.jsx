// Petits éléments de la salle d'entretien (thème sombre) : boutons, alertes, sections.
import { AlertCircle, Loader2 } from 'lucide-react';

export const cx = (...classes) => classes.filter(Boolean).join(' ');

const VARIANTES = {
  plein: 'bg-brand-500 text-nuit-950 hover:bg-brand-600 disabled:bg-brand-500/40 disabled:text-nuit-950/60',
  doux: 'bg-sal-surface text-sal-fort hover:bg-sal-surface-fort disabled:text-sal-doux',
  danger: 'bg-red-600 text-sal-fort hover:bg-red-500 disabled:bg-red-600/40',
  bleu: 'bg-meet text-white hover:bg-meet-700 disabled:bg-meet/50',
  discret: 'text-sal-corps hover:bg-sal-surface hover:text-sal-fort disabled:text-sal-doux',
};

/** Bouton des panneaux latéraux. */
export function BoutonSalle({ variante = 'doux', icone: Icone, chargement = false, className, children, ...props }) {
  return (
    <button
      type="button"
      {...props}
      disabled={props.disabled || chargement}
      className={cx(
        'inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed',
        VARIANTES[variante],
        className,
      )}
    >
      {chargement ? <Loader2 className="size-4 animate-spin" aria-hidden /> : Icone && <Icone className="size-4" aria-hidden />}
      {children}
    </button>
  );
}

export function AlerteSalle({ children }) {
  return (
    <div role="alert" className="flex items-start gap-2.5 rounded-lg border border-red-400/30 bg-red-500/10 px-3 py-2.5 text-sm text-sal-danger">
      <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div>{children}</div>
    </div>
  );
}

export function SuccesSalle({ children }) {
  return <p role="status" className="rounded-lg border border-brand-500/30 bg-brand-500/10 px-3 py-2.5 text-sm text-sal-succes">{children}</p>;
}

/** Bloc d'un panneau : titre à icône et contenu. */
export function Section({ titre, icone: Icone, children }) {
  return (
    <section className="flex flex-col gap-3 border-b border-sal-bord px-5 py-5 text-sm last:border-b-0">
      <h3 className="flex items-center gap-2 font-medium text-sal-fort">
        {Icone && <Icone className="size-4 text-sal-doux" strokeWidth={1.5} aria-hidden />} {titre}
      </h3>
      {children}
    </section>
  );
}

export const Discret = ({ children }) => <p className="text-xs leading-relaxed text-sal-doux">{children}</p>;
export const Corps = ({ children }) => <p className="leading-relaxed text-sal-corps">{children}</p>;

/** Ligne « libellé / valeur » des listes de détails. */
export function Ligne({ libelle, children }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5">
      <dt className="text-sal-doux">{libelle}</dt>
      <dd className="text-right font-medium text-sal-fort">{children}</dd>
    </div>
  );
}
