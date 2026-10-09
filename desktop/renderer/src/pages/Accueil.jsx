// Assistant de démarrage, juste après la création du compte : l'entreprise, la boîte de recrutement (une seule
// connexion pour recevoir les candidatures et répondre aux candidats), les candidatures déjà reçues. Chaque étape
// peut être faite plus tard ; tout reste modifiable ensuite (Profil entreprise, Boîte mail, Mails aux candidats).
import { CheckCircle2, Circle } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api.js';
import { FournisseurAgent, useAgent } from '../agent/ContexteAgent.jsx';
import ConnexionSimple, { EtatBoite } from '../agent/ConnexionSimple.jsx';
import Demarrage from '../agent/Demarrage.jsx';
import EcranPublic from '../components/EcranPublic.jsx';
import { Alerte, Bouton, Champ, Chargement, Saisie, cx } from '../components/ui.jsx';

const ETAPES = ['entreprise', 'boite', 'reprise', 'pret'];

export default function Accueil() {
  return (
    <FournisseurAgent>
      <Assistant />
    </FournisseurAgent>
  );
}

function Assistant() {
  const navigate = useNavigate();
  const { statut } = useAgent();
  const [etape, setEtape] = useState('entreprise');
  const [entreprise, setEntreprise] = useState(null);
  const [boite, setBoite] = useState(null); // GET /boite après connexion

  const suivante = () => {
    const i = ETAPES.indexOf(etape);
    let prochaine = ETAPES[i + 1];
    if (prochaine === 'reprise' && !statut?.needs_setup) prochaine = 'pret';
    setEtape(prochaine);
  };

  const terminer = async () => {
    try {
      await api.put('/accueil/termine');
    } finally {
      navigate('/', { replace: true });
    }
  };

  const numero = Math.min(ETAPES.indexOf(etape) + 1, 3);
  const titres = {
    entreprise: ['Votre entreprise', 'Ces informations apparaissent dans les mails envoyés aux candidats et sur les rapports.'],
    boite: [
      'Votre boîte de recrutement',
      "L'adresse où vous recevez les candidatures. INJARA y récupère les CV et s'en sert pour répondre aux candidats.",
    ],
    reprise: ['Les candidatures déjà reçues', 'Choisissez ce que INJARA doit récupérer dans votre boîte.'],
    pret: ["C'est prêt", 'Voici ce qui est configuré. Tout reste modifiable plus tard.'],
  };

  return (
    <EcranPublic titre={titres[etape][0]} sousTitre={titres[etape][1]} largeur="max-w-xl">
      {etape !== 'pret' && <p className="etiquette -mt-4 mb-6">Étape {numero} sur 3</p>}
      {etape === 'entreprise' && <EtapeEntreprise onSuivant={(e) => { setEntreprise(e); suivante(); }} onPlusTard={suivante} />}
      {etape === 'boite' && <EtapeBoite boite={boite} setBoite={setBoite} onSuivant={suivante} />}
      {etape === 'reprise' && (
        <div className="flex flex-col gap-4">
          <Demarrage onTermine={() => setEtape('pret')} />
          <PlusTard onClick={() => setEtape('pret')} />
        </div>
      )}
      {etape === 'pret' && <Recapitulatif entreprise={entreprise} boite={boite} onTerminer={terminer} />}
    </EcranPublic>
  );
}

function PlusTard({ onClick, children = 'Plus tard' }) {
  return (
    <button type="button" onClick={onClick} className="self-start text-sm font-medium text-doux hover:text-fort hover:underline">
      {children}
    </button>
  );
}

function EtapeEntreprise({ onSuivant, onPlusTard }) {
  const [formulaire, setFormulaire] = useState(null);
  const [erreurs, setErreurs] = useState({});
  const [erreur, setErreur] = useState('');
  const [envoi, setEnvoi] = useState(false);

  useEffect(() => {
    api.get('/entreprise').then(
      (p) => setFormulaire({ nom: p.nom || '', ville: p.ville || '', secteur: p.secteur || '' }),
      (err) => setErreur(err.message),
    );
  }, []);

  const modifier = (champ) => (e) => setFormulaire((f) => ({ ...f, [champ]: e.target.value }));

  const enregistrer = async (e) => {
    e.preventDefault();
    setErreurs({});
    setErreur('');
    if (!formulaire.nom.trim()) {
      setErreurs({ nom: "Indiquez le nom de l'entreprise." });
      return;
    }
    setEnvoi(true);
    try {
      onSuivant(await api.put('/entreprise', formulaire));
    } catch (err) {
      setErreurs(err.champs);
      if (!Object.keys(err.champs).length) setErreur(err.message);
    } finally {
      setEnvoi(false);
    }
  };

  if (!formulaire) return erreur ? <Alerte>{erreur}</Alerte> : <Chargement />;
  return (
    <form onSubmit={enregistrer} noValidate className="flex flex-col gap-4">
      <Alerte>{erreur}</Alerte>
      <Champ label="Nom de l'entreprise" erreur={erreurs.nom} obligatoire>
        {(a) => <Saisie {...a} autoFocus value={formulaire.nom} onChange={modifier('nom')} />}
      </Champ>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Champ label="Ville" erreur={erreurs.ville}>
          {(a) => <Saisie {...a} placeholder="Douala" value={formulaire.ville} onChange={modifier('ville')} />}
        </Champ>
        <Champ label="Secteur d'activité" erreur={erreurs.secteur}>
          {(a) => <Saisie {...a} placeholder="Banque, industrie, numérique…" value={formulaire.secteur} onChange={modifier('secteur')} />}
        </Champ>
      </div>
      <div className="mt-2 flex items-center justify-between gap-2">
        <PlusTard onClick={onPlusTard} />
        <Bouton type="submit" chargement={envoi} geste="avancer">Continuer</Bouton>
      </div>
    </form>
  );
}

function EtapeBoite({ boite, setBoite, onSuivant }) {
  const { statut } = useAgent();
  const [changer, setChanger] = useState(false);
  const [etat, setEtat] = useState(boite);

  // Boîte déjà liée (ou mode démo) : on affiche son état plutôt que le formulaire
  useEffect(() => {
    if (!etat && statut?.connected) api.get('/boite').then(setEtat, () => {});
  }, [statut?.connected]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!statut) return <Chargement />;
  if (etat?.connectee && !changer) {
    return (
      <div className="flex flex-col gap-5">
        <div className="rounded-lg border border-accent-trait bg-accent-doux p-4">
          <EtatBoite etat={etat} />
        </div>
        <div className="flex items-center justify-between gap-2">
          <PlusTard onClick={() => setChanger(true)}>Utiliser une autre adresse</PlusTard>
          <Bouton
            geste="avancer"
            onClick={() => {
              setBoite(etat);
              onSuivant();
            }}
          >
            Continuer
          </Bouton>
        </div>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-5">
      <ConnexionSimple
        onConnecte={(nouveau) => {
          setEtat(nouveau);
          setChanger(false);
        }}
      />
      <PlusTard onClick={onSuivant} />
    </div>
  );
}

function Recapitulatif({ entreprise, boite, onTerminer }) {
  const [envoi, setEnvoi] = useState(false);
  const [etat, setEtat] = useState(boite);
  useEffect(() => {
    if (!etat) api.get('/boite').then(setEtat, () => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const lignes = [
    { ok: Boolean(entreprise?.nom), texte: entreprise?.nom ? `Entreprise : ${entreprise.nom}` : 'Entreprise : à compléter dans Profil entreprise' },
  ];
  return (
    <div className="flex flex-col gap-6">
      <ul className="flex flex-col gap-2 text-base">
        {lignes.map((l) => (
          <li key={l.texte} className="flex items-start gap-2">
            {l.ok ? <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-accent-texte" aria-hidden /> : <Circle className="mt-0.5 size-5 shrink-0 text-tenu" aria-hidden />}
            <span className={cx(l.ok ? 'text-fort' : 'text-doux')}>{l.texte}</span>
          </li>
        ))}
      </ul>
      {etat?.connectee ? (
        <EtatBoite etat={etat} />
      ) : (
        <p className="flex items-start gap-2 text-base text-doux">
          <Circle className="mt-0.5 size-5 shrink-0 text-tenu" aria-hidden />
          Boîte de recrutement : à connecter dans Boîte mail. En attendant, vous pouvez importer des CV à la main.
        </p>
      )}
      <Bouton
        taille="lg"
        geste="avancer"
        chargement={envoi}
        className="self-start"
        onClick={() => {
          setEnvoi(true);
          onTerminer();
        }}
      >
        Ouvrir INJARA
      </Bouton>
    </div>
  );
}
