// Actions d'un poste sur les mails : envoyer les invitations, clôturer la sélection, envoyer les réponses négatives.
import { CalendarCheck, Lock, MailX } from 'lucide-react';
import { useState } from 'react';
import { api } from '../api.js';
import { useAgent } from '../agent/ContexteAgent.jsx';
import { Bouton, Carte, Confirmation } from '../components/ui.jsx';
import FenetreEnvoi from './FenetreEnvoi.jsx';

const TITRES = { invitation: 'Envoyer les invitations', refus: 'Envoyer les réponses négatives' };

export default function ActionsPoste({ posteId, onChange }) {
  const { notifier } = useAgent();
  const [envoi, setEnvoi] = useState(null); // type en cours : invitation | refus
  const [cloture, setCloture] = useState(null); // aperçu de la clôture
  const [chargement, setChargement] = useState(false);

  const ouvrirCloture = async () => {
    try {
      setCloture(await api.get(`/postes/${posteId}/cloture`));
    } catch (err) {
      notifier(err.message, 'erreur');
    }
  };

  const cloturer = async () => {
    setChargement(true);
    try {
      const r = await api.post(`/postes/${posteId}/cloture`);
      notifier(`${r.ecartes} candidature${r.ecartes > 1 ? 's' : ''} passée${r.ecartes > 1 ? 's' : ''} à « écarté ». Aucun mail n'est parti.`, 'succes');
      onChange?.();
    } catch (err) {
      notifier(err.message, 'erreur');
    } finally {
      setChargement(false);
      setCloture(null);
    }
  };

  return (
    <Carte className="mb-6 flex flex-wrap items-center justify-between gap-3 py-3.5">
      <p className="text-sm text-doux">Mails aux candidats : rien ne part sans votre confirmation.</p>
      <div className="flex flex-wrap gap-2">
        <Bouton variante="secondaire" taille="sm" icone={CalendarCheck} onClick={() => setEnvoi('invitation')}>Envoyer les invitations</Bouton>
        <Bouton variante="secondaire" taille="sm" icone={Lock} onClick={ouvrirCloture}>Clôturer la sélection</Bouton>
        <Bouton variante="secondaire" taille="sm" icone={MailX} onClick={() => setEnvoi('refus')}>Envoyer les réponses négatives</Bouton>
      </div>

      <FenetreEnvoi
        ouverte={Boolean(envoi)}
        titre={TITRES[envoi] || ''}
        charger={() => api.get(`/postes/${posteId}/envois/${envoi}`)}
        envoyer={(ids, echecsSeulement) => api.post(`/postes/${posteId}/envois/${envoi}`, { candidatures: ids, echecs_seulement: echecsSeulement })}
        onFerme={(aEnvoye) => {
          setEnvoi(null);
          if (aEnvoye) onChange?.();
        }}
      />
      <Confirmation
        ouverte={Boolean(cloture)}
        titre="Clôturer la sélection ?"
        variante="primaire"
        libelleConfirmer={`Écarter ${cloture?.a_ecarter ?? 0} candidature${cloture?.a_ecarter > 1 ? 's' : ''}`}
        chargement={chargement}
        onConfirmer={cloturer}
        onAnnuler={() => setCloture(null)}
      >
        {cloture && (
          <>
            Les <strong className="text-fort">{cloture.a_ecarter}</strong> candidature{cloture.a_ecarter > 1 ? 's' : ''} encore « à examiner »
            passeront à « écarté ». Les candidatures « en attente » ({cloture.en_attente}) et « retenu » ({cloture.retenus}) ne sont pas
            touchées.
            <br />
            Aucun mail ne part : les réponses négatives s'envoient ensuite, après confirmation.
          </>
        )}
      </Confirmation>
    </Carte>
  );
}
