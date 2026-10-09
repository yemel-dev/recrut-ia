// Barre supérieure (identité, candidat, état) et barre de commandes (style visioconférence) de la salle.
import { ArrowLeft, Circle, DoorClosed, DoorOpen, Mic, MicOff, PanelRightClose, PanelRightOpen, PhoneOff, Play, Video, VideoOff } from 'lucide-react';
import { Link } from 'react-router-dom';
import { STATUTS_ENTRETIEN } from '../../constantes.js';
import { formaterDateHeure } from '../../format.js';
import { cx } from './elements.jsx';
import { INDICATEURS } from './phase.js';

export function BarreSuperieure({ entretien, nom, poste, phase, duree, enregistrement, panneauOuvert, onPanneau }) {
  const [libelle, voyant] = INDICATEURS[phase];
  const PanneauIcone = panneauOuvert ? PanelRightClose : PanelRightOpen;
  return (
    <header className="flex items-center gap-3 px-1 text-white">
      <Link
        to={`/candidatures/${entretien.candidature_id}`}
        className="inline-flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-2 text-sm font-medium text-white/70 transition-colors hover:bg-white/10 hover:text-white"
        title={`Retour à la fiche de ${nom}`}
      >
        <ArrowLeft className="size-4" aria-hidden />
        <span className="hidden sm:inline">Fiche</span>
        <span className="sr-only sm:hidden">Retour à la fiche de {nom}</span>
      </Link>
      <div className="hidden h-6 w-px bg-white/15 sm:block" aria-hidden />
      <div className="flex min-w-0 flex-1 flex-col">
        <h1 className="truncate text-base leading-tight font-semibold tracking-tight">{nom}</h1>
        <p className="truncate text-xs text-white/55">
          {poste ? `${poste} · ` : ''}
          {STATUTS_ENTRETIEN[entretien.statut]}
          {entretien.statut === 'planifie' && entretien.date_entretien && ` · prévu le ${formaterDateHeure(entretien.date_entretien)}`}
        </p>
      </div>
      {enregistrement === 'actif' && (
        <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-danger/15 px-3 py-1 text-xs font-semibold text-sal-danger ring-1 ring-danger/30">
          <Circle className="size-2.5 animate-pulse fill-current" aria-hidden /> <span className="hidden sm:inline">Enregistrement</span><span className="sm:hidden">REC</span>
        </span>
      )}
      {duree && <span className="shrink-0 font-mono text-sm tabular-nums text-white/80" aria-label={`Durée de l'entretien ${duree}`}>{duree}</span>}
      <span className="inline-flex shrink-0 items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-medium" role="status">
        <span className={cx('size-2 rounded-full', voyant)} aria-hidden />
        <span className="hidden md:inline">{libelle}</span>
        <span className="sr-only md:hidden">{libelle}</span>
      </span>
      <button
        type="button"
        onClick={onPanneau}
        aria-pressed={panneauOuvert}
        aria-label={panneauOuvert ? 'Masquer le panneau latéral' : 'Afficher le panneau latéral'}
        title={panneauOuvert ? 'Masquer le panneau' : 'Afficher le panneau'}
        className="grid size-10 shrink-0 place-items-center rounded-lg text-white/75 transition-colors hover:bg-white/10 hover:text-white"
      >
        <PanneauIcone className="size-5" aria-hidden />
      </button>
    </header>
  );
}

/** Bouton rond de la barre de commandes, avec infobulle (survol et focus clavier). */
function Commande({ icone: Icone, libelle, actif = true, variante = 'neutre', badge, className, ...props }) {
  const styles = {
    neutre: 'bg-white/10 text-white hover:bg-white/20',
    coupe: 'bg-danger-plein text-white hover:brightness-110',
    selection: 'bg-accent/20 text-vert-100 ring-1 ring-accent/50 hover:bg-accent/30',
  };
  return (
    <span className="group relative">
      <button
        type="button"
        aria-label={libelle}
        {...props}
        className={cx(
          'relative grid size-12 place-items-center rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-40',
          styles[variante],
          className,
        )}
      >
        <Icone className="size-5" aria-hidden />
        {badge > 0 && (
          <span className="absolute -top-1 -right-1 grid min-w-5 place-items-center rounded-full bg-alerte px-1 text-[11px] font-bold text-nuit-950">{badge}</span>
        )}
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 mb-2 -translate-x-1/2 rounded-md bg-black/85 px-2 py-1 text-xs whitespace-nowrap text-white opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100"
      >
        {libelle}
      </span>
    </span>
  );
}

export function BarreCommandes({ entretien, salle, occupe, onOuvrirSalle, onDemarrer, onTerminer, onChoisirOnglet, onglets, ongletActif, panneauOuvert }) {
  const enCours = entretien.statut === 'en_cours';
  const planifie = entretien.statut === 'planifie';
  const salleOuverte = salle.etat === 'ouverte';

  return (
    <div className="flex items-center justify-center px-1">
      {/* Commandes */}
      <div className="flex flex-wrap items-center justify-center gap-2.5 rounded-full bg-nuit-800/90 px-3 py-2 shadow-xl ring-1 ring-white/10 backdrop-blur" role="toolbar" aria-label="Commandes de la salle">
        <>
          <Commande
            icone={salle.microActif ? Mic : MicOff}
            libelle={salle.microActif ? 'Couper le micro' : 'Réactiver le micro'}
            variante={salle.microActif ? 'neutre' : 'coupe'}
            disabled={!salleOuverte}
            aria-pressed={!salle.microActif}
            onClick={salle.basculerMicro}
          />
          <Commande
            icone={salle.cameraActive ? Video : VideoOff}
            libelle={salle.cameraActive ? 'Couper la caméra' : 'Réactiver la caméra'}
            variante={salle.cameraActive ? 'neutre' : 'coupe'}
            disabled={!salleOuverte}
            aria-pressed={!salle.cameraActive}
            onClick={salle.basculerCamera}
          />
          <span className="mx-1 h-7 w-px bg-white/15" aria-hidden />
          {salleOuverte ? (
            <Commande
              icone={DoorClosed}
              libelle={enCours ? "Terminez l'entretien d'abord pour fermer la salle" : 'Fermer la salle'}
              disabled={enCours}
              onClick={salle.fermer}
            />
          ) : (
            <Commande icone={DoorOpen} libelle="Ouvrir la salle" variante="selection" disabled={salle.etat === 'ouverture'} onClick={onOuvrirSalle} />
          )}
          {planifie && (
            <button
              type="button"
              onClick={onDemarrer}
              disabled={occupe || !salleOuverte || !salle.candidatConnecte}
              title={!salleOuverte ? "Ouvrez la salle d'abord" : !salle.candidatConnecte ? 'Disponible dès que le candidat est connecté' : undefined}
              className="inline-flex h-12 items-center gap-2 rounded-full bg-accent px-5 text-sm font-semibold text-sur-accent shadow-halo transition-colors hover:bg-accent-survol disabled:cursor-not-allowed disabled:bg-accent/25 disabled:text-white/50 disabled:shadow-none"
            >
              <Play className="size-4 fill-current" aria-hidden /> Démarrer l'entretien
            </button>
          )}
          {enCours && (
            <button
              type="button"
              onClick={onTerminer}
              className="inline-flex h-12 items-center gap-2 rounded-full bg-danger-plein px-5 text-sm font-semibold text-white transition-[filter] hover:brightness-110"
            >
              <PhoneOff className="size-4" aria-hidden /> Terminer l'entretien
            </button>
          )}
        </>
        <span className="mx-1 h-7 w-px bg-white/15" aria-hidden />
        {onglets.map(({ id, libelle, icone: Icone, badge }) => (
          <Commande
            key={id}
            icone={Icone}
            libelle={libelle}
            variante={panneauOuvert && ongletActif === id ? 'selection' : 'neutre'}
            aria-pressed={panneauOuvert && ongletActif === id}
            badge={badge}
            onClick={() => onChoisirOnglet(id)}
          />
        ))}
      </div>

    </div>
  );
}
