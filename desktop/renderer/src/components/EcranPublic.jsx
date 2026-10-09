// Écrans accessibles sans connexion (création du compte, connexion, récupération) : formulaire à gauche,
// panneau de marque à droite. L'apparition du symbole est le seul moment orchestré de l'application.
import { ScanText, ShieldCheck, Video } from 'lucide-react';
import { m } from 'motion/react';
import { useTheme } from '../theme.js';
import { COURBE_SORTIE } from './mouvement.js';

const ATOUTS = [
  { icone: ScanText, texte: 'Chaque CV reçu est lu, noté et rattaché au bon poste.' },
  { icone: Video, texte: 'Entretiens vidéo avec le candidat, sans rien lui faire installer.' },
  { icone: ShieldCheck, texte: 'Tout reste chiffré sur cet ordinateur.' },
];

export default function EcranPublic({ titre, sousTitre, children, largeur = 'max-w-sm' }) {
  const { theme } = useTheme();
  return (
    <div className="flex min-h-0 flex-1 bg-chrome">
      <main className="contenu-selectionnable flex min-w-0 flex-1 flex-col overflow-y-auto bg-fond px-12 py-10 lg:rounded-tr-2xl lg:border-t lg:border-r lg:border-trait">
        <div className={`m-auto w-full ${largeur}`}>
          <m.div
            initial={{ opacity: 0, transform: 'translateY(8px)' }}
            animate={{ opacity: 1, transform: 'translateY(0px)' }}
            transition={{ duration: 0.3, ease: COURBE_SORTIE }}
          >
            <img
              src={theme === 'clair' ? './marque/symbole-nuit-96.webp' : './marque/symbole-vert-96.webp'}
              alt=""
              width="40"
              height="40"
              className="mb-8 size-10"
            />
            <h1 className="titre-ecran text-3xl! leading-tight!">{titre}</h1>
            {sousTitre && <p className="mt-3 text-base text-doux">{sousTitre}</p>}
            <div className="mt-8">{children}</div>
          </m.div>
        </div>
        <p className="mx-auto mt-8 flex items-center gap-1.5 text-xs text-tenu">
          <ShieldCheck className="size-3.5" aria-hidden /> Vos données restent sur cet ordinateur.
        </p>
      </main>

      <aside className="relative hidden w-[46%] max-w-[640px] shrink-0 flex-col overflow-hidden px-12 py-12 lg:flex" aria-hidden>
        {/* Halo vert et symbole géant, en partie hors cadre */}
        <div className="pointer-events-none absolute -right-48 -bottom-56 size-[640px] rounded-full bg-[radial-gradient(closest-side,rgb(0_191_99/0.14),transparent)]" />
        <m.img
          src="./marque/symbole-vert-512.webp"
          alt=""
          width="560"
          height="560"
          className="pointer-events-none absolute -right-40 -bottom-48 size-[540px]"
          initial={{ opacity: 0, transform: 'rotate(-22.5deg) scale(0.92)' }}
          animate={{ opacity: 0.32, transform: 'rotate(0deg) scale(1)' }}
          transition={{ duration: 1.1, ease: COURBE_SORTIE, delay: 0.1 }}
        />
        <img
          src={theme === 'clair' ? './marque/logotype-nuit-128.webp' : './marque/logotype-blanc-128.webp'}
          alt=""
          height="28"
          className="relative h-7 w-auto self-start"
        />
        <div className="relative mt-20 max-w-sm">
          <p className="font-titres text-2xl leading-snug text-fort">
            Le tri des candidatures est fait. La décision vous appartient.
          </p>
          <ul className="mt-8 flex flex-col gap-4">
            {ATOUTS.map(({ icone: Icone, texte }) => (
              <li key={texte} className="flex items-start gap-3 text-base text-texte">
                <span className="grid size-7 shrink-0 place-items-center rounded-md border border-accent-trait bg-accent-doux text-accent-texte">
                  <Icone className="size-3.5" />
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
