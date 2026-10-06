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
};

const versFormulaire = (poste) => Object.fromEntries(Object.keys(VIDE).map((k) => [k, poste[k] ?? VIDE[k]]));

function versRequete(f) {
  const experience = String(f.experience_min_annees).trim();
  return {
    ...f,
    experience_min_annees: experience === '' ? null : Number(experience),
    date_limite: f.date_limite || null,
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
      <Link to={retour} className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-muted hover:text-navy-900">
        <ArrowLeft className="size-4" aria-hidden /> Retour
      </Link>
      <div ref={haut}>
        <EnTetePage
          titre={id ? 'Modifier le poste' : 'Nouveau poste'}
          description="Les champs marqués d'un astérisque sont obligatoires."
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

        <Section titre="Sélection" facultatif>
          <Champ label="Processus de sélection" erreur={erreurs.processus_selection}>
            {(a) => <ZoneTexte {...a} rows={4} placeholder="Ex. Tri des CV, test écrit, entretien avec le manager." {...valeur('processus_selection')} />}
          </Champ>
          <Champ label="Documents demandés" erreur={erreurs.documents_demandes}>
            {(a) => <SaisieListe {...a} placeholder="Ex. CV, Lettre de motivation, Diplômes" {...liste('documents_demandes')} />}
          </Champ>
        </Section>

        <div className="sticky bottom-0 -mx-8 flex justify-end gap-2 border-t border-line bg-mist px-8 py-4">
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
      <h2 className="font-semibold text-navy-900">
        {titre}
        {facultatif && <span className="ml-2 text-xs font-normal text-muted">facultatif</span>}
      </h2>
      {children}
    </Carte>
  );
}
