// Écrans accessibles sans connexion (création du compte, connexion, récupération).
// À gauche : la marque (soleil et logotype) et le formulaire dans une carte en verre, posée sur une photo floutée.
// À droite : panneau blanc cassé à motifs, accroche, illustration et atouts. Les deux soleils tournent en continu
// (CSS, .soleil-tournant). Aucune animation en JavaScript. Styles propres à ces écrans : styles/ecran-public.css.
import { ScanText, ShieldCheck, Video } from 'lucide-react';

const ATOUTS = [
  { icone: ScanText, texte: 'Chaque CV reçu est lu, noté et rattaché au bon poste.' },
  { icone: Video, texte: 'Entretiens vidéo avec le candidat, sans rien lui faire installer.' },
  { icone: ShieldCheck, texte: 'Tout reste chiffré sur cet ordinateur.' },
];

/**
 * `accroche` : mot d'accueil facultatif, en police décorative au-dessus du titre (« Bon retour », « Bienvenue »).
 * `largeur` : largeur maximale de la carte du formulaire.
 */
export default function EcranPublic({ titre, sousTitre, accroche, children, largeur = 'max-w-[27rem]' }) {
  return (
    <div className="flex min-h-0 flex-1 bg-nuit-900">
      {/* ─── Gauche : marque et formulaire ─── */}
      <main className="contenu-selectionnable public-defilement relative isolate flex min-w-0 flex-1 flex-col overflow-y-auto px-8 py-6 lg:px-12">
        <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden" aria-hidden>
          <img src="./connexion/arriere-plan.webp" alt="" className="public-photo size-full object-cover" />
          <div className="public-voile absolute inset-0" />
        </div>

        <header className="flex items-center gap-3.5">
          <img src="./marque/symbole-vert-192.webp" alt="" width="56" height="56" className="soleil-tournant size-14" />
          <img src="./marque/logotype-blanc-128.webp" alt="INJARA" height="40" className="h-10 w-auto" />
        </header>

        <div className={`zone-verre carte-verre mx-auto my-auto w-full ${largeur} px-8 py-8 sm:px-10`}>
          <div className="apparition">
            {accroche && <p className="font-accent text-[1.75rem] leading-none text-accent-texte">{accroche}</p>}
            <h1 className={`text-[2rem] leading-tight text-fort ${accroche ? 'mt-2' : ''}`}>{titre}</h1>
            {sousTitre && <p className="mt-2.5 text-base text-doux">{sousTitre}</p>}
            <div className="mt-7">{children}</div>
          </div>
        </div>

        <p className="pastille-verre mx-auto mt-6 flex items-center gap-2 rounded-full px-4 py-1.5 text-sm text-white/90">
          <ShieldCheck className="size-4 text-vert-300" aria-hidden /> Vos données restent sur cet ordinateur.
        </p>
      </main>

      {/* ─── Droite : panneau de marque ─── */}
      <aside className="panneau-marque relative isolate hidden w-[46%] max-w-[880px] shrink-0 flex-col overflow-hidden lg:flex">
        <img
          src="./marque/symbole-vert-512.webp"
          alt=""
          width="520"
          height="520"
          className="soleil-tournant pointer-events-none absolute -right-44 -bottom-48 -z-10 size-[520px] opacity-12"
        />

        <div className="m-auto flex w-full max-w-[34rem] flex-col items-center px-10 py-8 text-center">
          <h2 className="max-w-[26rem] text-[1.625rem] leading-tight text-nuit-900">
            Le tri des candidatures est fait. La décision vous appartient.
          </h2>

          <div className="arche mt-7 flex w-[min(100%,40vh,26rem)] items-end justify-center overflow-hidden px-4 pt-8">
            <img
              src="./connexion/femme-analyse.webp"
              alt="Une recruteuse examine des CV à la loupe."
              width="960"
              height="936"
              className="h-auto w-full"
            />
          </div>

          <ul className="mt-7 flex flex-col gap-3 text-left">
            {ATOUTS.map(({ icone: Icone, texte }) => (
              <li key={texte} className="flex items-start gap-3 text-base">
                <span className="grid size-7 shrink-0 place-items-center rounded-full bg-white text-vert-700 shadow-[0_0_0_1px_rgb(3_30_64/0.08)]">
                  <Icone className="size-4" aria-hidden />
                </span>
                <span className="pt-1">{texte}</span>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  );
}
