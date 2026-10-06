// Composants d'interface communs.
import { AlertCircle, Eye, EyeOff, Loader2, X } from 'lucide-react';
import { useEffect, useId, useRef, useState } from 'react';
import { STATUTS } from '../constantes.js';

const cx = (...classes) => classes.filter(Boolean).join(' ');

const BOUTONS = {
  primaire: 'bg-brand-600 text-white hover:bg-brand-700 disabled:bg-brand-600/50',
  secondaire: 'bg-white text-navy-900 border border-line hover:bg-navy-50 disabled:text-muted',
  danger: 'bg-danger text-white hover:bg-danger/90 disabled:bg-danger/50',
  discret: 'text-navy-700 hover:bg-navy-50',
};

export function Bouton({ variante = 'primaire', chargement = false, icone: Icone, className, children, ...props }) {
  return (
    <button
      type="button"
      {...props}
      disabled={props.disabled || chargement}
      className={cx(
        'inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed',
        BOUTONS[variante],
        className,
      )}
    >
      {chargement ? <Loader2 className="size-4 animate-spin" aria-hidden /> : Icone && <Icone className="size-4" aria-hidden />}
      {children}
    </button>
  );
}

export function Champ({ label, erreur, aide, obligatoire, children, className }) {
  const id = useId();
  return (
    <div className={cx('flex flex-col gap-1.5', className)}>
      <label htmlFor={id} className="text-sm font-medium text-navy-800">
        {label}
        {obligatoire && <span className="text-danger"> *</span>}
      </label>
      {children({ id, 'aria-invalid': Boolean(erreur), 'aria-describedby': erreur || aide ? `${id}-info` : undefined })}
      {erreur ? (
        <p id={`${id}-info`} className="text-sm text-danger">{erreur}</p>
      ) : (
        aide && <p id={`${id}-info`} className="text-xs text-muted">{aide}</p>
      )}
    </div>
  );
}

const CHAMP_SAISIE =
  'w-full rounded-lg border border-line bg-white px-3 py-2 text-sm text-navy-900 placeholder:text-navy-200 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100 aria-[invalid=true]:border-danger';

export function Saisie({ className, ...props }) {
  return <input {...props} className={cx(CHAMP_SAISIE, className)} />;
}

export function ZoneTexte({ className, ...props }) {
  return <textarea rows={5} {...props} className={cx(CHAMP_SAISIE, 'resize-y', className)} />;
}

export function Liste({ options, vide = 'Non précisé', className, ...props }) {
  return (
    <select {...props} className={cx(CHAMP_SAISIE, className)}>
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
      <Saisie {...props} type={visible ? 'text' : 'password'} className="pr-10" />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-muted hover:text-navy-900"
        aria-label={visible ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
      >
        {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
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
            <li key={element} className="inline-flex items-center gap-1 rounded-full bg-navy-50 py-1 pl-3 pr-1 text-sm text-navy-800">
              {element}
              <button
                type="button"
                onClick={() => onChange(valeur.filter((v) => v !== element))}
                className="rounded-full p-0.5 text-muted hover:bg-navy-100 hover:text-navy-900"
                aria-label={`Retirer ${element}`}
              >
                <X className="size-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Carte({ className, children }) {
  return <section className={cx('rounded-xl border border-line bg-white p-6', className)}>{children}</section>;
}

export function Alerte({ children }) {
  if (!children) return null;
  return (
    <div role="alert" className="flex items-start gap-2 rounded-lg border border-danger/20 bg-danger-50 px-4 py-3 text-sm text-danger">
      <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div>{children}</div>
    </div>
  );
}

const COULEURS_STATUT = {
  brouillon: 'bg-navy-50 text-navy-700 ring-navy-100',
  actif: 'bg-brand-50 text-brand-700 ring-brand-100',
  cloture: 'bg-white text-muted ring-line',
};

export function BadgeStatut({ statut }) {
  return (
    <span className={cx('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset', COULEURS_STATUT[statut])}>
      {STATUTS[statut] || statut}
    </span>
  );
}

export function EnTetePage({ titre, description, actions }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-navy-900">{titre}</h1>
        {description && <p className="mt-1 text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  );
}

export function Chargement({ texte = 'Chargement…' }) {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted">
      <Loader2 className="size-4 animate-spin" aria-hidden /> {texte}
    </div>
  );
}

/** Boîte de confirmation modale (utilisée avant toute suppression). */
export function Confirmation({ ouverte, titre, children, libelleConfirmer = 'Confirmer', onConfirmer, onAnnuler, chargement }) {
  const dialogue = useRef(null);
  useEffect(() => {
    const d = dialogue.current;
    if (!d) return;
    if (ouverte && !d.open) d.showModal();
    if (!ouverte && d.open) d.close();
  }, [ouverte]);
  return (
    <dialog
      ref={dialogue}
      onCancel={(e) => {
        e.preventDefault();
        if (!chargement) onAnnuler();
      }}
      className="m-auto w-full max-w-md rounded-xl border border-line bg-white p-0 shadow-xl backdrop:bg-navy-900/40"
    >
      <div className="p-6">
        <h2 className="text-lg font-semibold text-navy-900">{titre}</h2>
        <div className="mt-2 text-sm text-muted">{children}</div>
      </div>
      <div className="flex justify-end gap-2 border-t border-line bg-mist px-6 py-4">
        <Bouton variante="secondaire" onClick={onAnnuler} disabled={chargement} autoFocus>Annuler</Bouton>
        <Bouton variante="danger" onClick={onConfirmer} chargement={chargement}>{libelleConfirmer}</Bouton>
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
      className="inline-flex items-center gap-3 text-sm font-medium text-navy-800 disabled:cursor-not-allowed disabled:opacity-60"
    >
      <span className={cx('relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors', actif ? 'bg-brand-600' : 'bg-navy-100')}>
        <span className={cx('absolute top-0.5 left-0.5 size-5 rounded-full bg-white shadow transition-transform', actif && 'translate-x-5')} />
      </span>
      {libelle}
    </button>
  );
}

/** Onglets simples : [{ valeur, libelle, compteur? }]. */
export function Onglets({ onglets, valeur, onChange }) {
  return (
    <div className="mb-4 flex gap-1 border-b border-line" role="tablist">
      {onglets.map((o) => (
        <button
          key={o.valeur}
          type="button"
          role="tab"
          aria-selected={valeur === o.valeur}
          onClick={() => onChange(o.valeur)}
          className={cx(
            '-mb-px flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors',
            valeur === o.valeur ? 'border-brand-600 text-navy-900' : 'border-transparent text-muted hover:text-navy-900',
          )}
        >
          {o.libelle}
          {o.compteur > 0 && <span className="rounded-full bg-navy-50 px-2 py-0.5 text-xs text-navy-700">{o.compteur}</span>}
        </button>
      ))}
    </div>
  );
}
