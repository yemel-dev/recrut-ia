// Carte « Mails » de la fiche candidat : état de chaque mail, relance d'un échec, renvoi explicite, modification.
import { Mail, RefreshCw, Send } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { api } from '../api.js';
import { Alerte, Bouton, Carte, cx } from '../components/ui.jsx';
import FenetreEnvoi from './FenetreEnvoi.jsx';
import { TYPES_MAIL, libelleEtat } from './elements.jsx';

export default function CarteMails({ candidatureId, decision, version }) {
  const [etat, setEtat] = useState(null);
  const [envoi, setEnvoi] = useState(null); // { type, forcer }

  const charger = useCallback(() => {
    api.get(`/candidatures/${candidatureId}/mails`).then(setEtat, () => {});
  }, [candidatureId]);
  useEffect(charger, [charger, version]);

  if (!etat) return null;
  const types = decision === 'retenu' ? ['invitation', 'modification'] : decision === 'ecarte' ? ['refus'] : [];
  const visibles = Object.keys(TYPES_MAIL).filter((t) => types.includes(t) || etat.etats[t].statut !== 'non_envoye');
  if (visibles.length === 0) return null;

  return (
    <Carte className="flex flex-col gap-3 text-base">
      <h2 className="titre-section flex items-center gap-2">
        <Mail className="size-4 text-doux" aria-hidden /> Mails au candidat
      </h2>
      {etat.destinataire ? (
        <p className="text-sm text-doux">Destinataire : {etat.destinataire}</p>
      ) : (
        <Alerte>Aucune adresse email connue pour ce candidat.</Alerte>
      )}
      {etat.modification_proposee && (
        <Alerte
          ton="alerte"
          titre="La date de l'entretien a changé depuis l'invitation."
          action={
            <Bouton variante="secondaire" taille="sm" icone={Send} onClick={() => setEnvoi({ type: 'modification', forcer: false })}>
              Prévenir le candidat
            </Bouton>
          }
        />
      )}
      <ul className="flex flex-col">
        {visibles.map((type) => {
          const e = etat.etats[type];
          const gerable = type !== 'modification' && types.includes(type);
          return (
            <li key={type} className="flex items-center justify-between gap-3 border-t border-trait py-2.5 first:border-t-0">
              <span className="min-w-0">
                <span className="block font-medium text-fort">{TYPES_MAIL[type]}</span>
                <span className={cx('block text-sm', e.statut === 'echec' ? 'text-danger' : 'text-doux')}>{libelleEtat(e)}</span>
              </span>
              {gerable && e.statut === 'echec' && (
                <Bouton variante="discret" taille="sm" icone={RefreshCw} geste="tourner" onClick={() => setEnvoi({ type, forcer: false })}>Relancer</Bouton>
              )}
              {gerable && e.statut === 'envoye' && (
                <Bouton variante="discret" taille="sm" icone={Send} onClick={() => setEnvoi({ type, forcer: true })}>Renvoyer</Bouton>
              )}
              {gerable && e.statut === 'non_envoye' && (
                <Bouton variante="secondaire" taille="sm" icone={Send} geste="avancer" onClick={() => setEnvoi({ type, forcer: false })}>Préparer</Bouton>
              )}
            </li>
          );
        })}
      </ul>
      <FenetreEnvoi
        ouverte={Boolean(envoi)}
        titre={envoi ? `${envoi.forcer ? 'Renvoyer' : 'Envoyer'} : ${TYPES_MAIL[envoi.type].toLowerCase()}` : ''}
        charger={() => api.get(`/candidatures/${candidatureId}/mails/${envoi.type}${envoi.forcer ? '?forcer=true' : ''}`)}
        envoyer={async () => {
          const r = await api.post(`/candidatures/${candidatureId}/mails/${envoi.type}`, { forcer: envoi.forcer });
          return { resultats: [r], envoyes: Number(r.statut === 'envoye'), echecs: Number(r.statut === 'echec'), ignores: 0 };
        }}
        onFerme={() => {
          setEnvoi(null);
          charger();
        }}
      />
    </Carte>
  );
}
