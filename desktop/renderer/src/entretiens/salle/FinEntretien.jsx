// Écran d'un entretien terminé ou annulé : page claire et sobre (résumé, accès au compte-rendu), sans l'appareillage de la salle.
import { ArrowLeft, CalendarCheck, CircleCheck, CircleSlash, Clock, Film, ShieldCheck, Users } from 'lucide-react';
import { Link } from 'react-router-dom';
import { formaterDateHeure } from '../../format.js';
import { cx } from './elements.jsx';
import { SectionBilanRegard, SectionLivrables, SectionVigilance } from './panneaux.jsx';

const TRAIT = 1.5;

/** « 754 s » → « 12 min » ; « 3 840 s » → « 1 h 04 ». */
export function formaterDureeLongue(secondes) {
  if (secondes < 60) return 'Moins d’une minute';
  const h = Math.floor(secondes / 3600);
  const m = Math.floor((secondes % 3600) / 60);
  return h > 0 ? `${h} h ${String(m).padStart(2, '0')}` : `${m} min`;
}

const utc = (iso) => (/(Z|[+-]\d\d:?\d\d)$/.test(iso) ? iso : `${iso}Z`);

function Fait({ icone: Icone, libelle, children }) {
  return (
    <div className="flex items-start gap-3">
      <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-full bg-sal-surface text-sal-doux">
        <Icone className="size-[18px]" strokeWidth={TRAIT} aria-hidden />
      </span>
      <div className="min-w-0">
        <dt className="text-xs text-sal-doux">{libelle}</dt>
        <dd className="mt-0.5 text-sm font-medium text-sal-fort">{children}</dd>
      </div>
    </div>
  );
}

export default function FinEntretien({ entretien, nom, poste, erreur, rapportEnCours, onRapport, onExporter }) {
  const annule = entretien.statut === 'annule';
  const duree =
    entretien.debut_le && entretien.fin_le
      ? formaterDureeLongue((new Date(utc(entretien.fin_le)) - new Date(utc(entretien.debut_le))) / 1000)
      : null;
  const Icone = annule ? CircleSlash : CircleCheck;

  return (
    <div className="ecran-clair min-h-0 flex-1 overflow-y-auto bg-[#f8f9fa]">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-5 py-8 sm:px-8 sm:py-12">
        <Link
          to={`/candidatures/${entretien.candidature_id}`}
          className="inline-flex w-fit items-center gap-1.5 rounded-md text-sm text-sal-corps transition-colors duration-200 hover:text-sal-fort"
        >
          <ArrowLeft className="size-4" strokeWidth={TRAIT} aria-hidden /> Retour à la fiche de {nom}
        </Link>

        <header className="flex flex-col items-center gap-3 text-center">
          <span className={cx('grid size-14 place-items-center rounded-full', annule ? 'bg-sal-surface text-sal-doux' : 'bg-meet/10 text-meet')}>
            <Icone className="size-7" strokeWidth={TRAIT} aria-hidden />
          </span>
          <h1 className="text-2xl font-medium tracking-tight text-sal-fort">{annule ? 'Entretien annulé' : 'Entretien terminé'}</h1>
          <p className="text-sm text-sal-corps">
            {annule ? 'Cet entretien a été annulé' : 'La salle a été fermée'} · {nom}
            {poste ? ` · ${poste}` : ''}
          </p>
        </header>

        {!annule && (
          <>
            <dl className="grid grid-cols-1 gap-5 rounded-2xl border border-sal-bord bg-white p-6 sm:grid-cols-2">
              {duree && <Fait icone={Clock} libelle="Durée">{duree}</Fait>}
              {entretien.fin_le && <Fait icone={CalendarCheck} libelle="Clôturé le">{formaterDateHeure(entretien.fin_le)}</Fait>}
              <Fait icone={Users} libelle="Participants">Vous et {nom}</Fait>
              <Fait icone={Film} libelle="Enregistrement">{entretien.enregistrement ? 'Conservé, chiffré' : 'Aucun enregistrement'}</Fait>
              <Fait icone={ShieldCheck} libelle="Consentement du candidat">{entretien.consentement_enregistrement ? 'Donné' : 'Non donné'}</Fait>
            </dl>

            {erreur && <p role="alert" className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">{erreur}</p>}

            <div className="flex flex-wrap items-center justify-center gap-3">
              <button
                type="button"
                onClick={() => document.getElementById('compte-rendu')?.scrollIntoView({ behavior: 'smooth' })}
                className="rounded-full bg-meet px-6 py-2.5 text-sm font-medium text-white transition-colors duration-200 hover:bg-meet-700"
              >
                Voir le compte-rendu
              </button>
              <Link
                to="/candidatures"
                className="rounded-full border border-sal-bord bg-white px-6 py-2.5 text-sm font-medium text-sal-fort transition-colors duration-200 hover:bg-sal-surface"
              >
                Retourner aux candidatures
              </Link>
            </div>

            <section id="compte-rendu" aria-label="Compte-rendu de l'entretien" className="scroll-mt-6">
              <h2 className="mb-3 text-lg font-medium text-sal-fort">Compte-rendu</h2>
              <div className="overflow-hidden rounded-2xl border border-sal-bord bg-white">
                <SectionLivrables entretien={entretien} rapportEnCours={rapportEnCours} onRapport={onRapport} onExporter={onExporter} />
                <SectionBilanRegard entretien={entretien} />
                <SectionVigilance entretien={entretien} />
              </div>
            </section>
          </>
        )}

        {annule && (
          <div className="flex justify-center">
            <Link to="/candidatures" className="rounded-full border border-sal-bord bg-white px-6 py-2.5 text-sm font-medium text-sal-fort transition-colors duration-200 hover:bg-sal-surface">
              Retourner aux candidatures
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
