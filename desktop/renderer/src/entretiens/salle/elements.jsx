// Petits éléments de la salle d'entretien (thème sombre) : boutons, alertes, sections.
import { AlertCircle, Loader2 } from 'lucide-react';

export const cx = (...classes) => classes.filter(Boolean).join(' ');

const VARIANTES = {
  plein: 'bg-accent text-sur-accent hover:bg-accent-survol disabled:bg-accent/35 disabled:text-sur-accent/60',
  doux: 'bg-sal-surface text-sal-fort hover:bg-sal-surface-fort disabled:text-sal-doux',
  danger: 'bg-danger-plein text-white hover:brightness-110 disabled:opacity-40',
  bleu: 'bg-accent text-sur-accent hover:bg-accent-survol disabled:bg-accent/35',
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
    <div role="alert" className="flex items-start gap-2.5 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2.5 text-sm text-sal-danger">
      <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div>{children}</div>
    </div>
  );
}

export function SuccesSalle({ children }) {
  return <p role="status" className="rounded-lg border border-accent/30 bg-accent/10 px-3 py-2.5 text-sm text-sal-succes">{children}</p>;
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
