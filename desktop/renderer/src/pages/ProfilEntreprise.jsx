import { Check, Pencil } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { Alerte, Bouton, Carte, Champ, Chargement, EnTetePage, Saisie, ZoneTexte } from '../components/ui.jsx';

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

  if (!profil) return erreurGenerale ? <Alerte>{erreurGenerale}</Alerte> : <Chargement />;

  return (
    <>
      <EnTetePage
        titre="Profil entreprise"
        description="Ces informations identifient votre entreprise dans INJARA."
        actions={
          !edition && (
            <Bouton variante="secondaire" icone={Pencil} onClick={() => setEdition(true)}>Modifier</Bouton>
          )
        }
      />
      {enregistre && (
        <p role="status" className="mb-4 flex items-center gap-2 text-sm font-medium text-brand-700">
          <Check className="size-4" aria-hidden /> Profil enregistré.
        </p>
      )}

      <Carte>
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
              <Bouton type="submit" chargement={envoi}>Enregistrer</Bouton>
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
      </Carte>
    </>
  );
}

function Info({ libelle, valeur, large }) {
  return (
    <div className={large ? 'md:col-span-2' : undefined}>
      <dt className="text-xs font-semibold tracking-wide text-muted uppercase">{libelle}</dt>
      <dd className={`mt-1 text-sm whitespace-pre-line ${valeur ? 'text-navy-900' : 'text-navy-200 italic'}`}>{valeur || 'Non renseigné'}</dd>
    </div>
  );
}
