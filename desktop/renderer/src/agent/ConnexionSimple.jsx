// Connexion de la boîte de recrutement en une fois : l'utilisateur donne son adresse, INJARA trouve le reste
// (backend/services/detection_boite.py) et ne demande que ce qui manque. La même connexion sert à lire les
// candidatures et à envoyer les mails aux candidats.
import { ArrowLeft, CheckCircle2, ExternalLink, Loader2, ShieldCheck, TriangleAlert } from 'lucide-react';
import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api.js';
import { Alerte, Bouton, Champ, MotDePasse, Saisie } from '../components/ui.jsx';
import { useAgent } from './ContexteAgent.jsx';

/** onConnecte(etat) : etat = { connectee, email, fournisseur, envoi } (GET /boite). */
export default function ConnexionSimple({ onConnecte, emailInitial = '' }) {
  const [email, setEmail] = useState(emailInitial);
  const [detection, setDetection] = useState(null);
  const [erreur, setErreur] = useState('');
  const [recherche, setRecherche] = useState(false);

  const continuer = async (e) => {
    e.preventDefault();
    setErreur('');
    if (!email.trim()) {
      setErreur("Saisissez l'adresse où vous recevez les candidatures.");
      return;
    }
    setRecherche(true);
    try {
      setDetection(await api.get(`/boite/detection?email=${encodeURIComponent(email.trim())}`));
    } catch (err) {
      setErreur(err.champs?.email || err.message);
    } finally {
      setRecherche(false);
    }
  };

  if (!detection) {
    return (
      <form onSubmit={continuer} noValidate className="flex flex-col gap-4">
        <Champ label="Adresse e-mail de recrutement" erreur={erreur} aide="L'adresse où les candidats envoient leur CV.">
          {(a) => (
            <Saisie {...a} type="email" autoFocus placeholder="recrutement@votre-entreprise.com" value={email} onChange={(e) => setEmail(e.target.value)} />
          )}
        </Champ>
        <Bouton type="submit" chargement={recherche} className="self-start">
          Continuer
        </Bouton>
        {recherche && <p className="text-sm text-doux">Recherche de votre messagerie…</p>}
      </form>
    );
  }

  const changer = () => setDetection(null);
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-trait bg-survol px-4 py-3 text-sm">
        <span>
          <strong className="text-fort">{detection.email}</strong>
          <span className="text-doux"> · {detection.fournisseur === 'votre hébergeur' ? 'messagerie de votre entreprise' : detection.fournisseur}</span>
        </span>
        <button type="button" onClick={changer} className="font-medium text-doux hover:text-fort hover:underline">
          Modifier l'adresse
        </button>
      </div>
      {detection.methode === 'impossible' && (
        <>
          <Alerte ton="alerte">{detection.avertissement}</Alerte>
          <Bouton variante="secondaire" icone={ArrowLeft} onClick={changer} className="self-start">Utiliser une autre adresse</Bouton>
        </>
      )}
      {detection.methode === 'google' && <ConnexionGoogle detection={detection} onConnecte={onConnecte} />}
      {detection.methode === 'mot_de_passe' && <ConnexionMotDePasse detection={detection} onConnecte={onConnecte} />}
    </div>
  );
}

function ConnexionGoogle({ detection, onConnecte }) {
  const { rafraichir } = useAgent();
  const [attente, setAttente] = useState(false);
  const [erreur, setErreur] = useState('');
  const tentative = useRef(0);

  const connecter = async () => {
    const numero = ++tentative.current;
    setErreur('');
    setAttente(true);
    try {
      const etat = await api.post('/boite/google', { email: detection.email });
      if (numero !== tentative.current) return;
      await rafraichir();
      onConnecte?.(etat);
    } catch (err) {
      if (numero === tentative.current) setErreur(err.message);
    } finally {
      if (numero === tentative.current) setAttente(false);
    }
  };

  if (attente) {
    return (
      <div className="flex flex-col gap-3 rounded-lg border border-trait bg-survol p-4 text-sm text-texte">
        <p className="flex items-center gap-2 font-semibold">
          <Loader2 className="size-4 animate-spin" aria-hidden /> En attente de Google…
        </p>
        <p>
          Votre navigateur vient de s'ouvrir. Choisissez le compte <strong>{detection.email}</strong>, puis cliquez sur « Continuer »
          jusqu'à la fin. Revenez ensuite ici.
        </p>
        <p className="text-doux">
          Si Google affiche « Google n'a pas validé cette application », cliquez sur « Paramètres avancés », puis sur « Continuer ».
        </p>
        <Bouton
          variante="secondaire"
          className="self-start"
          onClick={() => {
            tentative.current += 1; // la réponse tardive sera ignorée
            setAttente(false);
          }}
        >
          Annuler
        </Bouton>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <Alerte>{erreur}</Alerte>
      <p className="text-base text-texte">
        C'est un compte Google : connectez-vous simplement avec Google. Votre navigateur va s'ouvrir, une seule fois.
      </p>
      <Bouton onClick={connecter} className="self-start">Se connecter avec Google</Bouton>
    </div>
  );
}

function ConnexionMotDePasse({ detection, onConnecte }) {
  const { rafraichir } = useAgent();
  const [motDePasse, setMotDePasse] = useState('');
  const [hote, setHote] = useState('');
  const [erreurs, setErreurs] = useState({});
  const [erreur, setErreur] = useState('');
  const [envoi, setEnvoi] = useState(false);
  const serveurDemande = !detection.hote || Boolean(erreurs.hote);
  const application = detection.mot_de_passe_application;

  const connecter = async (e) => {
    e.preventDefault();
    setErreur('');
    setErreurs({});
    if (!motDePasse) {
      setErreurs({ mot_de_passe: 'Saisissez le mot de passe.' });
      return;
    }
    setEnvoi(true);
    try {
      const etat = await api.post('/boite/mot-de-passe', { email: detection.email, mot_de_passe: motDePasse, hote: hote.trim() || null });
      await rafraichir();
      onConnecte?.(etat);
    } catch (err) {
      if (Object.keys(err.champs).length) setErreurs(err.champs);
      else setErreur(err.message);
    } finally {
      setMotDePasse(''); // le mot de passe n'est jamais conservé dans l'interface
      setEnvoi(false);
    }
  };

  return (
    <form onSubmit={connecter} noValidate className="flex flex-col gap-4">
      <Alerte>{erreur || erreurs.email}</Alerte>
      {detection.avertissement && <Alerte ton="alerte">{detection.avertissement}</Alerte>}
      {application && (
        <div className="rounded-lg border border-trait bg-survol p-4">
          <p className="text-sm font-semibold text-fort">
            {detection.fournisseur} demande un mot de passe spécial pour INJARA (« mot de passe d'application »). Cela prend une minute :
          </p>
          <ol className="mt-2 flex list-decimal flex-col gap-1.5 pl-5 text-sm text-texte">
            {detection.etapes.map((etape) => <li key={etape}>{etape}</li>)}
          </ol>
          {detection.lien && (
            <Bouton variante="secondaire" taille="sm" icone={ExternalLink} className="mt-3" onClick={() => window.injara.liens.ouvrir(detection.lien)}>
              Ouvrir la page {detection.fournisseur === 'Yahoo' ? 'Yahoo' : 'Google'}
            </Bouton>
          )}
        </div>
      )}
      <Champ
        label={application ? "Mot de passe d'application" : 'Mot de passe de la boîte mail'}
        erreur={erreurs.mot_de_passe}
        aide={application ? undefined : 'Celui que vous utilisez pour lire les mails de cette adresse.'}
      >
        {(a) => <MotDePasse {...a} autoFocus autoComplete="off" value={motDePasse} onChange={(e) => setMotDePasse(e.target.value)} />}
      </Champ>
      {serveurDemande && (
        <Champ
          label="Serveur de messagerie"
          erreur={erreurs.hote}
          aide={erreurs.hote ? undefined : "Nous ne l'avons pas trouvé automatiquement. Votre hébergeur ou la personne qui gère vos mails peut vous le donner."}
        >
          {(a) => <Saisie {...a} placeholder="ex. mail.votre-entreprise.com" value={hote} onChange={(e) => setHote(e.target.value)} />}
        </Champ>
      )}
      <Bouton type="submit" chargement={envoi} className="self-start">Connecter la boîte</Bouton>
      {envoi && <p className="text-sm text-doux">Connexion et essai de l'envoi des mails…</p>}
      <p className="flex items-center gap-2 text-sm text-doux">
        <ShieldCheck className="size-4 shrink-0" aria-hidden />
        Le mot de passe est rangé dans le coffre sécurisé de cet ordinateur.
      </p>
    </form>
  );
}

/** Résultat d'une connexion : lecture des candidatures et envoi des mails, en clair. */
export function EtatBoite({ etat }) {
  const envoi = etat.envoi || {};
  const envoiPret = envoi.autorise || envoi.simule;
  return (
    <ul className="flex flex-col gap-2 text-base">
      <li className="flex items-start gap-2">
        <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-accent-texte" aria-hidden />
        <span>
          <strong className="text-fort">Réception des candidatures</strong>
          <span className="text-doux"> : prête{etat.email ? ` sur ${etat.email}` : ''}.</span>
        </span>
      </li>
      <li className="flex items-start gap-2">
        {envoiPret ? (
          <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-accent-texte" aria-hidden />
        ) : (
          <TriangleAlert className="mt-0.5 size-5 shrink-0 text-alerte" aria-hidden />
        )}
        <span>
          <strong className="text-fort">Mails aux candidats</strong>
          {envoiPret ? (
            <span className="text-doux"> : prêts{envoi.simule ? ' (mode démo, rien ne part réellement)' : ''}.</span>
          ) : (
            <span className="text-doux">
              {' '}: pas encore. {envoi.motif}{' '}
              <Link to="/parametres/mails" className="font-semibold text-accent-texte underline underline-offset-4">Régler l'envoi</Link>
            </span>
          )}
        </span>
      </li>
    </ul>
  );
}
