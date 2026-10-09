import { Check, Copy, KeyRound } from 'lucide-react';
import { useState } from 'react';
import { Alerte, Bouton } from './ui.jsx';

/** Affiche la clé de récupération une seule fois ; impossible de continuer sans cocher la case. */
export default function CleRecuperation({ cle, onContinuer, libelleContinuer = 'Continuer vers la connexion' }) {
  const [conservee, setConservee] = useState(false);
  const [copiee, setCopiee] = useState(false);

  const copier = async () => {
    try {
      await navigator.clipboard.writeText(cle);
      setCopiee(true);
      setTimeout(() => setCopiee(false), 2000);
    } catch {
      setCopiee(false);
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <Alerte ton="alerte" titre="Cette clé ne sera affichée qu'une seule fois.">
        C'est le seul moyen de retrouver l'accès à vos données si vous oubliez votre mot de passe. Notez-la sur papier
        ou dans un gestionnaire de mots de passe, et rangez-la hors de cet ordinateur.
      </Alerte>

      <div className="rounded-lg border border-trait-fort bg-enfonce p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <span className="etiquette flex items-center gap-1.5">
            <KeyRound className="size-3.5" aria-hidden /> Clé de récupération
          </span>
          <Bouton variante="secondaire" taille="sm" icone={copiee ? Check : Copy} onClick={copier} aria-live="polite">
            {copiee ? 'Copiée' : 'Copier'}
          </Bouton>
        </div>
        <p
          className="grid grid-cols-4 gap-x-3 gap-y-1.5 font-mono text-lg font-semibold tracking-wider text-fort tabular-nums select-all"
          aria-label={cle}
          translate="no"
        >
          {cle.split('-').map((groupe, i) => (
            <span key={i}>{groupe}</span>
          ))}
        </p>
      </div>

      <label className="flex cursor-pointer items-start gap-3 text-base text-texte">
        <input
          type="checkbox"
          checked={conservee}
          onChange={(e) => setConservee(e.target.checked)}
          className="mt-0.5 size-4 shrink-0 accent-[var(--accent)]"
        />
        Je l'ai conservée en lieu sûr.
      </label>

      <Bouton taille="lg" onClick={onContinuer} disabled={!conservee}>{libelleContinuer}</Bouton>
    </div>
  );
}
