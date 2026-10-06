import { Check, Copy, KeyRound, TriangleAlert } from 'lucide-react';
import { useState } from 'react';
import { Bouton } from './ui.jsx';

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
      <div className="flex gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        <TriangleAlert className="mt-0.5 size-5 shrink-0" aria-hidden />
        <div>
          <p className="font-semibold">Cette clé ne sera affichée qu'une seule fois.</p>
          <p className="mt-1">
            C'est le seul moyen de retrouver l'accès à vos données si vous oubliez votre mot de passe. Notez-la sur
            papier ou dans un gestionnaire de mots de passe, et rangez-la hors de cet ordinateur.
          </p>
        </div>
      </div>

      <div className="rounded-lg border border-line bg-mist p-4">
        <div className="mb-2 flex items-center gap-2 text-xs font-semibold tracking-wide text-muted uppercase">
          <KeyRound className="size-3.5" aria-hidden /> Clé de récupération
        </div>
        <p className="font-mono text-lg font-semibold tracking-wider break-all text-navy-900 select-all">{cle}</p>
        <Bouton variante="secondaire" icone={copiee ? Check : Copy} onClick={copier} className="mt-3">
          {copiee ? 'Copiée' : 'Copier'}
        </Bouton>
      </div>

      <label className="flex cursor-pointer items-start gap-3 text-sm text-navy-800">
        <input
          type="checkbox"
          checked={conservee}
          onChange={(e) => setConservee(e.target.checked)}
          className="mt-0.5 size-4 accent-brand-600"
        />
        Je l'ai conservée en lieu sûr.
      </label>

      <Bouton onClick={onContinuer} disabled={!conservee}>{libelleContinuer}</Bouton>
    </div>
  );
}
