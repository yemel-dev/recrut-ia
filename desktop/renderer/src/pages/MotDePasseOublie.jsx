import { KeyRound, LockKeyhole } from 'lucide-react';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api.js';
import CleRecuperation from '../components/CleRecuperation.jsx';
import EcranPublic from '../components/EcranPublic.jsx';
import { Alerte, Bouton, Champ, MotDePasse, Saisie } from '../components/ui.jsx';
import { useSession } from '../session.jsx';
import { aideMotDePasse, verifierMotDePasse } from '../motDePasse.js';

export default function MotDePasseOublie() {
  const navigate = useNavigate();
  const { rafraichir } = useSession();
  const [cleSaisie, setCleSaisie] = useState('');
  const [motDePasse, setMotDePasse] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [erreurs, setErreurs] = useState({});
  const [erreurGenerale, setErreurGenerale] = useState('');
  const [envoi, setEnvoi] = useState(false);
  const [nouvelleCle, setNouvelleCle] = useState(null);

  const soumettre = async (e) => {
    e.preventDefault();
    setErreurGenerale('');
    const { mot_de_passe, confirmation: errConfirmation } = verifierMotDePasse(motDePasse, confirmation);
    const locales = {};
    if (!cleSaisie.trim()) locales.cle_de_recuperation = 'Saisissez votre clé de récupération.';
    if (mot_de_passe) locales.nouveau_mot_de_passe = mot_de_passe;
    if (errConfirmation) locales.confirmation = errConfirmation;
    setErreurs(locales);
    if (Object.keys(locales).length) return;

    setEnvoi(true);
    try {
      const reponse = await api.post('/auth/recuperation', { cle_de_recuperation: cleSaisie, nouveau_mot_de_passe: motDePasse });
      setCleSaisie('');
      setMotDePasse('');
      setConfirmation('');
      setNouvelleCle(reponse.cle_de_recuperation);
    } catch (err) {
      setErreurs(err.champs);
      if (!Object.keys(err.champs).length) setErreurGenerale(err.message);
    } finally {
      setEnvoi(false);
    }
  };

  if (nouvelleCle) {
    return (
      <EcranPublic
        titre="Mot de passe modifié"
        sousTitre="Votre ancienne clé de récupération n'est plus valable. Voici la nouvelle."
        largeur="max-w-md"
      >
        <CleRecuperation
          cle={nouvelleCle}
          onContinuer={async () => {
            await rafraichir();
            navigate('/connexion', { replace: true });
          }}
        />
      </EcranPublic>
    );
  }

  return (
    <EcranPublic
      titre="Mot de passe oublié"
      sousTitre="Saisissez la clé de récupération reçue à la création du compte, puis choisissez un nouveau mot de passe."
    >
      <form onSubmit={soumettre} noValidate className="flex flex-col gap-5">
        <Alerte>{erreurGenerale}</Alerte>
        <Champ label="Clé de récupération" icone={KeyRound} erreur={erreurs.cle_de_recuperation} aide="Format : XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX" obligatoire>
          {(a) => (
            <Saisie
              {...a}
              autoFocus
              autoComplete="off"
              spellCheck={false}
              className="font-mono uppercase"
              value={cleSaisie}
              onChange={(e) => setCleSaisie(e.target.value)}
            />
          )}
        </Champ>
        <Champ label="Nouveau mot de passe" icone={LockKeyhole} erreur={erreurs.nouveau_mot_de_passe} aide={aideMotDePasse(motDePasse)} obligatoire>
          {(a) => <MotDePasse {...a} autoComplete="new-password" value={motDePasse} onChange={(e) => setMotDePasse(e.target.value)} />}
        </Champ>
        <Champ label="Confirmer le nouveau mot de passe" icone={LockKeyhole} erreur={erreurs.confirmation} obligatoire>
          {(a) => <MotDePasse {...a} autoComplete="new-password" value={confirmation} onChange={(e) => setConfirmation(e.target.value)} />}
        </Champ>
        <Bouton type="submit" taille="lg" chargement={envoi} className="mt-2">Changer le mot de passe</Bouton>
        <Link to="/connexion" className="self-center text-sm font-medium text-accent-texte underline-offset-4 hover:underline">
          Retour à la connexion
        </Link>
      </form>
    </EcranPublic>
  );
}
