import { useAgent } from '../agent/ContexteAgent.jsx';
import ConnexionBoite from '../agent/ConnexionBoite.jsx';
import Demarrage from '../agent/Demarrage.jsx';
import Reglages from '../agent/Reglages.jsx';
import { Alerte, Chargement, EnTetePage } from '../components/ui.jsx';

/** Boîte mail de recrutement : liaison, premier réglage, puis compte et réglages de l'agent. */
export default function BoiteMail() {
  const { statut, erreur } = useAgent();
  if (!statut) return erreur ? <Alerte>{erreur}</Alerte> : <Chargement />;

  const ecran = !statut.connected ? 'connexion' : statut.needs_setup ? 'demarrage' : 'reglages';
  const descriptions = {
    connexion: "Liez la boîte mail qui reçoit les candidatures : l'agent INJARA y récupérera les CV automatiquement.",
    demarrage: 'Dernière étape : choisissez les candidatures à reprendre.',
    reglages: "L'agent INJARA récupère les CV reçus en pièce jointe (PDF et DOCX), sans jamais créer de doublon.",
  };
  return (
    <>
      <EnTetePage titre="Boîte mail" description={descriptions[ecran]} />
      {ecran === 'connexion' && <ConnexionBoite />}
      {ecran === 'demarrage' && <Demarrage />}
      {ecran === 'reglages' && <Reglages />}
    </>
  );
}
