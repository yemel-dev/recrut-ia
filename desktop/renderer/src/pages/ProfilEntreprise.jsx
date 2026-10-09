import { Building2, Check, MapPin, Pencil } from 'lucide-react';
import { AnimatePresence, m } from 'motion/react';
import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { COURBE_SORTIE } from '../components/mouvement.js';
import { Alerte, Bouton, Carte, Champ, EnTetePage, Saisie, ZoneTexte } from '../components/ui.jsx';

const CHAMPS = [
  { nom: 'nom', libelle: "Nom de l'entreprise", obligatoire: true },
  { nom: 'secteur', libelle: "Secteur d'activité", exemple: 'Banque, industrie, numérique…' },
  { nom: 'ville', libelle: 'Ville' },
  { nom: 'email_pro', libelle: 'Email professionnel', type: 'email' },
  { nom: 'telephone', libelle: 'Téléphone', type: 'tel', exemple: '+237 6 00 00 00 00' },
];

const versFormulaire = (profil) => Object.fromEntries(Object.entries(profil).map(([k, v]) => [k, v ?? '']));

export default function ProfilEntreprise() {
  const [profil, setProfil] = useState(null);
  const [formulaire, setFormulaire] = useState(null);
  const [edition, setEdition] = useState(false);
  const [erreurs, setErreurs] = useState({});
  const [erreurGenerale, setErreurGenerale] = useState('');
  const [envoi, setEnvoi] = useState(false);
  const [enregistre, setEnregistre] = useState(false);

  useEffect(() => {
    api.get('/entreprise').then(
      (p) => {
        setProfil(p);
        setFormulaire(versFormulaire(p));
        setEdition(!p.nom); // profil vide : on ouvre directement le formulaire
      },
      (err) => setErreurGenerale(err.message),
    );
  }, []);

  const modifier = (champ) => (e) => setFormulaire((f) => ({ ...f, [champ]: e.target.value }));

  const enregistrer = async (e) => {
    e.preventDefault();
    setErreurGenerale('');
    setErreurs({});
    setEnvoi(true);
    try {
      const p = await api.put('/entreprise', formulaire);
      setProfil(p);
      setFormulaire(versFormulaire(p));
      setEdition(false);
      setEnregistre(true);
      setTimeout(() => setEnregistre(false), 3000);
    } catch (err) {
      setErreurs(err.champs);
      if (!Object.keys(err.champs).length) setErreurGenerale(err.message);
    } finally {
      setEnvoi(false);
    }
  };

  if (!profil) {
    return erreurGenerale ? <Alerte>{erreurGenerale}</Alerte> : <div className="squelette h-72 rounded-lg" aria-busy="true" aria-label="Chargement du profil" />;
  }

  const initiales = (profil.nom || '')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((mot) => mot[0].toUpperCase())
    .join('');

  return (
    <>
      <EnTetePage
        titre="Profil entreprise"
        description="Ces informations identifient votre entreprise dans INJARA et sur les rapports des candidats."
        actions={!edition && <Bouton variante="secondaire" icone={Pencil} geste="incliner" onClick={() => setEdition(true)}>Modifier</Bouton>}
      />
      <AnimatePresence>
        {enregistre && (
          <m.div
            initial={{ opacity: 0, transform: 'translateY(-4px)' }}
            animate={{ opacity: 1, transform: 'translateY(0px)' }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.22, ease: COURBE_SORTIE }}
          >
            <Alerte ton="succes" className="mb-5">Profil enregistré.</Alerte>
          </m.div>
        )}
      </AnimatePresence>

      <Carte sansMarge className="overflow-hidden">
        {!edition && (
          <div className="relative flex items-center gap-5 border-b border-trait px-6 py-6">
            <div className="pointer-events-none absolute -top-20 -right-10 size-64 rounded-full bg-[radial-gradient(closest-side,var(--accent-doux),transparent)]" aria-hidden />
            <span className="relative grid size-16 shrink-0 place-items-center rounded-xl border border-accent-trait bg-accent-doux font-titres text-2xl text-accent-texte">
              {initiales || <Building2 className="size-7" aria-hidden />}
            </span>
            <div className="relative min-w-0">
              <p className="font-titres text-2xl text-fort">{profil.nom || 'Entreprise sans nom'}</p>
              <p className="mt-1 flex flex-wrap items-center gap-x-3 text-base text-doux">
                {profil.secteur && <span>{profil.secteur}</span>}
                {profil.ville && <span className="inline-flex items-center gap-1"><MapPin className="size-3.5" aria-hidden /> {profil.ville}</span>}
              </p>
            </div>
          </div>
        )}
        <div className="p-6">
          {edition ? (
            <form onSubmit={enregistrer} noValidate className="flex flex-col gap-5">
              <Alerte>{erreurGenerale}</Alerte>
              <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                {CHAMPS.map(({ nom, libelle, obligatoire, type = 'text', exemple }) => (
                  <Champ key={nom} label={libelle} erreur={erreurs[nom]} obligatoire={obligatoire}>
                    {(a) => <Saisie {...a} type={type} placeholder={exemple} value={formulaire[nom]} onChange={modifier(nom)} />}
                  </Champ>
                ))}
              </div>
              <Champ label="Description" erreur={erreurs.description} aide="Activité, taille, valeurs… quelques lignes suffisent.">
                {(a) => <ZoneTexte {...a} value={formulaire.description} onChange={modifier('description')} />}
              </Champ>
              <div className="flex justify-end gap-2">
                {profil.nom && (
                  <Bouton
                    variante="secondaire"
                    onClick={() => {
                      setFormulaire(versFormulaire(profil));
                      setErreurs({});
                      setEdition(false);
                    }}
                  >
                    Annuler
                  </Bouton>
                )}
                <Bouton type="submit" icone={Check} chargement={envoi}>Enregistrer</Bouton>
              </div>
            </form>
          ) : (
            <dl className="grid grid-cols-1 gap-x-8 gap-y-5 md:grid-cols-2">
              {CHAMPS.map(({ nom, libelle }) => (
                <Info key={nom} libelle={libelle} valeur={profil[nom]} />
              ))}
              <Info libelle="Description" valeur={profil.description} large />
            </dl>
          )}
        </div>
      </Carte>
    </>
  );
}

function Info({ libelle, valeur, large }) {
  return (
    <div className={large ? 'md:col-span-2' : undefined}>
      <dt className="etiquette">{libelle}</dt>
      <dd className={`mt-1 text-base whitespace-pre-line ${valeur ? 'text-fort' : 'text-tenu italic'}`}>{valeur || 'Non renseigné'}</dd>
    </div>
  );
}
