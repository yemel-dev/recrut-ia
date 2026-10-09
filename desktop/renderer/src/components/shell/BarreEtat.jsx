// Barre d'état (bas de fenêtre) : boîte mail, moteur d'analyse, connexion. Lecture seule, toujours visible.
import { CircleAlert, Cpu, Mail, WifiOff } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../api.js';
import { cx } from '../ui.jsx';

const heure = (iso) => (iso ? new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }) : null);

function Element({ children, className, ...props }) {
  const Comp = props.to ? Link : 'span';
  return (
    <Comp {...props} className={cx('inline-flex h-full items-center gap-1.5 px-2 whitespace-nowrap', props.to && 'rounded-sm transition-colors hover:bg-survol hover:text-texte', className)}>
      {children}
    </Comp>
  );
}

function Voyant({ ton }) {
  const couleurs = { actif: 'bg-accent', pause: 'bg-alerte', eteint: 'bg-tenu', erreur: 'bg-danger' };
  return <span className={cx('size-1.5 shrink-0 rounded-full', couleurs[ton])} aria-hidden />;
}

export default function BarreEtat({ statut, reconnexionConseillee }) {
  const [traitement, setTraitement] = useState(null);
  const [enLigne, setEnLigne] = useState(navigator.onLine);

  useEffect(() => {
    let actif = true;
    const lire = () => api.get('/traitement/etat').then((t) => actif && setTraitement(t), () => {});
    lire();
    const minuteur = setInterval(lire, 5000);
    return () => {
      actif = false;
      clearInterval(minuteur);
    };
  }, []);

  useEffect(() => {
    const maj = () => setEnLigne(navigator.onLine);
    window.addEventListener('online', maj);
    window.addEventListener('offline', maj);
    return () => {
      window.removeEventListener('online', maj);
      window.removeEventListener('offline', maj);
    };
  }, []);

  let boite;
  if (!statut) boite = { ton: 'eteint', texte: 'Boîte mail…' };
  else if (reconnexionConseillee && statut.connected) boite = { ton: 'erreur', texte: 'Boîte mail : vérifications en échec' };
  else if (!statut.connected) boite = { ton: 'eteint', texte: 'Aucune boîte mail liée' };
  else if (statut.needs_setup) boite = { ton: 'pause', texte: 'Boîte mail : configuration à terminer' };
  else if (statut.watching) {
    const h = heure(statut.last_sync_at);
    boite = { ton: 'actif', texte: `Boîte surveillée toutes les ${statut.poll_minutes} min${h ? ` · vérifiée à ${h}` : ''}` };
  } else boite = { ton: 'pause', texte: 'Surveillance de la boîte en pause' };

  const adequation = traitement?.adequation;
  let moteur = null;
  if (traitement?.en_cours) moteur = { texte: "L'IA analyse les candidatures…", ia: true };
  else if (adequation?.en_chargement) moteur = { texte: "Moteur d'analyse en chargement…", ia: true };
  else if (adequation && !adequation.disponible) moteur = { texte: 'Analyse sans le moteur sémantique' };
  else if (adequation) moteur = { texte: "Moteur d'analyse prêt" };

  return (
    <footer
      className="flex h-[var(--hauteur-etat)] shrink-0 items-center gap-1 border-t border-trait bg-chrome px-2 text-xs text-doux"
      aria-label="Barre d'état"
    >
      <Element to="/boite-mail" title="Ouvrir la boîte mail">
        {boite.ton === 'erreur' ? <CircleAlert className="size-3.5 text-danger" aria-hidden /> : <Mail className="size-3.5" aria-hidden />}
        <Voyant ton={boite.ton} />
        {boite.texte}
      </Element>

      {moteur && (
        <Element role="status">
          {moteur.ia ? (
            <span className="ia-pulsation size-2 rounded-full bg-accent shadow-[0_0_8px_var(--halo)]" aria-hidden />
          ) : (
            <Cpu className="size-3.5" aria-hidden />
          )}
          <span className={moteur.ia ? 'ia-reflet font-medium' : ''}>{moteur.texte}</span>
        </Element>
      )}

      <span className="flex-1" />

      {!enLigne && (
        <Element className="text-alerte" title="L'application fonctionne hors ligne ; la boîte mail et le lien des entretiens attendront le retour du réseau.">
          <WifiOff className="size-3.5" aria-hidden /> Hors ligne
        </Element>
      )}
      <Element className="text-tenu">Données sur cet ordinateur</Element>
    </footer>
  );
}
