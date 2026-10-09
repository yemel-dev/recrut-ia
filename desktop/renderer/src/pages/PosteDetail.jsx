import { ArrowLeft, Pencil, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api.js';
import TopPoste from '../candidatures/TopPoste.jsx';
import SuppressionPoste from '../components/SuppressionPoste.jsx';
import { Alerte, BadgeStatut, Bouton, Carte, Segments } from '../components/ui.jsx';
import { STATUTS, TELETRAVAIL, TYPES_CONTRAT } from '../constantes.js';
import { experience, formaterDate } from '../format.js';

export default function PosteDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [poste, setPoste] = useState(null);
  const [erreur, setErreur] = useState('');
  const [suppression, setSuppression] = useState(false);
  const [changementStatut, setChangementStatut] = useState(false);

  useEffect(() => {
    api.get(`/postes/${id}`).then(setPoste, (err) => setErreur(err.message));
  }, [id]);

  const changerStatut = async (statut) => {
    setChangementStatut(true);
    setErreur('');
    try {
      setPoste(await api.put(`/postes/${id}/statut`, { statut }));
    } catch (err) {
      setErreur(err.message);
    } finally {
      setChangementStatut(false);
    }
  };

  if (!poste) {
    return erreur ? (
      <>
        <Alerte>{erreur}</Alerte>
        <Link to="/postes" className="mt-4 inline-block text-sm font-medium text-accent-texte hover:underline">Retour aux postes</Link>
      </>
    ) : (
      <div aria-busy="true" aria-label="Chargement du poste">
        <div className="squelette mb-6 h-4 w-32" />
        <div className="squelette mb-3 h-8 w-80" />
        <div className="squelette mb-6 h-4 w-60" />
        <div className="squelette mb-6 h-16 rounded-lg" />
        <div className="squelette h-80 rounded-lg" />
      </div>
    );
  }

  const conditions = [
    ['Référence interne', poste.reference_interne],
    ['Département', poste.departement],
    ['Lieu', poste.lieu],
    ['Télétravail', TELETRAVAIL[poste.teletravail]],
    ['Type de contrat', TYPES_CONTRAT[poste.type_contrat]],
    ['Durée', poste.duree],
    ['Date limite', poste.date_limite && formaterDate(poste.date_limite)],
    ['Rémunération', poste.remuneration],
  ].filter(([, v]) => v);

  return (
    <>
      <Link to="/postes" className="geste-hote mb-5 inline-flex items-center gap-1.5 text-sm font-medium text-doux transition-colors hover:text-fort">
        <ArrowLeft className="size-4" aria-hidden data-geste="reculer" /> Tous les postes
      </Link>

      <header className="mb-6 flex items-start justify-between gap-6">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="titre-ecran">{poste.intitule}</h1>
            <BadgeStatut statut={poste.statut} />
          </div>
          <p className="mt-2 text-base text-doux">
            {poste.niveau_formation} · {experience(poste.experience_min_annees)}
            {poste.reference_interne && <span className="text-tenu tabular-nums"> · {poste.reference_interne}</span>}
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <Bouton variante="secondaire" icone={Pencil} geste="incliner" onClick={() => navigate(`/postes/${id}/modifier`)}>Modifier</Bouton>
          <Bouton variante="secondaire" icone={Trash2} geste="soulever" onClick={() => setSuppression(true)} className="hover:border-danger-trait hover:text-danger">
            Supprimer
          </Bouton>
        </div>
      </header>

      {erreur && <Alerte className="mb-4">{erreur}</Alerte>}

      <Carte className="mb-6 flex flex-wrap items-center justify-between gap-4 py-3.5">
        <p className="flex items-center gap-2.5 text-base text-texte">
          <span className={`size-2 shrink-0 rounded-full ${poste.statut === 'actif' ? 'bg-accent shadow-[0_0_8px_var(--halo)]' : poste.statut === 'brouillon' ? 'bg-info' : 'bg-tenu'}`} aria-hidden />
          {poste.statut === 'actif'
            ? 'Ce poste est actif : il servira au classement des candidatures.'
            : poste.statut === 'brouillon'
              ? "Ce poste est en brouillon : il n'est pas encore utilisé pour classer les candidatures."
              : "Ce poste est clôturé : il n'est plus utilisé pour classer les candidatures."}
        </p>
        <Segments
          libelle="Statut du poste"
          valeur={poste.statut}
          onChange={(valeur) => !changementStatut && valeur !== poste.statut && changerStatut(valeur)}
          options={Object.entries(STATUTS).map(([valeur, libelle]) => ({ valeur, libelle }))}
        />
      </Carte>

      <div className="mb-6">
        <TopPoste posteId={Number(id)} actif={poste.statut === 'actif'} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex min-w-0 flex-col gap-6">
          <Carte>
            <Titre>Description et missions</Titre>
            <p className="max-w-prose text-base leading-relaxed whitespace-pre-line text-texte">{poste.description}</p>
          </Carte>
          {poste.processus_selection && (
            <Carte>
              <Titre>Processus de sélection</Titre>
              <p className="max-w-prose text-base leading-relaxed whitespace-pre-line text-texte">{poste.processus_selection}</p>
            </Carte>
          )}
        </div>

        <div className="flex flex-col gap-6">
          <Carte className="flex flex-col gap-5">
            <Etiquettes titre="Compétences requises" valeurs={poste.competences_requises} accent />
            <Etiquettes titre="Compétences comportementales" valeurs={poste.competences_comportementales} />
            <Etiquettes titre="Langues" valeurs={poste.langues} />
            <Etiquettes titre="Documents demandés" valeurs={poste.documents_demandes} />
          </Carte>
          {conditions.length > 0 && (
            <Carte>
              <Titre>Conditions</Titre>
              <dl className="flex flex-col gap-2.5">
                {conditions.map(([libelle, valeur]) => (
                  <div key={libelle} className="flex justify-between gap-4 text-base">
                    <dt className="text-doux">{libelle}</dt>
                    <dd className="text-right font-medium text-fort">{valeur}</dd>
                  </div>
                ))}
              </dl>
            </Carte>
          )}
        </div>
      </div>

      <SuppressionPoste
        poste={suppression ? poste : null}
        onAnnuler={() => setSuppression(false)}
        onSupprime={() => navigate('/postes', { replace: true })}
      />
    </>
  );
}

function Titre({ children }) {
  return <h2 className="titre-section mb-3">{children}</h2>;
}

function Etiquettes({ titre, valeurs, accent }) {
  if (!valeurs?.length) return null;
  return (
    <div>
      <h3 className="etiquette mb-2">{titre}</h3>
      <ul className="flex flex-wrap gap-1.5">
        {valeurs.map((v) => (
          <li
            key={v}
            className={`rounded-sm border px-2 py-0.5 text-sm ${accent ? 'border-accent-trait bg-accent-doux text-accent-texte' : 'border-trait bg-survol text-texte'}`}
          >
            {v}
          </li>
        ))}
      </ul>
    </div>
  );
}
