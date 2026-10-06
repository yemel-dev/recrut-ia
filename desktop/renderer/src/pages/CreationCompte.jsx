import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api.js';
import CleRecuperation from '../components/CleRecuperation.jsx';
import EcranPublic from '../components/EcranPublic.jsx';
import { Alerte, Bouton, Champ, MotDePasse, Saisie } from '../components/ui.jsx';
import { aideMotDePasse, verifierMotDePasse } from '../motDePasse.js';
import { useSession } from '../session.jsx';

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export default function CreationCompte() {
  const navigate = useNavigate();
  const { rafraichir } = useSession();
  const [email, setEmail] = useState('');
  const [motDePasse, setMotDePasse] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [erreurs, setErreurs] = useState({});
  const [erreurGenerale, setErreurGenerale] = useState('');
  const [envoi, setEnvoi] = useState(false);
  const [cle, setCle] = useState(null);

  const soumettre = async (e) => {
    e.preventDefault();
    setErreurGenerale('');
    const locales = verifierMotDePasse(motDePasse, confirmation);
    if (!EMAIL.test(email.trim())) locales.email = 'Adresse email invalide.';
    setErreurs(locales);
    if (Object.keys(locales).length) return;

    setEnvoi(true);
    try {
      const reponse = await api.post('/auth/compte', { email: email.trim(), mot_de_passe: motDePasse });
      setMotDePasse('');
      setConfirmation('');
      setCle(reponse.cle_de_recuperation);
    } catch (err) {
      setErreurs(err.champs);
      if (!Object.keys(err.champs).length) setErreurGenerale(err.message);
    } finally {
      setEnvoi(false);
    }
  };

  if (cle) {
    return (
      <EcranPublic titre="Votre compte est créé" sousTitre="Dernière étape : conservez votre clé de récupération." largeur="max-w-lg">
        <CleRecuperation
          cle={cle}
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
      titre="Bienvenue sur INJARA"
      sousTitre="Créez le compte de votre entreprise. Il protège l'accès à l'application sur cet ordinateur."
    >
      <form onSubmit={soumettre} noValidate className="flex flex-col gap-4">
        <Alerte>{erreurGenerale}</Alerte>
        <Champ label="Email" erreur={erreurs.email} obligatoire>
          {(a) => <Saisie {...a} type="email" autoComplete="username" autoFocus value={email} onChange={(e) => setEmail(e.target.value)} />}
        </Champ>
        <Champ label="Mot de passe" erreur={erreurs.mot_de_passe} aide={aideMotDePasse(motDePasse)} obligatoire>
          {(a) => <MotDePasse {...a} autoComplete="new-password" value={motDePasse} onChange={(e) => setMotDePasse(e.target.value)} />}
        </Champ>
        <Champ label="Confirmer le mot de passe" erreur={erreurs.confirmation} obligatoire>
          {(a) => <MotDePasse {...a} autoComplete="new-password" value={confirmation} onChange={(e) => setConfirmation(e.target.value)} />}
        </Champ>
        <Bouton type="submit" chargement={envoi} className="mt-2">Créer le compte</Bouton>
      </form>
    </EcranPublic>
  );
}
