// Liaison de la boîte mail de recrutement : Gmail / Google Workspace, ou autre messagerie (adresse + mot de passe).
import { AtSign, FileKey, LoaderCircle, Mail, ShieldCheck } from 'lucide-react';
import { useRef, useState } from 'react';
import { api } from '../api.js';
import { Alerte, Bouton, Carte, Champ, MotDePasse, Saisie } from '../components/ui.jsx';
import { useAgent } from './ContexteAgent.jsx';

export default function ConnexionBoite() {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <CarteGmail />
      <FormulaireMessagerie />
      <p className="flex items-center gap-2 text-sm text-doux lg:col-span-2">
        <ShieldCheck className="size-4" aria-hidden />
        INJARA lit uniquement la boîte mail : il n'envoie, ne supprime et ne modifie aucun email. Le mot de passe est rangé
        dans le coffre sécurisé de l'ordinateur.
      </p>
    </div>
  );
}

function CarteGmail() {
  const { etat, rafraichir } = useAgent();
  const [attente, setAttente] = useState(false);
  const [erreur, setErreur] = useState('');
  const tentative = useRef(0);
  const identifiantsManquants = etat && etat.mode === 'real' && !etat.identifiants_google;

  const lier = async () => {
    const numero = ++tentative.current;
    setErreur('');
    setAttente(true);
    try {
      await api.post('/gmail/connect');
      if (numero === tentative.current) await rafraichir();
    } catch (err) {
      if (numero === tentative.current) setErreur(err.message);
    } finally {
      if (numero === tentative.current) setAttente(false);
    }
  };

  const importerIdentifiants = async () => {
    setErreur('');
    const reponse = await window.injara.fichiers.importerIdentifiantsGoogle();
    if (reponse.annule) return;
    if (!reponse.ok) setErreur(reponse.donnees?.champs?.fichier || reponse.donnees?.detail || 'Fichier refusé.');
    await rafraichir();
  };

  return (
    <Carte className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <span className="flex size-10 items-center justify-center rounded-lg border border-accent-trait bg-accent-doux text-accent-texte"><Mail className="size-5" aria-hidden /></span>
        <div>
          <h2 className="titre-section">Gmail ou Google Workspace</h2>
          <p className="text-sm text-doux">Connectez-vous avec votre compte Google.</p>
        </div>
      </div>

      <Alerte>{erreur}</Alerte>

      {identifiantsManquants ? (
        <>
          <p className="text-sm text-texte">
            Pour lier un compte Google, importez d'abord le fichier d'identifiants Google de votre entreprise
            (<span className="font-mono text-xs">credentials.json</span>, un « ID client OAuth » de type « Application de bureau »
            créé dans la console Google Cloud).
          </p>
          <Bouton variante="secondaire" icone={FileKey} onClick={importerIdentifiants} className="self-start">
            Importer le fichier d'identifiants
          </Bouton>
        </>
      ) : attente ? (
        <div className="flex flex-col gap-3 rounded-lg border border-trait bg-survol p-4 text-sm text-texte">
          <p className="flex items-center gap-2 font-semibold">
            <LoaderCircle className="size-4 animate-spin" aria-hidden /> En attente de Google…
          </p>
          <p>Une fenêtre Google vient de s'ouvrir dans votre navigateur. Autorisez l'accès, puis revenez ici.</p>
          <p className="text-doux">
            Si Google affiche « Google n'a pas validé cette application », cliquez sur « Paramètres avancés », puis sur
            « Continuer ».
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
      ) : (
        <Bouton onClick={lier} className="self-start">Lier mon compte Gmail</Bouton>
      )}
    </Carte>
  );
}

function FormulaireMessagerie() {
  const { rafraichir } = useAgent();
  const [email, setEmail] = useState('');
  const [motDePasse, setMotDePasse] = useState('');
  const [hote, setHote] = useState('');
  const [hoteDeduit, setHoteDeduit] = useState(false); // serveur rempli automatiquement d'après l'adresse
  const [port, setPort] = useState('993');
  const [dossier, setDossier] = useState('INBOX');
  const [detection, setDetection] = useState(null); // { known, host, port, help }
  const [avance, setAvance] = useState(false);
  const [serveurRequis, setServeurRequis] = useState(false);
  const [erreur, setErreur] = useState('');
  const [aide, setAide] = useState('');
  const [envoi, setEnvoi] = useState(false);

  const detecter = async () => {
    const adresse = email.trim();
    if (!adresse.includes('@')) return;
    try {
      const d = await api.get(`/gmail/imap/detect?email=${encodeURIComponent(adresse)}`);
      setDetection(d);
      if (d.known) {
        setHote(d.host);
        setPort(String(d.port));
        setHoteDeduit(true);
      } else if (hoteDeduit) {
        setHote(''); // l'adresse a changé : le serveur déduit de l'ancienne n'est plus valable
        setHoteDeduit(false);
      }
    } catch {
      setDetection(null);
    }
  };

  const afficherServeur = avance || serveurRequis || (detection && !detection.known);

  const soumettre = async (e) => {
    e.preventDefault();
    setErreur('');
    setAide('');
    if (!email.trim() || !motDePasse) {
      setErreur("Saisissez l'adresse et le mot de passe de la boîte mail.");
      return;
    }
    setEnvoi(true);
    const corps = { email: email.trim(), password: motDePasse, port: Number(port) || 993, folder: dossier.trim() || 'INBOX' };
    if (hote.trim() && (afficherServeur || hoteDeduit)) corps.host = hote.trim();
    try {
      await api.post('/gmail/connect/imap', corps);
      await rafraichir();
    } catch (err) {
      if (err.statut === 401) {
        setErreur('Adresse ou mot de passe refusé.');
        setAide(detection?.help || '');
      } else if (err.statut === 502) {
        setErreur("Impossible de joindre le serveur de messagerie. Vérifiez son adresse et votre connexion Internet.");
      } else if (err.statut === 422 && /serveur/i.test(err.message)) {
        setServeurRequis(true);
        setErreur("Le serveur de messagerie n'a pas pu être deviné : renseignez-le ci-dessous (demandez-le à votre hébergeur, ex. imap.mail.ovh.net).");
      } else {
        setErreur(err.message);
      }
    } finally {
      setMotDePasse(''); // le mot de passe n'est jamais conservé dans l'interface
      setEnvoi(false);
    }
  };

  return (
    <Carte>
      <form onSubmit={soumettre} noValidate className="flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <span className="flex size-10 items-center justify-center rounded-lg border border-trait bg-survol-fort text-doux"><AtSign className="size-5" aria-hidden /></span>
          <div>
            <h2 className="titre-section">Autre messagerie</h2>
            <p className="text-sm text-doux">Adresse et mot de passe de la boîte mail de recrutement.</p>
          </div>
        </div>
        {erreur && (
          <Alerte>
            {erreur}
            {aide && <p className="mt-1">{aide}</p>}
          </Alerte>
        )}
        <Champ label="Adresse e-mail" obligatoire>
          {(a) => (
            <Saisie {...a} type="email" placeholder="recrutement@entreprise.com" value={email} onChange={(e) => setEmail(e.target.value)} onBlur={detecter} />
          )}
        </Champ>
        <Champ label="Mot de passe de la boîte mail" aide={detection?.help} obligatoire>
          {(a) => <MotDePasse {...a} autoComplete="off" value={motDePasse} onChange={(e) => setMotDePasse(e.target.value)} />}
        </Champ>
        {afficherServeur && (
          <Champ label="Serveur de messagerie (IMAP)" erreur={serveurRequis && !hote.trim() ? 'Champ obligatoire pour cette adresse.' : undefined} obligatoire={serveurRequis || (detection && !detection.known)}>
            {(a) => (
              <Saisie
                {...a}
                placeholder="ex. imap.mail.ovh.net"
                value={hote}
                onChange={(e) => {
                  setHote(e.target.value);
                  setHoteDeduit(false);
                }}
              />
            )}
          </Champ>
        )}
        {avance && (
          <div className="grid grid-cols-2 gap-4">
            <Champ label="Port">{(a) => <Saisie {...a} type="number" value={port} onChange={(e) => setPort(e.target.value)} />}</Champ>
            <Champ label="Dossier à lire">{(a) => <Saisie {...a} value={dossier} onChange={(e) => setDossier(e.target.value)} />}</Champ>
          </div>
        )}
        <div className="flex items-center justify-between gap-2">
          <button type="button" onClick={() => setAvance((v) => !v)} aria-expanded={avance} className="text-sm font-medium text-doux hover:text-fort hover:underline">
            {avance ? 'Masquer les paramètres avancés' : 'Paramètres avancés'}
          </button>
          <Bouton type="submit" chargement={envoi}>Lier la boîte mail</Bouton>
        </div>
      </form>
    </Carte>
  );
}
