import { useState } from 'react';
import { useAgent } from '../agent/ContexteAgent.jsx';
import ConnexionSimple from '../agent/ConnexionSimple.jsx';
import Demarrage from '../agent/Demarrage.jsx';
import Reglages from '../agent/Reglages.jsx';
import { Alerte, Carte, Chargement, EnTetePage } from '../components/ui.jsx';

/** Boîte mail de recrutement : liaison, premier réglage, puis compte et réglages de l'agent. */
export default function BoiteMail() {
  const { statut, erreur } = useAgent();
  if (!statut) return erreur ? <Alerte>{erreur}</Alerte> : <Chargement />;

  const ecran = !statut.connected ? 'connexion' : statut.needs_setup ? 'demarrage' : 'reglages';
  const descriptions = {
    connexion: "Connectez la boîte qui reçoit les candidatures : INJARA y récupère les CV et s'en sert pour répondre aux candidats.",
    demarrage: 'Dernière étape : choisissez les candidatures à reprendre.',
    reglages: "L'agent INJARA récupère les CV reçus en pièce jointe (PDF et DOCX), sans jamais créer de doublon.",
  };
  return (
    <>
      <EnTetePage titre="Boîte mail" description={descriptions[ecran]} />
      {ecran === 'connexion' && <Connexion />}
      {ecran === 'demarrage' && <Demarrage />}
      {ecran === 'reglages' && <Reglages />}
    </>
  );
}

function Connexion() {
  const { etat, rafraichir, notifier } = useAgent();
  const [erreur, setErreur] = useState('');

  const importerIdentifiants = async () => {
    setErreur('');
    const reponse = await window.injara.fichiers.importerIdentifiantsGoogle();
    if (reponse.annule) return;
    if (!reponse.ok) setErreur(reponse.donnees?.champs?.fichier || reponse.donnees?.detail || 'Fichier refusé.');
    else notifier('Connexion avec Google activée sur cet ordinateur.', 'succes');
    await rafraichir();
  };

  return (
    <div className="flex max-w-xl flex-col gap-4">
      <Carte>
        <ConnexionSimple
          onConnecte={(e) => {
            const envoiPret = e.envoi?.autorise || e.envoi?.simule;
            notifier(envoiPret ? 'Boîte connectée : réception des CV et mails aux candidats prêts.' : `Boîte connectée. Mails aux candidats : ${e.envoi?.motif}`, envoiPret ? 'succes' : 'info');
          }}
        />
      </Carte>
      <Alerte>{erreur}</Alerte>
      {etat?.mode === 'real' && !etat.identifiants_google && (
        <p className="text-sm text-tenu">
          Administrateur :{' '}
          <button type="button" onClick={importerIdentifiants} className="underline underline-offset-4 hover:text-fort">
            activer la connexion avec Google sur cet ordinateur
          </button>{' '}
          (fichier d'identifiants de l'application).
        </p>
      )}
    </div>
  );
}
