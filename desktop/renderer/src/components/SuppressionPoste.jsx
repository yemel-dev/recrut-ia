import { useState } from 'react';
import { api } from '../api.js';
import { Alerte, Confirmation } from './ui.jsx';

/** Demande confirmation, puis supprime le poste. `poste` à null : boîte fermée. */
export default function SuppressionPoste({ poste, onSupprime, onAnnuler }) {
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState('');

  const confirmer = async () => {
    setEnvoi(true);
    setErreur('');
    try {
      await api.delete(`/postes/${poste.id}`);
      onSupprime(poste);
    } catch (err) {
      setErreur(err.message);
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <Confirmation
      ouverte={Boolean(poste)}
      titre="Supprimer ce poste ?"
      libelleConfirmer="Supprimer définitivement"
      chargement={envoi}
      onConfirmer={confirmer}
      onAnnuler={() => {
        setErreur('');
        onAnnuler();
      }}
    >
      <p>
        Le poste <strong className="text-navy-900">« {poste?.intitule} »</strong> sera supprimé définitivement. Cette
        action ne peut pas être annulée.
      </p>
      {poste?.statut === 'actif' && (
        <p className="mt-2">S'il s'agit seulement d'arrêter le recrutement, vous pouvez plutôt le clôturer.</p>
      )}
      {erreur && <div className="mt-3"><Alerte>{erreur}</Alerte></div>}
    </Confirmation>
  );
}
