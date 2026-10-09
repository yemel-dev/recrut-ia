// Contenu du panneau latéral de la salle : les fonctions secondaires de l'entretien (invitation, aide réseau, regard,
// vigilance, bilan). La logique (appels API, tunnel, TURN, copie du lien) est celle d'origine.
import { Check, Copy, Download, Eye, FileDown, Globe, ShieldAlert } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { api } from '../../api.js';
import { formaterDateHeure } from '../../format.js';
import { testerTurn } from '../testTurn.js';
import { AlerteSalle, BoutonSalle, Corps, Discret, Ligne, Section, SuccesSalle } from './elements.jsx';

/** Lien du candidat : il faut d'abord activer l'accès à distance (tunnel), jamais actif sans que le recruteur le demande. */
export function SectionInvitation({ entretien }) {
  const [tunnel, setTunnel] = useState(null);
  const [lien, setLien] = useState(null);
  const [erreur, setErreur] = useState('');
  const [occupe, setOccupe] = useState(false);
  const [copie, setCopie] = useState(false);

  const charger = useCallback(async () => {
    try {
      const t = await api.get('/tunnel');
      setTunnel(t);
      setLien(t.actif ? await api.get(`/entretiens/${entretien.id}/lien`) : null);
    } catch (err) {
      setErreur(err.message);
    }
  }, [entretien.id]);

  useEffect(() => {
    charger();
  }, [charger]);

  const basculer = async () => {
    setOccupe(true);
    setErreur('');
    try {
      if (tunnel.actif) await api.delete('/tunnel');
      else await api.post('/tunnel');
      await charger();
    } catch (err) {
      setErreur(err.message);
    } finally {
      setOccupe(false);
    }
  };

  const copier = async () => {
    await navigator.clipboard.writeText(lien.lien);
    setCopie(true);
    setTimeout(() => setCopie(false), 2000);
  };

  return (
    <>
      <Section titre="Invitation du candidat" icone={Globe}>
        {erreur && <AlerteSalle>{erreur}</AlerteSalle>}
        {!tunnel ? (
          <Discret>Chargement…</Discret>
        ) : lien ? (
          <>
            <Corps>Envoyez ce lien au candidat. Il l'ouvre dans son navigateur, sans rien installer.</Corps>
            <input
              readOnly
              value={lien.lien}
              onFocus={(e) => e.target.select()}
              aria-label="Lien d'entretien du candidat"
              className="w-full rounded-lg border border-sal-bord bg-sal-champ px-3 py-2.5 text-xs text-sal-fort"
            />
            <BoutonSalle variante="plein" icone={copie ? Check : Copy} onClick={copier}>{copie ? 'Lien copié' : 'Copier le lien'}</BoutonSalle>
            {lien.expire_le && <Discret>Valable jusqu'au {formaterDateHeure(lien.expire_le)}.</Discret>}
            <BoutonSalle variante="discret" chargement={occupe} onClick={basculer} className="self-start">Désactiver l'accès à distance</BoutonSalle>
          </>
        ) : (
          <>
            <Corps>
              Pour que le candidat vous rejoigne, INJARA ouvre un accès temporaire depuis Internet vers la seule page d'entretien. Le reste d'INJARA reste inaccessible, et l'accès se coupe à votre déconnexion.
            </Corps>
            {!tunnel.disponible && <AlerteSalle>Aucun outil de tunnel n'est installé sur cet ordinateur (cloudflared). Installez-le, puis revenez ici.</AlerteSalle>}
            <BoutonSalle variante="plein" icone={Globe} chargement={occupe} disabled={!tunnel.disponible} onClick={basculer}>Activer l'accès à distance</BoutonSalle>
          </>
        )}
      </Section>
      {lien && <ReseauTurn />}
    </>
  );
}

/** Serveur TURN : relaie la vidéo quand la connexion directe échoue (réseau d'entreprise, partage de connexion, éloignement). */
function ReseauTurn() {
  const [etat, setEtat] = useState(null);
  const [champs, setChamps] = useState({ urls: '', username: '', credential: '' });
  const [message, setMessage] = useState(null); // { ok, texte }
  const [occupe, setOccupe] = useState(false);

  const charger = useCallback(() => api.get('/reseau').then(setEtat, () => {}), []);
  useEffect(() => {
    charger();
  }, [charger]);

  const enregistrer = async (e) => {
    e.preventDefault();
    setOccupe(true);
    setMessage(null);
    try {
      const urls = champs.urls.split(/[\s,]+/).filter(Boolean);
      setEtat(await api.put('/reseau/turn', { urls, username: champs.username, credential: champs.credential }));
      setChamps({ urls: '', username: '', credential: '' });
      setMessage({ ok: true, texte: 'Serveur TURN enregistré. Testez-le maintenant.' });
    } catch (err) {
      setMessage({ ok: false, texte: err.message });
    } finally {
      setOccupe(false);
    }
  };

  const tester = async () => {
    setOccupe(true);
    setMessage(null);
    try {
      const { ice } = await api.get('/reseau/test');
      const resultat = await testerTurn(ice);
      setMessage({ ok: resultat.ok, texte: resultat.message });
    } catch (err) {
      setMessage({ ok: false, texte: err.message });
    } finally {
      setOccupe(false);
    }
  };

  const retirer = async () => {
    setOccupe(true);
    setMessage(null);
    try {
      setEtat(await api.delete('/reseau/turn'));
    } catch (err) {
      setMessage({ ok: false, texte: err.message });
    } finally {
      setOccupe(false);
    }
  };

  const champ = 'w-full rounded-lg border border-sal-bord bg-sal-champ px-3 py-2 text-xs text-sal-fort placeholder:text-sal-doux';
  const etiquette = 'flex flex-col gap-1 text-xs font-medium text-sal-corps';
  return (
    <details className="group border-b border-sal-bord px-5 py-4 text-sm">
      <summary className="cursor-pointer list-none font-semibold text-sal-fort marker:hidden [&::-webkit-details-marker]:hidden">
        <span className="mr-1.5 inline-block text-sal-doux transition-transform group-open:rotate-90" aria-hidden>›</span>
        Le candidat n'arrive pas à se connecter ?{' '}
        {(etat?.turn.configure || etat?.cloudflare.configure) && <span className="ml-1 text-xs font-normal text-vert-400">(TURN configuré)</span>}
      </summary>
      <div className="mt-3 flex flex-col gap-3">
        <Corps>
          Quand la connexion directe est impossible (réseau d'entreprise, partage de connexion, grande distance), le candidat reste sur « connexion en cours ». Un serveur TURN relaie alors la vidéo, toujours chiffrée.
          Prenez-en un chez un fournisseur (offre gratuite possible) ou installez le vôtre (coturn), puis saisissez ses informations.
        </Corps>
        {etat?.source_forcee && <AlerteSalle>La variable INJARA_ICE_SERVERS est définie : elle remplace cette configuration.</AlerteSalle>}
        {etat?.cloudflare.configure && !etat.turn.configure && (
          <div className="flex flex-col gap-2 rounded-lg bg-sal-creux p-3 text-xs text-sal-corps">
            <p><strong className="text-sal-fort">Cloudflare TURN</strong> est configuré dans le fichier .env : des identifiants temporaires sont demandés automatiquement.</p>
            <div><BoutonSalle chargement={occupe} onClick={tester}>Tester le serveur</BoutonSalle></div>
          </div>
        )}
        {etat?.turn.configure && (
          <div className="flex flex-col gap-2 rounded-lg bg-sal-creux p-3 text-xs text-sal-corps">
            <p><strong className="text-sal-fort">Adresses :</strong> {etat.turn.urls.join(', ')}</p>
            <p><strong className="text-sal-fort">Utilisateur :</strong> {etat.turn.username} · mot de passe enregistré (chiffré)</p>
            <div className="flex gap-2">
              <BoutonSalle chargement={occupe} onClick={tester}>Tester le serveur</BoutonSalle>
              <BoutonSalle variante="discret" disabled={occupe} onClick={retirer}>Retirer</BoutonSalle>
            </div>
          </div>
        )}
        {message && (message.ok ? <SuccesSalle>{message.texte}</SuccesSalle> : <AlerteSalle>{message.texte}</AlerteSalle>)}
        <form onSubmit={enregistrer} className="flex flex-col gap-2.5">
          <label className={etiquette}>
            Adresses du serveur (une par ligne)
            <textarea required rows={2} value={champs.urls} onChange={(e) => setChamps({ ...champs, urls: e.target.value })} placeholder={'turn:relais.exemple.com:3478\nturns:relais.exemple.com:443'} className={champ} />
          </label>
          <label className={etiquette}>
            Nom d'utilisateur
            <input required value={champs.username} onChange={(e) => setChamps({ ...champs, username: e.target.value })} autoComplete="off" className={champ} />
          </label>
          <label className={etiquette}>
            Mot de passe
            <input required type="password" value={champs.credential} onChange={(e) => setChamps({ ...champs, credential: e.target.value })} autoComplete="off" className={champ} />
          </label>
          <div><BoutonSalle type="submit" variante="plein" chargement={occupe}>{etat?.turn.configure ? 'Remplacer' : 'Enregistrer'}</BoutonSalle></div>
          <Discret>Ces identifiants sont transmis au navigateur du candidat, qui en a besoin pour se connecter : utilisez un compte dédié, que vous pouvez révoquer.</Discret>
        </form>
      </div>
    </details>
  );
}

const ETATS_REGARD = {
  attentif: ["Face à l'écran", 'bg-accent/15 text-sal-succes ring-accent/40'],
  regard_detourne: ['Regard détourné', 'bg-alerte/15 text-sal-alerte ring-alerte/40'],
  visage_absent: ['Visage absent', 'bg-danger/15 text-sal-danger ring-danger/40'],
  plusieurs_visages: ['Plusieurs visages', 'bg-danger/15 text-sal-danger ring-danger/40'],
};
export const LIBELLES_ALERTE = { regard_detourne: 'Regard détourné', visage_absent: 'Visage absent', plusieurs_visages: "Plusieurs visages dans l'image" };

/** Indicateur en direct. Ce n'est qu'une aide : un regard qui s'éloigne un instant n'a rien d'anormal. */
export function SectionRegard({ regard, consentement }) {
  const [libelle, couleur] = ETATS_REGARD[regard.etat] || ["En attente d'images…", 'bg-sal-creux text-sal-doux ring-sal-bord'];
  return (
    <Section titre="Regard et mouvements de tête" icone={Eye}>
      {!consentement ? (
        <Corps>Le candidat n'a pas consenti : son regard n'est pas analysé.</Corps>
      ) : regard.message ? (
        <AlerteSalle>{regard.message}</AlerteSalle>
      ) : !regard.actif ? (
        <Corps>L'analyse démarre avec l'entretien.</Corps>
      ) : (
        <>
          <span className={`inline-flex w-fit rounded-full px-3 py-1 text-sm font-semibold ring-1 ${couleur}`}>{libelle}</span>
          {regard.evenements.length > 0 && (
            <ul className="flex flex-col gap-1 text-xs text-sal-doux">
              {regard.evenements.map((e, i) => <li key={i}>{e.a.toLocaleTimeString('fr-FR')} · {LIBELLES_ALERTE[e.type] || e.type}</li>)}
            </ul>
          )}
          <Discret>Indicateur seulement : il ne décide de rien. Les images ne sont pas conservées.</Discret>
        </>
      )}
    </Section>
  );
}

export function SectionBilanRegard({ entretien }) {
  const b = entretien.bilan_regard;
  const alertes = (entretien.alertes ?? []).filter((a) => LIBELLES_ALERTE[a.type]);
  return (
    <Section titre="Regard et mouvements de tête" icone={Eye}>
      {!b ? (
        <Corps>Aucune analyse pour cet entretien (pas de consentement, ou aucune image analysée).</Corps>
      ) : (
        <>
          <p className="text-3xl font-bold text-sal-fort">{Math.round(entretien.score_regard)}<span className="text-sm font-medium text-sal-doux"> / 100</span></p>
          <dl className="divide-y divide-sal-bord">
            <Ligne libelle="Face à l'écran">{b.part_attentif} %</Ligne>
            <Ligne libelle="Regard détourné">{b.part_regard_detourne} %</Ligne>
            <Ligne libelle="Visage absent">{b.part_visage_absent} %</Ligne>
            <Ligne libelle="Plusieurs visages">{b.part_plusieurs_visages} %</Ligne>
            <Ligne libelle="Agitation de la tête">{b.agitation_tete_deg_par_min} °/min</Ligne>
          </dl>
          {alertes.length > 0 && (
            <ul className="flex flex-col gap-1 border-t border-sal-bord pt-2 text-xs text-sal-doux">
              {alertes.map((a) => <li key={a.id}>{formaterDateHeure(a.horodatage)} · {LIBELLES_ALERTE[a.type]}</li>)}
            </ul>
          )}
          <Discret>Indicateur seulement : il ne modifie ni le score du CV ni votre décision.</Discret>
        </>
      )}
    </Section>
  );
}

const SIGNAUX_PAGE = {
  perte_focus: "A quitté la page de l'entretien",
  sortie_plein_ecran: 'A quitté le plein écran',
  plusieurs_ecrans: 'Plusieurs écrans détectés',
};
const RAISONS = { onglet_masque: 'autre onglet ou fenêtre réduite', fenetre_inactive: 'autre fenêtre au premier plan' };

/** Nombre de signalements de la page du candidat (pastille de l'onglet « Suivi »). */
export const compterSignaux = (entretien) => (entretien.alertes ?? []).filter((a) => SIGNAUX_PAGE[a.type]).length;

/** Ce que la page du candidat a signalé. Une page web ne voit pas les autres programmes : ce sont des indices, pas des preuves. */
export function SectionVigilance({ entretien }) {
  const signaux = (entretien.alertes ?? []).filter((a) => SIGNAUX_PAGE[a.type]);
  return (
    <Section titre="Vigilance" icone={ShieldAlert}>
      <p className={entretien.consignes_acceptees_le ? 'text-sal-succes' : 'text-sal-corps'}>
        {entretien.consignes_acceptees_le
          ? `Le candidat s'est engagé à fermer les autres applications et fenêtres (${formaterDateHeure(entretien.consignes_acceptees_le)}).`
          : "Le candidat ne s'est pas (encore) engagé à respecter les consignes."}
      </p>
      {!entretien.consentement_enregistrement ? (
        <Corps>Le candidat n'a pas consenti : ses changements de page ne sont pas relevés.</Corps>
      ) : signaux.length === 0 ? (
        <Corps>Aucun signalement : le candidat est resté sur la page de l'entretien.</Corps>
      ) : (
        <ul className="flex flex-col gap-2">
          {signaux.map((a) => (
            <li key={a.id} className="flex flex-wrap gap-x-2 rounded-lg bg-alerte/10 px-3 py-2 ring-1 ring-alerte/25">
              <span className="text-sal-doux">{formaterDateHeure(a.horodatage)}</span>
              <span className="font-medium text-sal-alerte">{SIGNAUX_PAGE[a.type]}</span>
              {a.details?.duree_s != null && <span className="text-sal-doux">pendant {a.details.duree_s} s{a.details.raison ? ` (${RAISONS[a.details.raison] || a.details.raison})` : ''}</span>}
            </li>
          ))}
        </ul>
      )}
      <Discret>Un navigateur ne voit pas les autres programmes : il signale seulement que le candidat quitte la page, le plein écran, ou a un second écran. Une notification qui passe peut aussi le déclencher. Aucun contrôle des applications n'est possible.</Discret>
    </Section>
  );
}

/** Rapport PDF et vidéo de l'entretien terminé. */
export function SectionLivrables({ entretien, rapportEnCours, onRapport, onExporter }) {
  return (
    <>
      <Section titre="Rapport" icone={FileDown}>
        <Corps>Le rapport PDF du candidat reprend son CV, ce bilan d'entretien (regard, vigilance).</Corps>
        <BoutonSalle variante="bleu" icone={FileDown} chargement={rapportEnCours} onClick={onRapport} className="self-start">Exporter le rapport (PDF)</BoutonSalle>
      </Section>
      <Section titre="Enregistrement" icone={Download}>
        {entretien.enregistrement ? (
          <>
            <Corps>L'enregistrement est conservé chiffré par INJARA. Le fichier exporté, lui, n'est pas chiffré : rangez-le à un endroit protégé.</Corps>
            <BoutonSalle icone={Download} onClick={onExporter} className="self-start">Enregistrer la vidéo sous…</BoutonSalle>
          </>
        ) : (
          <Corps>Cet entretien n'a pas été enregistré.</Corps>
        )}
      </Section>
    </>
  );
}
