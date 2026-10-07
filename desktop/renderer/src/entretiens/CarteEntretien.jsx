import { Video } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api.js';
import { Alerte, Bouton, Carte } from '../components/ui.jsx';
import { STATUTS_ENTRETIEN } from '../constantes.js';
import { formaterDateHeure } from '../format.js';

/** Entretien vidéo d'une candidature : invitation, reprise de l'entretien en cours, historique. */
export default function CarteEntretien({ candidatureId, decision }) {
  const navigate = useNavigate();
  const [entretiens, setEntretiens] = useState(null);
  const [erreur, setErreur] = useState('');
  const [occupe, setOccupe] = useState(false);

  const charger = useCallback(() => {
    api.get(`/candidatures/${candidatureId}/entretiens`).then(setEntretiens, (err) => setErreur(err.message));
  }, [candidatureId]);
  useEffect(charger, [charger]);

  const inviter = async () => {
    setOccupe(true);
    setErreur('');
    try {
      const e = await api.post(`/candidatures/${candidatureId}/entretiens`, {});
      navigate(`/entretiens/${e.id}`);
    } catch (err) {
      setErreur(err.message);
      setOccupe(false);
    }
  };

  if (!entretiens) return erreur ? <Alerte>{erreur}</Alerte> : null;
  const actif = entretiens.find((e) => ['planifie', 'en_cours'].includes(e.statut));

  return (
    <Carte className="flex flex-col gap-3 text-sm">
      <h2 className="flex items-center gap-2 font-semibold text-navy-900"><Video className="size-4" aria-hidden /> Entretien vidéo</h2>
      {erreur && <Alerte>{erreur}</Alerte>}
      {actif ? (
        <Link to={`/entretiens/${actif.id}`} className="inline-flex justify-center rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700">
          {actif.statut === 'en_cours' ? "Reprendre l'entretien" : "Ouvrir l'entretien"}
        </Link>
      ) : (
        <>
          <Bouton icone={Video} chargement={occupe} onClick={inviter}>Inviter à un entretien vidéo</Bouton>
          {decision?.etat !== 'retenu' && <p className="text-xs text-muted">Ce candidat n'est pas marqué « Retenu », vous pouvez tout de même l'inviter.</p>}
        </>
      )}
      {entretiens.filter((e) => e !== actif).length > 0 && (
        <ul className="flex flex-col divide-y divide-line border-t border-line pt-1">
          {entretiens.filter((e) => e !== actif).map((e) => (
            <li key={e.id} className="flex items-center justify-between gap-3 py-2">
              <Link to={`/entretiens/${e.id}`} className="font-medium text-navy-900 hover:underline">{STATUTS_ENTRETIEN[e.statut]}</Link>
              <span className="text-xs text-muted">{formaterDateHeure(e.fin_le || e.cree_le || e.date_entretien)}</span>
            </li>
          ))}
        </ul>
      )}
    </Carte>
  );
}
