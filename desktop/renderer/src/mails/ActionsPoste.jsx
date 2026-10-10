// Actions d'un poste sur les mails : envoyer les invitations, envoyer (ou relancer) les réponses négatives.
// La clôture du poste envoie d'elle-même la réponse négative aux non retenus (pages/PosteDetail.jsx).
import { CalendarCheck, MailX } from 'lucide-react';
import { useState } from 'react';
import { api } from '../api.js';
import { Bouton, Carte } from '../components/ui.jsx';
import FenetreEnvoi from './FenetreEnvoi.jsx';

const TITRES = { invitation: 'Envoyer les invitations', refus: 'Envoyer les réponses négatives' };

export default function ActionsPoste({ posteId, onChange }) {
  const [envoi, setEnvoi] = useState(null); // type en cours : invitation | refus

  return (
    <Carte className="mb-6 flex flex-wrap items-center justify-between gap-3 py-3.5">
      <p className="text-sm text-doux">
        Mails aux candidats : vous invitez vous-même les retenus. À la clôture du poste, les autres reçoivent la réponse négative.
      </p>
      <div className="flex flex-wrap gap-2">
        <Bouton variante="secondaire" taille="sm" icone={CalendarCheck} onClick={() => setEnvoi('invitation')}>Envoyer les invitations</Bouton>
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
    </Carte>
  );
}
