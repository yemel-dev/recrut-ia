// Liste des raccourcis clavier (touche « ? » ou palette de commandes).
import { useEffect, useRef } from 'react';
import { MODIFICATEUR } from '../../commandes.js';
import { Bouton, Touche } from '../ui.jsx';

const RACCOURCIS = [
  ['Ouvrir la palette de commandes', [MODIFICATEUR, 'K']],
  ['Tableau de bord', [MODIFICATEUR, '1']],
  ['Candidatures', [MODIFICATEUR, '2']],
  ['Postes', [MODIFICATEUR, '3']],
  ['Boîte mail', [MODIFICATEUR, '4']],
  ['Profil entreprise', [MODIFICATEUR, '5']],
  ['Mails aux candidats', [MODIFICATEUR, '6']],
  ['Créer un poste', [MODIFICATEUR, 'N']],
  ['Importer des CV', [MODIFICATEUR, 'I']],
  ['Replier la barre latérale', [MODIFICATEUR, 'B']],
  ['Menu d’une ligne (liste des candidatures)', ['Maj', 'F10']],
  ['Afficher cette aide', ['?']],
];

export default function AideRaccourcis({ ouverte, onFermer }) {
  const dialogue = useRef(null);
  useEffect(() => {
    const d = dialogue.current;
    if (ouverte && !d.open) d.showModal();
    if (!ouverte && d.open) d.close();
  }, [ouverte]);
  return (
    <dialog
      ref={dialogue}
      aria-labelledby="titre-raccourcis"
      onClose={onFermer}
      onClick={(e) => e.target === e.currentTarget && onFermer()}
      className="modale-native m-auto w-full max-w-md rounded-xl border border-trait-fort bg-surface-2 p-0 text-texte shadow-flottante"
    >
      <div className="p-6">
        <h2 id="titre-raccourcis" className="titre-section">Raccourcis clavier</h2>
        <p className="mt-1 text-sm text-doux">Désactivés pendant un entretien vidéo, pour ne pas quitter la salle par erreur.</p>
        <dl className="mt-5 divide-y divide-trait">
          {RACCOURCIS.map(([libelle, touches]) => (
            <div key={libelle} className="flex items-center justify-between gap-4 py-2 text-base">
              <dt className="text-texte">{libelle}</dt>
              <dd className="flex gap-1">{touches.map((t) => <Touche key={t}>{t}</Touche>)}</dd>
            </div>
          ))}
        </dl>
      </div>
      <div className="flex justify-end border-t border-trait bg-survol px-6 py-3.5">
        <Bouton variante="secondaire" onClick={onFermer} autoFocus>Fermer</Bouton>
      </div>
    </dialog>
  );
}
