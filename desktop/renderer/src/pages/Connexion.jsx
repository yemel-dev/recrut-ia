import { useState } from 'react';
import { LockKeyhole, Mail } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import EcranPublic from '../components/EcranPublic.jsx';
import { Alerte, Bouton, Champ, MotDePasse, Saisie } from '../components/ui.jsx';
import { useSession } from '../session.jsx';

export default function Connexion() {
  const navigate = useNavigate();
  const { connecter } = useSession();
  const [email, setEmail] = useState('');
  const [motDePasse, setMotDePasse] = useState('');
  const [erreur, setErreur] = useState('');
  const [envoi, setEnvoi] = useState(false);

  const soumettre = async (e) => {
    e.preventDefault();
    if (!email.trim() || !motDePasse) {
      setErreur('Saisissez votre email et votre mot de passe.');
      return;
    }
    setErreur('');
    setEnvoi(true);
    try {
      await connecter(email.trim(), motDePasse);
      navigate('/', { replace: true });
    } catch (err) {
      setErreur(err.message);
      setMotDePasse('');
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <EcranPublic accroche="Bon retour" titre="Connexion" sousTitre="Accédez à l'espace recrutement de votre entreprise.">
      <form onSubmit={soumettre} noValidate className="flex flex-col gap-5">
        <Alerte>{erreur}</Alerte>
        <Champ label="Email" icone={Mail}>
          {(a) => <Saisie {...a} type="email" autoComplete="username" autoFocus value={email} onChange={(e) => setEmail(e.target.value)} />}
        </Champ>
        <Champ label="Mot de passe" icone={LockKeyhole}>
          {(a) => <MotDePasse {...a} autoComplete="current-password" value={motDePasse} onChange={(e) => setMotDePasse(e.target.value)} />}
        </Champ>
        <Bouton type="submit" taille="lg" chargement={envoi} className="mt-2">Se connecter</Bouton>
        <Link to="/mot-de-passe-oublie" className="self-center text-sm font-medium text-accent-texte underline-offset-4 hover:underline">
          Mot de passe oublié ?
        </Link>
      </form>
    </EcranPublic>
  );
}
