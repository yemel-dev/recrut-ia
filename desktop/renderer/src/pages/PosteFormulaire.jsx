import { ArrowLeft } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api.js';
import { Alerte, Bouton, Carte, Champ, Chargement, EnTetePage, Liste, Saisie, SaisieListe, ZoneTexte } from '../components/ui.jsx';
import { NIVEAUX_FORMATION, STATUTS, TELETRAVAIL, TYPES_CONTRAT } from '../constantes.js';

const VIDE = {
  intitule: '',
  description: '',
  competences_requises: [],
  experience_min_annees: '',
  niveau_formation: '',
  reference_interne: '',
  departement: '',
  lieu: '',
  teletravail: '',
  type_contrat: '',
  duree: '',
  date_limite: '',
  competences_comportementales: [],
  langues: [],
  remuneration: '',
  processus_selection: '',
  documents_demandes: [],
  statut: 'brouillon',
  poids_competences: 40,
  poids_experience: 25,
  poids_formation: 20,
  poids_adequation: 15,
};

const POIDS = [
  ['poids_competences', 'Compétences', 'Part des compétences requises trouvées dans le CV.'],
  ['poids_experience', 'Expérience', "Années d'expérience par rapport au minimum demandé."],
  ['poids_formation', 'Formation', 'Diplôme obtenu par rapport au niveau demandé.'],
  ['poids_adequation', 'Adéquation globale', 'Proximité entre le CV et la description du poste.'],
];

const versFormulaire = (poste) => Object.fromEntries(Object.keys(VIDE).map((k) => [k, poste[k] ?? VIDE[k]]));

function versRequete(f) {
  const experience = String(f.experience_min_annees).trim();
  return {
    ...f,
    experience_min_annees: experience === '' ? null : Number(experience),
    date_limite: f.date_limite || null,
    ...Object.fromEntries(POIDS.map(([champ]) => [champ, f[champ] === '' ? null : Number(f[champ])])),
  };
}

export default function PosteFormulaire() {
  const { id } = useParams();
  const navigate = useNavigate();
  const haut = useRef(null);
  const [formulaire, setFormulaire] = useState(id ? null : VIDE);
  const [erreurs, setErreurs] = useState({});
  const [erreurGenerale, setErreurGenerale] = useState('');
  const [envoi, setEnvoi] = useState(false);

  useEffect(() => {
    if (id) api.get(`/postes/${id}`).then((p) => setFormulaire(versFormulaire(p)), (err) => setErreurGenerale(err.message));
  }, [id]);

  const valeur = (champ) => ({
    value: formulaire[champ],
    onChange: (e) => setFormulaire((f) => ({ ...f, [champ]: e.target.value })),
  });
  const liste = (champ) => ({
    valeur: formulaire[champ],
    onChange: (v) => setFormulaire((f) => ({ ...f, [champ]: v })),
  });

  const enregistrer = async (e) => {
    e.preventDefault();
    setErreurs({});
    setErreurGenerale('');
    setEnvoi(true);
    try {
      const poste = id
        ? await api.put(`/postes/${id}`, versRequete(formulaire))
        : await api.post('/postes', versRequete(formulaire));
      navigate(`/postes/${poste.id}`, { replace: true });
    } catch (err) {
      setErreurs(err.champs);
      setErreurGenerale(Object.keys(err.champs).length ? 'Certains champs sont à corriger : ils sont signalés en rouge.' : err.message);
      haut.current?.scrollIntoView({ behavior: 'smooth' });
    } finally {
      setEnvoi(false);
    }
  };

  if (!formulaire) return erreurGenerale ? <Alerte>{erreurGenerale}</Alerte> : <Chargement />;

  const retour = id ? `/postes/${id}` : '/postes';

  return (
    <>
      <Link to={retour} className="geste-hote mb-5 inline-flex items-center gap-1.5 text-sm font-medium text-doux transition-colors hover:text-fort">
        <ArrowLeft className="size-4" aria-hidden data-geste="reculer" /> Retour
      </Link>
      <div ref={haut}>
        <EnTetePage
          titre={id ? 'Modifier le poste' : 'Nouveau poste'}
          description={id ? 'Les candidatures seront renotées après l’enregistrement.' : 'Décrivez le poste : INJARA s’en servira pour classer et noter les CV reçus.'}
        />
      </div>

      <form onSubmit={enregistrer} noValidate className="flex flex-col gap-6">
        <Alerte>{erreurGenerale}</Alerte>

        <Section titre="Le poste">
          <Champ label="Intitulé du poste" erreur={erreurs.intitule} obligatoire>
            {(a) => <Saisie {...a} autoFocus={!id} placeholder="Ex. Chargé de clientèle entreprises" {...valeur('intitule')} />}
          </Champ>
          <Champ label="Description et missions" erreur={erreurs.description} aide="Contexte du poste, responsabilités, missions principales." obligatoire>
            {(a) => <ZoneTexte {...a} rows={8} {...valeur('description')} />}
          </Champ>
          <Champ label="Statut" erreur={erreurs.statut} aide="Seuls les postes actifs serviront au classement des candidatures." className="md:w-1/2">
            {(a) => <Liste {...a} options={STATUTS} vide={null} {...valeur('statut')} />}
          </Champ>
        </Section>

        <Section titre="Profil recherché">
          <Champ label="Compétences requises" erreur={erreurs.competences_requises} aide="Appuyez sur Entrée ou mettez une virgule entre chaque compétence." obligatoire>
            {(a) => <SaisieListe {...a} placeholder="Ex. Analyse financière, Excel, Négociation" {...liste('competences_requises')} />}
          </Champ>
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            <Champ label="Expérience minimale (en années)" erreur={erreurs.experience_min_annees} aide="0 si le poste est ouvert aux débutants." obligatoire>
              {(a) => <Saisie {...a} type="number" min={0} max={50} step={1} {...valeur('experience_min_annees')} />}
            </Champ>
            <Champ label="Niveau de formation requis" erreur={erreurs.niveau_formation} obligatoire>
              {(a) => (
                <Liste {...a} options={Object.fromEntries(NIVEAUX_FORMATION.map((n) => [n, n]))} vide="Choisir un niveau" {...valeur('niveau_formation')} />
              )}
            </Champ>
          </div>
          <Champ label="Compétences comportementales" erreur={erreurs.competences_comportementales}>
            {(a) => <SaisieListe {...a} placeholder="Ex. Rigueur, Sens du service" {...liste('competences_comportementales')} />}
          </Champ>
          <Champ label="Langues" erreur={erreurs.langues}>
            {(a) => <SaisieListe {...a} placeholder="Ex. Français, Anglais" {...liste('langues')} />}
          </Champ>
        </Section>

        <Section titre="Conditions" facultatif>
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            <Champ label="Référence interne" erreur={erreurs.reference_interne}>
              {(a) => <Saisie {...a} placeholder="Ex. RH-2026-014" {...valeur('reference_interne')} />}
            </Champ>
            <Champ label="Département" erreur={erreurs.departement}>
              {(a) => <Saisie {...a} {...valeur('departement')} />}
            </Champ>
            <Champ label="Lieu" erreur={erreurs.lieu}>
              {(a) => <Saisie {...a} placeholder="Ex. Douala, Akwa" {...valeur('lieu')} />}
            </Champ>
            <Champ label="Télétravail" erreur={erreurs.teletravail}>
              {(a) => <Liste {...a} options={TELETRAVAIL} {...valeur('teletravail')} />}
            </Champ>
            <Champ label="Type de contrat" erreur={erreurs.type_contrat}>
              {(a) => <Liste {...a} options={TYPES_CONTRAT} {...valeur('type_contrat')} />}
            </Champ>
            <Champ label="Durée" erreur={erreurs.duree} aide="Pour un CDD, un stage ou une mission.">
              {(a) => <Saisie {...a} placeholder="Ex. 6 mois" {...valeur('duree')} />}
            </Champ>
            <Champ label="Date limite de candidature" erreur={erreurs.date_limite}>
              {(a) => <Saisie {...a} type="date" {...valeur('date_limite')} />}
            </Champ>
            <Champ label="Rémunération" erreur={erreurs.remuneration}>
              {(a) => <Saisie {...a} placeholder="Ex. 350 000 à 450 000 FCFA brut / mois" {...valeur('remuneration')} />}
            </Champ>
          </div>
        </Section>

        <Section titre="Pondération du score" facultatif>
          <p className="-mt-2 text-base text-doux">
            Le score de chaque candidature (sur 100) combine ces quatre critères. Le total doit faire 100.
          </p>
          <div className="grid grid-cols-2 gap-5 md:grid-cols-4">
            {POIDS.map(([champ, libelle, aide]) => (
              <Champ key={champ} label={libelle} erreur={erreurs[champ]} aide={aide}>
                {(a) => <Saisie {...a} type="number" min={0} max={100} step={5} {...valeur(champ)} />}
              </Champ>
            ))}
          </div>
          {(() => {
            const total = POIDS.reduce((somme, [champ]) => somme + (Number(formulaire[champ]) || 0), 0);
            const juste = total === 100 && !erreurs.poids;
            return (
              <div className="flex flex-col gap-2" aria-live="polite">
                <div className="flex h-1.5 gap-0.5 overflow-hidden rounded-full bg-survol-fort" aria-hidden>
                  {POIDS.map(([champ], i) => (
                    <span
                      key={champ}
                      className="h-full transition-[flex-grow] duration-200"
                      style={{ flexGrow: Math.max(0, Number(formulaire[champ]) || 0), flexBasis: 0, backgroundColor: ['var(--accent)', 'var(--info)', 'var(--alerte)', 'var(--vert-300)'][i] }}
                    />
                  ))}
                  {total < 100 && <span className="h-full" style={{ flexGrow: 100 - total, flexBasis: 0 }} />}
                </div>
                <p className={`text-sm font-medium tabular-nums ${juste ? 'text-accent-texte' : 'text-danger'}`}>
                  Total : {total} / 100{erreurs.poids && total !== 100 ? ` : ${erreurs.poids}` : ''}
                </p>
              </div>
            );
          })()}
        </Section>

        <Section titre="Sélection" facultatif>
          <Champ label="Processus de sélection" erreur={erreurs.processus_selection}>
            {(a) => <ZoneTexte {...a} rows={4} placeholder="Ex. Tri des CV, test écrit, entretien avec le manager." {...valeur('processus_selection')} />}
          </Champ>
          <Champ label="Documents demandés" erreur={erreurs.documents_demandes}>
            {(a) => <SaisieListe {...a} placeholder="Ex. CV, Lettre de motivation, Diplômes" {...liste('documents_demandes')} />}
          </Champ>
        </Section>

        <div className="sticky bottom-0 z-10 -mx-10 -mb-16 flex items-center justify-end gap-2 border-t border-trait bg-fond/90 px-10 py-3.5 backdrop-blur">
          <span className="mr-auto text-sm text-tenu">Les champs marqués d'un astérisque sont obligatoires.</span>
          <Bouton variante="secondaire" onClick={() => navigate(retour)}>Annuler</Bouton>
          <Bouton type="submit" chargement={envoi}>{id ? 'Enregistrer les modifications' : 'Créer le poste'}</Bouton>
        </div>
      </form>
    </>
  );
}

function Section({ titre, facultatif, children }) {
  return (
    <Carte className="flex flex-col gap-5">
      <h2 className="titre-section">
        {titre}
        {facultatif && <span className="ml-2 text-sm font-normal text-tenu">facultatif</span>}
      </h2>
      {children}
    </Carte>
  );
}
