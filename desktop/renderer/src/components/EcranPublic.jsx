import { ShieldCheck } from 'lucide-react';

/** Mise en page des écrans accessibles sans connexion. */
export default function EcranPublic({ titre, sousTitre, children, largeur = 'max-w-md' }) {
  return (
    <div className="flex min-h-full flex-col items-center justify-center px-6 py-12">
      <img src="./injara-horizontal-navy.webp" alt="INJARA" className="mb-8 h-10 w-auto" />
      <main className={`w-full ${largeur} rounded-2xl border border-line bg-white p-8 shadow-sm`}>
        <h1 className="text-xl font-bold text-navy-900">{titre}</h1>
        {sousTitre && <p className="mt-1 text-sm text-muted">{sousTitre}</p>}
        <div className="mt-6">{children}</div>
      </main>
      <p className="mt-6 flex items-center gap-1.5 text-xs text-muted">
        <ShieldCheck className="size-3.5" aria-hidden /> Vos données restent sur cet ordinateur.
      </p>
    </div>
  );
}
