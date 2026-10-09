// Panneau latéral repliable : colonne à droite sur grand écran, tiroir superposé sur fenêtre étroite.
import { Circle, X } from 'lucide-react';
import { formaterDateHeure } from '../../format.js';
import { STATUTS_ENTRETIEN } from '../../constantes.js';
import { cx, Corps, Discret, Ligne, Section } from './elements.jsx';
import { SectionBilanRegard, SectionInvitation, SectionLivrables, SectionRegard, SectionVigilance } from './panneaux.jsx';

function SectionDetails({ entretien, enregistrement, salle }) {
  const consentement = entretien.consentement_enregistrement;
  return (
    <Section titre="Informations" icone={Circle}>
      <dl className="divide-y divide-white/5">
        <Ligne libelle="Statut">{STATUTS_ENTRETIEN[entretien.statut]}</Ligne>
        {entretien.date_entretien && <Ligne libelle="Prévu le">{formaterDateHeure(entretien.date_entretien)}</Ligne>}
        {entretien.debut_le && <Ligne libelle="Commencé le">{formaterDateHeure(entretien.debut_le)}</Ligne>}
        {entretien.fin_le && <Ligne libelle="Terminé le">{formaterDateHeure(entretien.fin_le)}</Ligne>}
        <Ligne libelle="Consentement"><span className={consentement ? 'text-brand-500' : 'text-amber-300'}>{consentement ? 'Donné' : 'Pas encore donné'}</span></Ligne>
        <Ligne libelle="Enregistrement">
          {enregistrement === 'actif' ? <span className="text-red-300">En cours</span> : enregistrement === 'erreur' ? <span className="text-red-300">En erreur</span> : entretien.enregistrement ? 'Conservé (chiffré)' : 'Aucun'}
        </Ligne>
        <Ligne libelle="Salle">{salle.etat === 'ouverte' ? 'Ouverte' : salle.etat === 'ouverture' ? 'Ouverture…' : 'Fermée'}</Ligne>
      </dl>
      <Corps>
        {consentement
          ? "Le candidat a consenti à l'enregistrement : il démarre avec l'entretien et reste sur cet ordinateur, chiffré."
          : "Le candidat n'a pas (encore) consenti à l'enregistrement : l'entretien ne sera pas enregistré."}
      </Corps>
      {['planifie', 'en_cours'].includes(entretien.statut) && <Discret>Le consentement est relu toutes les quelques secondes tant que l'entretien est ouvert.</Discret>}
    </Section>
  );
}

export default function PanneauLateral({ onglet, onglets, onChoisir, onFermer, entretien, regard, enregistrement, salle, rapportEnCours, onRapport, onExporter }) {
  const ouvert = ['planifie', 'en_cours'].includes(entretien.statut);
  const termine = entretien.statut === 'termine';
  const actif = onglets.find((o) => o.id === onglet) ?? onglets[0];

  return (
    <>
      {/* Voile derrière le tiroir, sur fenêtre étroite seulement */}
      <button type="button" aria-label="Fermer le panneau" onClick={onFermer} className="fixed inset-0 z-20 cursor-default bg-black/50 lg:hidden" tabIndex={-1} />
      <aside
        aria-label={actif.libelle}
        className={cx(
          'glisser-entree z-30 flex flex-col overflow-hidden bg-nuit-900 ring-1 ring-white/10',
          'fixed inset-y-0 right-0 w-full max-w-sm shadow-2xl',
          'lg:static lg:inset-auto lg:w-96 lg:max-w-none lg:shrink-0 lg:rounded-2xl lg:shadow-none',
        )}
      >
        <div className="flex items-center gap-1 border-b border-white/10 px-3 py-2.5">
          <div role="tablist" aria-label="Sections du panneau" className="flex flex-1 gap-1 overflow-x-auto">
            {onglets.map(({ id, libelle, icone: Icone, badge }) => (
              <button
                key={id}
                type="button"
                role="tab"
                id={`onglet-${id}`}
                aria-selected={id === actif.id}
                aria-controls="contenu-panneau"
                onClick={() => onChoisir(id)}
                className={cx(
                  'inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium whitespace-nowrap transition-colors',
                  id === actif.id ? 'bg-white/10 text-white' : 'text-white/60 hover:bg-white/5 hover:text-white',
                )}
              >
                <Icone className="size-4" aria-hidden /> {libelle}
                {badge > 0 && <span className="rounded-full bg-amber-400 px-1.5 text-[11px] font-bold text-nuit-950">{badge}</span>}
              </button>
            ))}
          </div>
          <button type="button" onClick={onFermer} aria-label="Fermer le panneau" className="grid size-9 shrink-0 place-items-center rounded-lg text-white/70 hover:bg-white/10 hover:text-white">
            <X className="size-5" aria-hidden />
          </button>
        </div>
        <div id="contenu-panneau" role="tabpanel" aria-labelledby={`onglet-${actif.id}`} className="min-h-0 flex-1 overflow-y-auto">
          {actif.id === 'invitation' && ouvert && <SectionInvitation entretien={entretien} />}
          {actif.id === 'suivi' && (
            <>
              {entretien.statut === 'en_cours' ? (
                <SectionRegard regard={regard} consentement={entretien.consentement_enregistrement} />
              ) : (
                <Section titre="Suivi en direct" icone={Circle}>
                  <Corps>Le regard et la vigilance du candidat s'affichent ici pendant l'entretien.</Corps>
                </Section>
              )}
              <SectionVigilance entretien={entretien} />
            </>
          )}
          {actif.id === 'bilan' && termine && (
            <>
              <SectionLivrables entretien={entretien} rapportEnCours={rapportEnCours} onRapport={onRapport} onExporter={onExporter} />
              <SectionBilanRegard entretien={entretien} />
              <SectionVigilance entretien={entretien} />
            </>
          )}
          {actif.id === 'details' && <SectionDetails entretien={entretien} enregistrement={enregistrement} salle={salle} />}
        </div>
      </aside>
    </>
  );
}
