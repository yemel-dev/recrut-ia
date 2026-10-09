// Zone vidéo de la salle : vidéo du candidat en grand, aperçu du recruteur en vignette, écrans d'état par-dessus.
// Les deux éléments <video> restent toujours montés : l'analyse du regard et l'enregistrement s'y accrochent.
import { Check, CircleDashed, DoorClosed, Loader2, MicOff, TriangleAlert, UserRound, UserPlus, Video, VideoOff } from 'lucide-react';
import { BoutonSalle, cx } from './elements.jsx';

function Etape({ fait, encours, children }) {
  const Icone = fait ? Check : encours ? Loader2 : CircleDashed;
  return (
    <li className={cx('flex items-center gap-3', fait ? 'text-white' : 'text-white/55')}>
      <span className={cx('grid size-6 shrink-0 place-items-center rounded-full', fait ? 'bg-accent text-nuit-950' : 'bg-white/10')}>
        <Icone className={cx('size-3.5', encours && !fait && 'animate-spin')} aria-hidden />
      </span>
      {children}
    </li>
  );
}

/** Carte centrée des écrans d'état. */
function Ecran({ icone: Icone, titre, children, actions, ton = 'neutre' }) {
  return (
    <div className="apparition absolute inset-0 grid place-items-center overflow-y-auto bg-gradient-to-b from-nuit-800 to-nuit-950 p-6 pb-32 sm:pb-28">
      <div className="flex w-full max-w-md flex-col items-center gap-5 py-10 text-center">
        <span className={cx('grid size-20 place-items-center rounded-full ring-1', ton === 'alerte' ? 'bg-danger/10 text-sal-danger ring-danger/30' : 'bg-accent/10 text-vert-400 ring-accent/30 shadow-halo')}>
          <Icone className={cx('size-9', Icone === Loader2 && 'animate-spin')} aria-hidden />
        </span>
        <h2 className="text-xl font-semibold tracking-tight text-white">{titre}</h2>
        <div className="flex w-full flex-col items-center gap-4 text-sm leading-relaxed text-white/70">{children}</div>
        {actions && <div className="flex flex-wrap justify-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}

export default function Scene({ phase, nom, entretien, salle, refDistant, refLocal, onOuvrir, onInviter, onAide }) {
  const ouverte = salle.etat === 'ouverte';
  const consentement = entretien.consentement_enregistrement;
  const enCours = entretien.statut === 'en_cours';
  const videoVisible = phase === 'connecte' || phase === 'interrompue';

  return (
    <div className="relative min-h-0 flex-1 overflow-hidden rounded-2xl bg-nuit-950 ring-1 ring-white/10">
      <video ref={refDistant} autoPlay playsInline aria-label={`Vidéo de ${nom}`} className={cx('absolute inset-0 size-full object-contain transition-opacity', videoVisible ? 'opacity-100' : 'opacity-0')} />

      {phase === 'connecte' && (
        <span className="apparition absolute top-3 left-3 rounded-md bg-black/55 px-2.5 py-1 text-xs font-medium text-white backdrop-blur">{nom}</span>
      )}

      {phase === 'fermee' && (
        <Ecran
          icone={DoorClosed}
          titre="La salle est fermée"
          actions={<BoutonSalle variante="plein" icone={Video} onClick={onOuvrir} className="px-5 py-2.5">Ouvrir la salle</BoutonSalle>}
        >
          <p>Ouvrez la salle pour activer votre caméra et votre micro, puis invitez {nom} à vous rejoindre.</p>
        </Ecran>
      )}

      {phase === 'ouverture' && (
        <Ecran icone={Loader2} titre="Ouverture de la salle…">
          <p>Accès à votre caméra et à votre micro, puis connexion au service d'entretien.</p>
        </Ecran>
      )}

      {phase === 'attente' && (
        <Ecran
          icone={UserRound}
          titre={enCours ? `${nom} s'est déconnecté(e)` : `En attente de ${nom}`}
          actions={
            <>
              <BoutonSalle variante="plein" icone={UserPlus} onClick={onInviter}>Inviter le candidat</BoutonSalle>
              <BoutonSalle variante="discret" onClick={onAide}>Un problème de connexion ?</BoutonSalle>
            </>
          }
        >
          <p>{enCours ? 'La vidéo reprendra automatiquement dès que le candidat rouvrira son lien.' : 'Le candidat apparaît ici dès qu’il ouvre son lien. Vous pouvez patienter dans la salle.'}</p>
          <ul className="flex w-full max-w-xs flex-col gap-2.5 rounded-xl bg-white/5 px-5 py-4 text-left ring-1 ring-white/10">
            <Etape fait>Salle ouverte, caméra et micro prêts</Etape>
            <Etape encours>Candidat connecté à la salle</Etape>
            <Etape>Vidéo reçue</Etape>
            <li className="border-t border-white/10 pt-2.5 text-xs text-white/60">
              {consentement ? 'Le candidat a donné son consentement.' : 'Consentement du candidat : pas encore donné.'}
            </li>
          </ul>
        </Ecran>
      )}

      {phase === 'negociation' && (
        <Ecran
          icone={Loader2}
          titre={`${nom} est dans la salle`}
          actions={<BoutonSalle variante="discret" onClick={onAide}>Ça dure trop longtemps ?</BoutonSalle>}
        >
          <p>Connexion de la vidéo en cours. Cela prend généralement quelques secondes.</p>
          <ul className="flex w-full max-w-xs flex-col gap-2.5 rounded-xl bg-white/5 px-5 py-4 text-left ring-1 ring-white/10">
            <Etape fait>Salle ouverte, caméra et micro prêts</Etape>
            <Etape fait>Candidat connecté à la salle</Etape>
            <Etape encours>Vidéo reçue</Etape>
          </ul>
        </Ecran>
      )}

      {phase === 'interrompue' && (
        <div className="apparition absolute inset-x-0 top-0 z-10 flex flex-wrap items-center justify-center gap-3 bg-danger-plein/90 px-4 py-2.5 text-sm font-medium text-white backdrop-blur">
          <TriangleAlert className="size-4" aria-hidden />
          Connexion interrompue : la vidéo peut reprendre d'elle-même. Sinon, le candidat peut recharger sa page.
          <button type="button" onClick={onAide} className="rounded-md bg-white/20 px-2.5 py-1 text-xs font-semibold hover:bg-white/30">Aide</button>
        </div>
      )}

      {/* Aperçu du recruteur : visible tant que la salle est ouverte ; l'effet miroir ne concerne que cet aperçu. */}
      <div
        className={cx(
          'absolute right-3 bottom-3 z-10 aspect-video w-1/4 min-w-32 max-w-60 overflow-hidden rounded-xl bg-nuit-900 shadow-xl ring-1 ring-white/25 transition-opacity',
          ouverte ? 'opacity-100' : 'pointer-events-none opacity-0',
        )}
      >
        <video ref={refLocal} autoPlay playsInline muted aria-label="Votre caméra" className="size-full -scale-x-100 object-cover" />
        {!salle.cameraActive && (
          <div className="absolute inset-0 grid place-items-center bg-nuit-900">
            <span className="grid size-12 place-items-center rounded-full bg-nuit-700 text-white"><VideoOff className="size-5" aria-label="Caméra coupée" /></span>
          </div>
        )}
        <span className="absolute bottom-1.5 left-1.5 flex items-center gap-1 rounded bg-black/55 px-1.5 py-0.5 text-[11px] font-medium text-white">
          {!salle.microActif && <MicOff className="size-3 text-sal-danger" aria-label="Micro coupé" />} Vous
        </span>
      </div>
    </div>
  );
}
