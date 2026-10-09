// Composants d'interface communs : ils ne lisent que les tokens sémantiques (styles/tokens.css).
import { AlertCircle, CheckCircle2, Eye, EyeOff, Info, Loader2, TriangleAlert, X } from 'lucide-react';
import { m } from 'motion/react';
import { useEffect, useId, useRef, useState } from 'react';
import { STATUTS } from '../constantes.js';
import { COURBE_SORTIE, DUREE } from './mouvement.js';

export const cx = (...classes) => classes.filter(Boolean).join(' ');

const BOUTONS = {
  primaire:
    'bg-accent text-sur-accent hover:bg-accent-survol disabled:bg-accent/35 disabled:text-sur-accent/60 shadow-[0_1px_0_0_rgb(255_255_255/0.25)_inset]',
  secondaire: 'border border-trait-fort bg-surface-2 text-fort hover:border-doux/50 hover:bg-survol-fort disabled:text-tenu',
  danger: 'bg-danger-plein text-white hover:brightness-110 disabled:opacity-50',
  discret: 'text-doux hover:bg-survol-fort hover:text-fort disabled:text-tenu',
  lien: 'px-0! h-auto! text-accent-texte hover:underline underline-offset-4',
};

const TAILLES = {
  sm: 'h-8 gap-1.5 rounded-md px-2.5 text-sm',
  md: 'h-9 gap-2 rounded-md px-3.5 text-sm',
  lg: 'h-11 gap-2 rounded-lg px-5 text-base',
};

/**
 * Bouton. `icone` : composant Lucide ; `geste` : animation de l'icône au survol (avancer, tourner, soulever…).
 * Sans texte, le bouton est carré : donner alors un aria-label.
 */
export function Bouton({ variante = 'primaire', taille = 'md', chargement = false, icone: Icone, geste, className, children, ...props }) {
  const seuleIcone = !children;
  return (
    <button
      type="button"
      {...props}
      disabled={props.disabled || chargement}
      aria-busy={chargement || undefined}
      className={cx(
        'appui geste-hote inline-flex shrink-0 items-center justify-center font-semibold whitespace-nowrap select-none',
        TAILLES[taille],
        seuleIcone && 'aspect-square px-0!',
        BOUTONS[variante],
        className,
      )}
    >
      {chargement ? (
        <Loader2 className="size-4 animate-spin" aria-hidden />
      ) : (
        Icone && <Icone className="size-4 shrink-0" aria-hidden data-geste={geste} />
      )}
      {children}
    </button>
  );
}

export function Champ({ label, erreur, aide, obligatoire, children, className }) {
  const id = useId();
  return (
    <div className={cx('flex flex-col gap-1.5', className)}>
      <label htmlFor={id} className="text-sm font-medium text-texte">
        {label}
        {obligatoire && <span className="text-danger" aria-hidden> *</span>}
      </label>
      {children({
        id,
        'aria-required': obligatoire || undefined,
        'aria-invalid': Boolean(erreur),
        'aria-describedby': erreur || aide ? `${id}-info` : undefined,
      })}
      {erreur ? (
        <p id={`${id}-info`} className="flex items-start gap-1.5 text-sm text-danger">
          <AlertCircle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          {erreur}
        </p>
      ) : (
        aide && <p id={`${id}-info`} className="text-xs text-doux">{aide}</p>
      )}
    </div>
  );
}

export const CHAMP_SAISIE = cx(
  'w-full rounded-md border border-trait bg-enfonce px-3 text-base text-fort placeholder:text-tenu',
  'transition-[border-color,box-shadow,background-color] duration-150',
  'hover:border-trait-fort focus:border-accent focus:shadow-[0_0_0_3px_var(--accent-doux)] focus:outline-none focus-visible:outline-none',
  'aria-[invalid=true]:border-danger aria-[invalid=true]:shadow-[0_0_0_3px_var(--danger-doux)]',
  'disabled:cursor-not-allowed disabled:opacity-60',
);

export function Saisie({ className, ...props }) {
  return <input {...props} className={cx(CHAMP_SAISIE, 'h-9', className)} />;
}

export function ZoneTexte({ className, ...props }) {
  return <textarea rows={5} {...props} className={cx(CHAMP_SAISIE, 'resize-y py-2 leading-relaxed', className)} />;
}

export function Liste({ options, vide = 'Non précisé', className, ...props }) {
  return (
    <select {...props} className={cx(CHAMP_SAISIE, 'h-9 pr-8', className)}>
      {vide !== null && <option value="">{vide}</option>}
      {Object.entries(options).map(([valeur, libelle]) => (
        <option key={valeur} value={valeur}>{libelle}</option>
      ))}
    </select>
  );
}

export function MotDePasse(props) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <Saisie {...props} type={visible ? 'text' : 'password'} className="pr-10" spellCheck={false} />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        className="absolute inset-y-0 right-0 flex w-10 items-center justify-center rounded-r-md text-doux transition-colors hover:text-fort"
        aria-label={visible ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
        aria-pressed={visible}
      >
        {visible ? <EyeOff className="size-4" aria-hidden /> : <Eye className="size-4" aria-hidden />}
      </button>
    </div>
  );
}

/** Saisie d'une liste : Entrée ou virgule pour ajouter, croix pour retirer. */
export function SaisieListe({ valeur, onChange, placeholder, ...props }) {
  const [brouillon, setBrouillon] = useState('');
  const ajouter = () => {
    const nouveaux = brouillon.split(',').map((v) => v.trim()).filter(Boolean);
    const existants = new Set(valeur.map((v) => v.toLowerCase()));
    const ajout = nouveaux.filter((v) => !existants.has(v.toLowerCase()));
    if (ajout.length) onChange([...valeur, ...ajout]);
    setBrouillon('');
  };
  return (
    <div className="flex flex-col gap-2">
      <Saisie
        {...props}
        value={brouillon}
        placeholder={placeholder}
        onChange={(e) => setBrouillon(e.target.value)}
        onBlur={ajouter}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ',') {
            e.preventDefault();
            ajouter();
          } else if (e.key === 'Backspace' && !brouillon && valeur.length) {
            onChange(valeur.slice(0, -1));
          }
        }}
      />
      {valeur.length > 0 && (
        <ul className="flex flex-wrap gap-1.5">
          {valeur.map((element) => (
            <li key={element} className="inline-flex items-center gap-1 rounded-sm border border-trait bg-survol py-0.5 pr-0.5 pl-2 text-sm text-fort">
              {element}
              <button
                type="button"
                onClick={() => onChange(valeur.filter((v) => v !== element))}
                className="grid size-5 place-items-center rounded-sm text-doux transition-colors hover:bg-survol-fort hover:text-fort"
                aria-label={`Retirer ${element}`}
              >
                <X className="size-3.5" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Carte : surface posée sur le fond de l'écran. `as` permet d'en faire un lien ou un article. */
export function Carte({ as: Element = 'section', sansMarge = false, className, children, ...props }) {
  return (
    <Element {...props} className={cx('rounded-lg border border-trait bg-surface shadow-carte', !sansMarge && 'p-5', className)}>
      {children}
    </Element>
  );
}

const TONS_ALERTE = {
  danger: { classes: 'border-danger-trait bg-danger-doux text-danger', icone: AlertCircle },
  alerte: { classes: 'border-alerte-trait bg-alerte-doux text-alerte', icone: TriangleAlert },
  info: { classes: 'border-info-trait bg-info-doux text-info', icone: Info },
  succes: { classes: 'border-accent-trait bg-accent-doux text-accent-texte', icone: CheckCircle2 },
};

/** Message encadré. Par défaut : une erreur (role="alert"). */
export function Alerte({ ton = 'danger', titre, children, action, className }) {
  if (!children && !titre) return null;
  const { classes, icone: Icone } = TONS_ALERTE[ton];
  return (
    <div role={ton === 'danger' ? 'alert' : 'status'} className={cx('flex items-start gap-3 rounded-md border px-3.5 py-3 text-sm', classes, className)}>
      <Icone className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1 text-texte">
        {titre && <p className="font-semibold text-fort">{titre}</p>}
        {children && <div className={titre ? 'mt-0.5' : ''}>{children}</div>}
      </div>
      {action}
    </div>
  );
}

const TONS_BADGE = {
  neutre: 'border-trait-fort text-doux',
  accent: 'border-accent-trait bg-accent-doux text-accent-texte',
  alerte: 'border-alerte-trait bg-alerte-doux text-alerte',
  danger: 'border-danger-trait bg-danger-doux text-danger',
  info: 'border-info-trait bg-info-doux text-info',
  plein: 'border-accent bg-accent text-sur-accent',
};

/** Badge d'état. `point` ajoute une pastille de couleur devant le libellé. */
export function Badge({ ton = 'neutre', point = false, className, children, ...props }) {
  return (
    <span
      {...props}
      className={cx('inline-flex h-5.5 items-center gap-1.5 rounded-sm border px-2 text-xs font-semibold whitespace-nowrap', TONS_BADGE[ton], className)}
    >
      {point && <span className="size-1.5 rounded-full bg-current" aria-hidden />}
      {children}
    </span>
  );
}

const TON_STATUT = { brouillon: 'info', actif: 'accent', cloture: 'neutre' };

export function BadgeStatut({ statut }) {
  return <Badge ton={TON_STATUT[statut]} point>{STATUTS[statut] || statut}</Badge>;
}

/** En-tête d'écran : titre (Unbounded), description, actions toujours à droite. */
export function EnTetePage({ titre, description, actions, avant }) {
  return (
    <header className="mb-7 flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
      <div className="min-w-0 max-w-3xl">
        {avant}
        <h1 className="titre-ecran">{titre}</h1>
        {description && <p className="mt-2 text-base text-doux">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

/** Indicateur de chargement : le symbole INJARA tourne lentement. */
export function Chargement({ texte = 'Chargement…', plein = false }) {
  return (
    <div role="status" className={cx('flex flex-col items-center justify-center gap-4 text-sm text-doux', plein ? 'h-full' : 'py-20')}>
      <img src="./marque/symbole-vert-96.webp" alt="" width="40" height="40" className="rotation-lente size-10 opacity-90" />
      {texte}
    </div>
  );
}

/** Boîte de confirmation modale (utilisée avant toute suppression). */
export function Confirmation({ ouverte, titre, children, libelleConfirmer = 'Confirmer', onConfirmer, onAnnuler, chargement, variante = 'danger' }) {
  const dialogue = useRef(null);
  const idTitre = useId();
  useEffect(() => {
    const d = dialogue.current;
    if (!d) return;
    if (ouverte && !d.open) d.showModal();
    if (!ouverte && d.open) d.close();
  }, [ouverte]);
  return (
    <dialog
      ref={dialogue}
      aria-labelledby={idTitre}
      onCancel={(e) => {
        e.preventDefault();
        if (!chargement) onAnnuler();
      }}
      className="modale-native m-auto w-full max-w-md overflow-hidden rounded-xl border border-trait-fort bg-surface-2 p-0 text-texte shadow-flottante"
    >
      <div className="p-6">
        <h2 id={idTitre} className="titre-section">{titre}</h2>
        <div className="mt-2 text-base text-doux">{children}</div>
      </div>
      <div className="flex justify-end gap-2 border-t border-trait bg-survol px-6 py-3.5">
        <Bouton variante="secondaire" onClick={onAnnuler} disabled={chargement} autoFocus>Annuler</Bouton>
        <Bouton variante={variante} onClick={onConfirmer} chargement={chargement}>{libelleConfirmer}</Bouton>
      </div>
    </dialog>
  );
}

/** Interrupteur marche / arrêt. */
export function Interrupteur({ actif, onChange, libelle, disabled }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={actif}
      disabled={disabled}
      onClick={() => onChange(!actif)}
      className="group inline-flex items-center gap-3 text-sm font-medium text-texte disabled:opacity-60"
    >
      <span
        className={cx(
          'relative inline-flex h-5 w-9 shrink-0 rounded-full border transition-colors duration-200',
          actif ? 'border-accent bg-accent' : 'border-trait-fort bg-survol-fort group-hover:border-doux/50',
        )}
      >
        <span
          className={cx(
            'absolute top-0.5 left-0.5 size-3.5 rounded-full shadow-sm transition-[transform,background-color] duration-200 ease-out',
            actif ? 'translate-x-4 bg-nuit-900' : 'bg-doux',
          )}
        />
      </span>
      {libelle}
    </button>
  );
}

/** Navigation clavier d'une liste d'onglets ou de segments : flèches, Début, Fin. */
function auClavier(e, valeurs, valeur, onChange) {
  const i = valeurs.indexOf(valeur);
  const cible = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: valeurs.length - 1 }[e.key];
  if (cible === undefined) return;
  e.preventDefault();
  const suivante = valeurs[(cible + valeurs.length) % valeurs.length];
  onChange(suivante);
  e.currentTarget.querySelector(`[data-valeur="${CSS.escape(String(suivante))}"]`)?.focus();
}

/** Onglets : [{ valeur, libelle, compteur? }]. Le soulignement vert glisse vers l'onglet choisi. */
export function Onglets({ onglets, valeur, onChange, className }) {
  const groupe = useId();
  return (
    <div
      className={cx('mb-5 flex gap-1 border-b border-trait', className)}
      role="tablist"
      onKeyDown={(e) => auClavier(e, onglets.map((o) => o.valeur), valeur, onChange)}
    >
      {onglets.map((o) => {
        const actif = valeur === o.valeur;
        return (
          <button
            key={o.valeur}
            type="button"
            role="tab"
            data-valeur={o.valeur}
            aria-selected={actif}
            tabIndex={actif ? 0 : -1}
            onClick={() => onChange(o.valeur)}
            className={cx(
              'relative -mb-px flex h-10 items-center gap-2 rounded-t-md px-3 text-base font-medium transition-colors',
              actif ? 'text-fort' : 'text-doux hover:text-fort',
            )}
          >
            {o.libelle}
            {o.compteur > 0 && (
              <span className={cx('rounded-sm px-1.5 text-xs tabular-nums', actif ? 'bg-accent-doux text-accent-texte' : 'bg-survol-fort text-doux')}>
                {o.compteur}
              </span>
            )}
            {actif && (
              <m.span
                layoutId={`onglet-${groupe}`}
                className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-accent"
                transition={{ duration: DUREE.normale, ease: COURBE_SORTIE }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}

/** Contrôle segmenté (filtres) : [{ valeur, libelle, compteur? }]. */
export function Segments({ options, valeur, onChange, libelle, className }) {
  return (
    <div
      role="radiogroup"
      aria-label={libelle}
      className={cx('inline-flex gap-0.5 rounded-md border border-trait bg-enfonce p-0.5', className)}
      onKeyDown={(e) => auClavier(e, options.map((o) => o.valeur), valeur, onChange)}
    >
      {options.map((o) => {
        const actif = valeur === o.valeur;
        return (
          <button
            key={o.valeur}
            type="button"
            role="radio"
            data-valeur={o.valeur}
            aria-checked={actif}
            tabIndex={actif ? 0 : -1}
            onClick={() => onChange(o.valeur)}
            className={cx(
              'inline-flex h-7 items-center gap-1.5 rounded-[5px] px-2.5 text-sm font-medium whitespace-nowrap transition-colors',
              actif ? 'bg-surface-2 text-fort shadow-[0_1px_2px_rgb(0_0_0/0.2)] ring-1 ring-trait-fort' : 'text-doux hover:text-fort',
            )}
          >
            {o.libelle}
            {o.compteur !== undefined && <span className={cx('tabular-nums', actif ? 'text-accent-texte' : 'text-tenu')}>{o.compteur}</span>}
          </button>
        );
      })}
    </div>
  );
}

/** Raccourci clavier affiché (Ctrl, K…). */
export function Touche({ children, className }) {
  return (
    <kbd className={cx('inline-flex h-5 min-w-5 items-center justify-center rounded-[4px] border border-trait-fort bg-survol px-1 font-sans text-[11px] font-medium text-doux', className)}>
      {children}
    </kbd>
  );
}
