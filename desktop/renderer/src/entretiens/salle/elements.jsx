// Petits éléments de la salle d'entretien (thème sombre) : boutons, alertes, sections.
import { AlertCircle, Loader2 } from 'lucide-react';

export const cx = (...classes) => classes.filter(Boolean).join(' ');

const VARIANTES = {
  plein: 'bg-brand-500 text-nuit-950 hover:bg-brand-600 disabled:bg-brand-500/40 disabled:text-nuit-950/60',
  doux: 'bg-white/10 text-white hover:bg-white/15 disabled:text-white/40',
  danger: 'bg-red-600 text-white hover:bg-red-500 disabled:bg-red-600/40',
  discret: 'text-white/70 hover:bg-white/10 hover:text-white disabled:text-white/30',
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
    <div role="alert" className="flex items-start gap-2.5 rounded-lg border border-red-400/30 bg-red-500/10 px-3 py-2.5 text-sm text-red-200">
      <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div>{children}</div>
    </div>
  );
}

export function SuccesSalle({ children }) {
  return <p role="status" className="rounded-lg border border-brand-500/30 bg-brand-500/10 px-3 py-2.5 text-sm text-brand-100">{children}</p>;
}

/** Bloc d'un panneau : titre à icône et contenu. */
export function Section({ titre, icone: Icone, children }) {
  return (
    <section className="flex flex-col gap-3 border-b border-white/10 px-5 py-5 text-sm last:border-b-0">
      <h3 className="flex items-center gap-2 font-semibold text-white">
        {Icone && <Icone className="size-4 text-brand-500" aria-hidden />} {titre}
      </h3>
      {children}
    </section>
  );
}

export const Discret = ({ children }) => <p className="text-xs leading-relaxed text-white/55">{children}</p>;
export const Corps = ({ children }) => <p className="leading-relaxed text-white/75">{children}</p>;

/** Ligne « libellé / valeur » des listes de détails. */
export function Ligne({ libelle, children }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5">
      <dt className="text-white/55">{libelle}</dt>
      <dd className="text-right font-medium text-white">{children}</dd>
    </div>
  );
}
