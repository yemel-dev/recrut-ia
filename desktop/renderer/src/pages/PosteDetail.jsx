import { ArrowLeft, Pencil, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api.js';
import SuppressionPoste from '../components/SuppressionPoste.jsx';
import { Alerte, BadgeStatut, Bouton, Carte, Chargement } from '../components/ui.jsx';
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
        <Link to="/postes" className="mt-4 inline-block text-sm font-medium text-brand-700 hover:underline">Retour aux postes</Link>
      </>
    ) : (
      <Chargement />
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
      <Link to="/postes" className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-muted hover:text-navy-900">
        <ArrowLeft className="size-4" aria-hidden /> Tous les postes
      </Link>

      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-navy-900">{poste.intitule}</h1>
            <BadgeStatut statut={poste.statut} />
          </div>
          <p className="mt-1 text-sm text-muted">
            {poste.niveau_formation} · {experience(poste.experience_min_annees)}
          </p>
        </div>
        <div className="flex gap-2">
          <Bouton variante="secondaire" icone={Pencil} onClick={() => navigate(`/postes/${id}/modifier`)}>Modifier</Bouton>
          <Bouton variante="secondaire" icone={Trash2} onClick={() => setSuppression(true)} className="hover:text-danger">Supprimer</Bouton>
        </div>
      </div>

      {erreur && <div className="mb-4"><Alerte>{erreur}</Alerte></div>}

      <Carte className="mb-6 flex flex-wrap items-center justify-between gap-4 py-4">
        <p className="text-sm text-muted">
          {poste.statut === 'actif'
            ? 'Ce poste est actif : il servira au classement des candidatures.'
            : poste.statut === 'brouillon'
              ? "Ce poste est en brouillon : il n'est pas encore utilisé pour classer les candidatures."
              : "Ce poste est clôturé : il n'est plus utilisé pour classer les candidatures."}
        </p>
        <div className="flex gap-1 rounded-lg border border-line p-1" role="group" aria-label="Statut du poste">
          {Object.entries(STATUTS).map(([valeur, libelle]) => (
            <button
              key={valeur}
              type="button"
              disabled={changementStatut || poste.statut === valeur}
              aria-pressed={poste.statut === valeur}
              onClick={() => changerStatut(valeur)}
              className={`rounded-md px-3 py-1 text-sm font-medium transition-colors ${
                poste.statut === valeur ? 'bg-navy-900 text-white' : 'text-muted hover:bg-navy-50 hover:text-navy-900'
              }`}
            >
              {libelle}
            </button>
          ))}
        </div>
      </Carte>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="flex flex-col gap-6 lg:col-span-2">
          <Carte>
            <Titre>Description et missions</Titre>
            <p className="text-sm leading-relaxed whitespace-pre-line text-navy-800">{poste.description}</p>
          </Carte>
          {poste.processus_selection && (
            <Carte>
              <Titre>Processus de sélection</Titre>
              <p className="text-sm leading-relaxed whitespace-pre-line text-navy-800">{poste.processus_selection}</p>
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
              <dl className="flex flex-col gap-3">
                {conditions.map(([libelle, valeur]) => (
                  <div key={libelle} className="flex justify-between gap-4 text-sm">
                    <dt className="text-muted">{libelle}</dt>
                    <dd className="text-right font-medium text-navy-900">{valeur}</dd>
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
  return <h2 className="mb-3 text-xs font-semibold tracking-wide text-muted uppercase">{children}</h2>;
}

function Etiquettes({ titre, valeurs, accent }) {
  if (!valeurs?.length) return null;
  return (
    <div>
      <Titre>{titre}</Titre>
      <ul className="flex flex-wrap gap-1.5">
        {valeurs.map((v) => (
          <li key={v} className={`rounded-full px-3 py-1 text-sm ${accent ? 'bg-brand-50 text-brand-700' : 'bg-navy-50 text-navy-800'}`}>{v}</li>
        ))}
      </ul>
    </div>
  );
}
