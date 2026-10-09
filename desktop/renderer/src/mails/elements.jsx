// Éléments d'affichage des mails aux candidats : aperçu d'un mail, état des envois.
import { CircleAlert, MailCheck } from 'lucide-react';
import { Badge } from '../components/ui.jsx';
import { formaterDateHeure } from '../format.js';

export const TYPES_MAIL = { invitation: 'Invitation', modification: "Modification de l'entretien", refus: 'Réponse négative' };
const COURTS = { invitation: 'Invitation', modification: 'Modification', refus: 'Réponse négative' };

/** Un mail tel qu'il partira (objet et texte). */
export function ApercuMail({ objet, corps, destinataire, note }) {
  return (
    <div className="rounded-md border border-trait bg-enfonce p-4 text-sm">
      {note && <p className="mb-2 text-xs text-tenu">{note}</p>}
      {destinataire && <p className="text-xs text-doux">À : {destinataire}</p>}
      <p className="font-semibold text-fort">{objet}</p>
      <p className="mt-2 whitespace-pre-line text-texte">{corps}</p>
    </div>
  );
}

/** État des mails sur une ligne du classement : seuls les mails envoyés ou en échec sont affichés. */
export function BadgesMails({ mails }) {
  if (!mails) return null;
  return Object.entries(mails)
    .filter(([, statut]) => statut === 'envoye' || statut === 'echec')
    .map(([type, statut]) => (
      <Badge key={type} ton={statut === 'echec' ? 'danger' : 'neutre'} title={statut === 'echec' ? `${COURTS[type]} : échec d'envoi` : `${COURTS[type]} envoyée`}>
        {statut === 'echec' ? <CircleAlert className="size-3" aria-hidden /> : <MailCheck className="size-3" aria-hidden />}
        {COURTS[type]}
        {statut === 'echec' ? ' : échec' : ''}
      </Badge>
    ));
}

export function libelleEtat(etat) {
  switch (etat?.statut) {
    case 'envoye':
      return `Envoyé le ${formaterDateHeure(etat.le)}`;
    case 'echec':
      return `Échec : ${etat.erreur}`;
    default:
      return 'Non envoyé';
  }
}
