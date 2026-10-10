// Éléments d'affichage des mails aux candidats : aperçu d'un mail, état des envois.
import { CircleAlert, MailCheck } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Badge } from '../components/ui.jsx';
import { formaterDateHeure } from '../format.js';

export const TYPES_MAIL = { invitation: 'Invitation', modification: "Modification de l'entretien", refus: 'Réponse négative' };
const COURTS = { invitation: 'Invitation', modification: 'Modification', refus: 'Réponse négative' };

/** Un mail tel qu'il partira : objet, destinataire, puis la version mise en forme (ou le texte). */
export function ApercuMail({ objet, corps, html, destinataire, note }) {
  return (
    <div className="overflow-hidden rounded-lg border border-trait bg-enfonce text-sm">
      <div className="border-b border-trait px-4 py-3">
        {note && <p className="mb-1 text-xs text-tenu">{note}</p>}
        <p className="font-semibold text-fort">{objet}</p>
        {destinataire && <p className="mt-0.5 text-xs text-doux">À : {destinataire}</p>}
      </div>
      {html ? <MailRendu html={html} /> : <p className="px-4 py-3 whitespace-pre-line text-texte">{corps}</p>}
    </div>
  );
}

/**
 * Le HTML du mail, isolé dans un cadre sans scripts ; sa hauteur suit le contenu. Les liens ne sont pas cliquables
 * dans l'aperçu (le cadre ne doit jamais charger une page extérieure).
 */
export function MailRendu({ html, className = '' }) {
  const cadre = useRef(null);
  const [hauteur, setHauteur] = useState(420);
  const ajuster = () => {
    const doc = cadre.current?.contentDocument;
    const h = doc?.documentElement?.scrollHeight;
    if (h) setHauteur(h); // 0 quand le cadre est masqué (onglet inactif) : on garde la hauteur connue
  };
  // Remesure quand le cadre devient visible ou change de largeur
  useEffect(() => {
    if (!cadre.current || typeof ResizeObserver === 'undefined') return undefined;
    const observateur = new ResizeObserver(ajuster);
    observateur.observe(cadre.current);
    return () => observateur.disconnect();
  }, []);
  return (
    <iframe
      ref={cadre}
      title="Aperçu du mail"
      sandbox="allow-same-origin"
      srcDoc={html}
      onLoad={ajuster}
      style={{ height: hauteur, pointerEvents: 'none' }}
      className={`block w-full border-0 bg-[#f2f5f9] ${className}`}
    />
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
