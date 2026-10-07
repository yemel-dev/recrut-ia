import { ArrowLeft, Check, Circle, Copy, Download, Eye, Globe, Mic, Power, Video, VideoOff } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api.js';
import { useAgent } from '../agent/ContexteAgent.jsx';
import { Alerte, Bouton, Carte, Chargement, Confirmation } from '../components/ui.jsx';
import { STATUTS_ENTRETIEN } from '../constantes.js';
import { creerEnregistreur, enregistrementPossible } from '../entretiens/enregistreur.js';
import { creerAnalyseurRegard } from '../entretiens/regard.js';
import { useSalle } from '../entretiens/useSalle.js';
import { formaterDateHeure } from '../format.js';

export default function Entretien() {
  const entretienId = Number(useParams().id);
  const { notifier } = useAgent();
  const [entretien, setEntretien] = useState(null);
  const [candidature, setCandidature] = useState(null);
  const [erreur, setErreur] = useState('');
  const [occupe, setOccupe] = useState(false);
  const [confirmerFin, setConfirmerFin] = useState(false);
  const [enregistrement, setEnregistrement] = useState('inactif'); // inactif | actif | erreur
  const salle = useSalle(entretienId);
  const enregistreur = useRef(null);
  const analyseur = useRef(null);
  const [regard, setRegard] = useState({ actif: false, etat: null, evenements: [], message: '' });
  const refDistant = useRef(null);
  const refLocal = useRef(null);

  const charger = useCallback(async () => {
    try {
      const e = await api.get(`/entretiens/${entretienId}`);
      setEntretien(e);
      return e;
    } catch (err) {
      setErreur(err.message);
      return null;
    }
  }, [entretienId]);

  useEffect(() => {
    charger().then((e) => e && api.get(`/candidatures/${e.candidature_id}`).then(setCandidature, () => {}));
  }, [charger]);

  // Le candidat peut donner son consentement après l'ouverture de la page : on relit régulièrement.
  const ouvert = entretien && ['planifie', 'en_cours'].includes(entretien.statut);
  useEffect(() => {
    if (!ouvert) return undefined;
    const minuteur = setInterval(charger, 4000);
    return () => clearInterval(minuteur);
  }, [ouvert, charger]);

  useEffect(() => {
    if (refLocal.current) refLocal.current.srcObject = salle.fluxLocal;
    enregistreur.current?.brancherAudio('local', salle.fluxLocal);
  }, [salle.fluxLocal]);
  useEffect(() => {
    if (refDistant.current) refDistant.current.srcObject = salle.fluxDistant;
    enregistreur.current?.brancherAudio('distant', salle.fluxDistant); // le candidat s'est reconnecté : nouveau flux, même fichier
  }, [salle.fluxDistant]);

  // Quitter la page pendant l'enregistrement : on envoie ce qui reste (l'entretien reste « en cours »).
  useEffect(() => () => void enregistreur.current?.arreter(), []);
  useEffect(() => () => analyseur.current?.arreter(), []);

  const demarrerRegard = () => {
    const a = creerAnalyseurRegard({
      entretienId,
      onResultat: ({ etat, evenements }) =>
        setRegard((r) => ({ ...r, actif: true, etat, evenements: [...evenements.map((e) => ({ ...e, a: new Date() })), ...r.evenements].slice(0, 5) })),
      onErreur: (message) => setRegard((r) => ({ ...r, actif: false, message })),
    });
    a.definirVideo(refDistant.current);
    a.demarrer();
    analyseur.current = a;
    setRegard({ actif: true, etat: null, evenements: [], message: '' });
  };

  const demarrer = async () => {
    setOccupe(true);
    setErreur('');
    try {
      const e = await api.put(`/entretiens/${entretienId}/statut`, { statut: 'en_cours' });
      setEntretien(e);
      const courant = (await charger()) || e; // consentement le plus récent
      if (courant.consentement_enregistrement) demarrerRegard();
      if (courant.consentement_enregistrement && enregistrementPossible()) {
        const enr = creerEnregistreur({
          entretienId,
          onErreur: (err) => {
            setEnregistrement('erreur');
            setErreur(`L'enregistrement a rencontré un problème : ${err?.message || 'erreur inconnue'}. L'entretien peut continuer.`);
          },
        });
        enr.definirVideo(refDistant.current);
        enr.brancherAudio('local', salle.fluxLocal);
        enr.brancherAudio('distant', salle.fluxDistant);
        enr.demarrer();
        enregistreur.current = enr;
        setEnregistrement('actif');
      }
    } catch (err) {
      setErreur(err.message);
    } finally {
      setOccupe(false);
    }
  };

  const terminer = async () => {
    setOccupe(true);
    setErreur('');
    try {
      analyseur.current?.arreter(); // plus d'images : le backend calcule le bilan à la fin de l'entretien
      analyseur.current = null;
      setRegard((r) => ({ ...r, actif: false }));
      // L'enregistrement est clos avant l'entretien : le backend refuse les morceaux d'un entretien terminé.
      if (enregistreur.current) {
        const complet = await enregistreur.current.arreter();
        enregistreur.current = null;
        setEnregistrement('inactif');
        if (!complet) setErreur("L'enregistrement est incomplet : un morceau n'a pas pu être enregistré.");
      }
      setEntretien(await api.put(`/entretiens/${entretienId}/statut`, { statut: 'termine' }));
      salle.fermer();
      setConfirmerFin(false);
      notifier('Entretien terminé.', 'succes');
    } catch (err) {
      setErreur(err.message);
    } finally {
      setOccupe(false);
    }
  };

  const exporter = async () => {
    setErreur('');
    const resultat = await window.injara.entretien.exporterEnregistrement(entretienId);
    if (resultat.ok) notifier(`Enregistrement exporté : ${resultat.chemin}`, 'succes');
    else if (!resultat.annule) setErreur(resultat.message);
  };

  if (!entretien) return erreur ? <Alerte>{erreur}</Alerte> : <Chargement />;

  const nom = candidature?.nom || candidature?.email || `Candidature ${entretien.candidature_id}`;
  const enCours = entretien.statut === 'en_cours';
  const planifie = entretien.statut === 'planifie';

  return (
    <>
      <Link to={`/candidatures/${entretien.candidature_id}`} className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-muted hover:text-navy-900">
        <ArrowLeft className="size-4" aria-hidden /> Fiche de {nom}
      </Link>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-navy-900">Entretien vidéo : {nom}</h1>
          <p className="mt-1 text-sm text-muted">
            {STATUTS_ENTRETIEN[entretien.statut]}
            {entretien.date_entretien && ` · prévu le ${formaterDateHeure(entretien.date_entretien)}`}
            {entretien.debut_le && ` · commencé le ${formaterDateHeure(entretien.debut_le)}`}
            {entretien.fin_le && ` · terminé le ${formaterDateHeure(entretien.fin_le)}`}
          </p>
        </div>
        {enregistrement === 'actif' && (
          <span className="inline-flex items-center gap-2 rounded-full bg-danger-50 px-3 py-1 text-sm font-semibold text-danger">
            <Circle className="size-3 animate-pulse fill-current" aria-hidden /> Enregistrement en cours
          </span>
        )}
      </div>

      {erreur && <div className="mb-4"><Alerte>{erreur}</Alerte></div>}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="flex flex-col gap-6 lg:col-span-2">
          {ouvert && (
            <Carte className="flex flex-col gap-4">
              <div className="relative aspect-video overflow-hidden rounded-lg bg-navy-900">
                <video ref={refDistant} autoPlay playsInline className="size-full object-contain" />
                {!salle.candidatConnecte && (
                  <p className="absolute inset-0 grid place-items-center px-6 text-center text-sm text-navy-100">
                    {salle.etat !== 'ouverte'
                      ? "Ouvrez la salle pour accueillir le candidat."
                      : salle.candidatPresent
                        ? 'Candidat présent, connexion de la vidéo…'
                        : 'En attente du candidat…'}
                  </p>
                )}
                <video ref={refLocal} autoPlay playsInline muted className="absolute right-3 bottom-3 w-1/4 min-w-28 -scale-x-100 rounded-lg border-2 border-white bg-black" />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {salle.etat === 'fermee' ? (
                  <Bouton icone={Video} chargement={salle.etat === 'ouverture'} onClick={salle.ouvrir}>Ouvrir la salle</Bouton>
                ) : (
                  <Bouton variante="secondaire" icone={VideoOff} disabled={enCours} onClick={salle.fermer} title={enCours ? "Terminez l'entretien d'abord" : undefined}>
                    Fermer la salle
                  </Bouton>
                )}
                {planifie && (
                  <Bouton icone={Mic} chargement={occupe} disabled={salle.etat !== 'ouverte' || !salle.candidatConnecte} onClick={demarrer}>
                    Démarrer l'entretien
                  </Bouton>
                )}
                {enCours && <Bouton variante="danger" icone={Power} onClick={() => setConfirmerFin(true)}>Terminer l'entretien</Bouton>}
              </div>
              {salle.erreur && <Alerte>{salle.erreur}</Alerte>}
              <p className="text-xs text-muted">
                {entretien.consentement_enregistrement
                  ? "Le candidat a consenti à l'enregistrement : il démarre avec l'entretien et reste sur cet ordinateur, chiffré."
                  : "Le candidat n'a pas (encore) consenti à l'enregistrement : l'entretien ne sera pas enregistré."}
              </p>
            </Carte>
          )}

          {enCours && <CarteRegard regard={regard} consentement={entretien.consentement_enregistrement} />}
          {entretien.statut === 'termine' && <CarteBilanRegard entretien={entretien} />}

          {entretien.statut === 'termine' && (
            <Carte className="flex flex-col gap-3">
              <h2 className="font-semibold text-navy-900">Enregistrement</h2>
              {entretien.enregistrement ? (
                <>
                  <p className="text-sm text-muted">
                    L'enregistrement est conservé chiffré par INJARA. Le fichier exporté, lui, n'est pas chiffré : rangez-le à un endroit protégé.
                  </p>
                  <div><Bouton icone={Download} onClick={exporter}>Enregistrer la vidéo sous…</Bouton></div>
                </>
              ) : (
                <p className="text-sm text-muted">Cet entretien n'a pas été enregistré.</p>
              )}
            </Carte>
          )}
          {entretien.statut === 'annule' && <Carte><p className="text-sm text-muted">Cet entretien a été annulé.</p></Carte>}
        </div>

        <div className="flex flex-col gap-6">{ouvert && <CarteInvitation entretien={entretien} />}</div>
      </div>

      <Confirmation
        ouverte={confirmerFin}
        titre="Terminer l'entretien ?"
        libelleConfirmer="Terminer"
        chargement={occupe}
        onConfirmer={terminer}
        onAnnuler={() => setConfirmerFin(false)}
      >
        L'enregistrement s'arrête et le candidat est déconnecté. Cette action est définitive.
      </Confirmation>
    </>
  );
}

/** Lien du candidat : il faut d'abord activer l'accès à distance (tunnel), jamais actif sans que le recruteur le demande. */
function CarteInvitation({ entretien }) {
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
    <Carte className="flex flex-col gap-3 text-sm">
      <h2 className="flex items-center gap-2 font-semibold text-navy-900"><Globe className="size-4" aria-hidden /> Invitation du candidat</h2>
      {erreur && <Alerte>{erreur}</Alerte>}
      {!tunnel ? (
        <Chargement />
      ) : lien ? (
        <>
          <p className="text-muted">Envoyez ce lien au candidat. Il l'ouvre dans son navigateur, sans rien installer.</p>
          <input readOnly value={lien.lien} onFocus={(e) => e.target.select()} aria-label="Lien d'entretien du candidat" className="w-full rounded-lg border border-line bg-mist px-3 py-2 text-xs text-navy-900" />
          <Bouton variante="secondaire" icone={copie ? Check : Copy} onClick={copier}>{copie ? 'Lien copié' : 'Copier le lien'}</Bouton>
          {lien.expire_le && <p className="text-xs text-muted">Valable jusqu'au {formaterDateHeure(lien.expire_le)}.</p>}
          <Bouton variante="discret" chargement={occupe} onClick={basculer}>Désactiver l'accès à distance</Bouton>
        </>
      ) : (
        <>
          <p className="text-muted">
            Pour que le candidat vous rejoigne, INJARA ouvre un accès temporaire depuis Internet vers la seule page d'entretien. Le reste d'INJARA reste inaccessible, et l'accès se coupe à votre déconnexion.
          </p>
          {!tunnel.disponible && (
            <Alerte>Aucun outil de tunnel n'est installé sur cet ordinateur (cloudflared ou ngrok). Installez-en un, puis revenez ici.</Alerte>
          )}
          <Bouton icone={Globe} chargement={occupe} disabled={!tunnel.disponible} onClick={basculer}>Activer l'accès à distance</Bouton>
        </>
      )}
    </Carte>
  );
}

const ETATS_REGARD = {
  attentif: ['Face à l\'écran', 'bg-emerald-50 text-emerald-700'],
  regard_detourne: ['Regard détourné', 'bg-amber-50 text-amber-700'],
  visage_absent: ['Visage absent', 'bg-danger-50 text-danger'],
  plusieurs_visages: ['Plusieurs visages', 'bg-danger-50 text-danger'],
};
const LIBELLES_ALERTE = { regard_detourne: 'Regard détourné', visage_absent: 'Visage absent', plusieurs_visages: 'Plusieurs visages dans l\'image' };

/** Indicateur en direct. Ce n'est qu'une aide : un regard qui s'éloigne un instant n'a rien d'anormal. */
function CarteRegard({ regard, consentement }) {
  const [libelle, couleur] = ETATS_REGARD[regard.etat] || ['En attente d\'images…', 'bg-mist text-muted'];
  return (
    <Carte className="flex flex-col gap-3 text-sm">
      <h2 className="flex items-center gap-2 font-semibold text-navy-900"><Eye className="size-4" aria-hidden /> Regard et mouvements de tête</h2>
      {!consentement ? (
        <p className="text-muted">Le candidat n'a pas consenti : son regard n'est pas analysé.</p>
      ) : regard.message ? (
        <Alerte>{regard.message}</Alerte>
      ) : !regard.actif ? (
        <p className="text-muted">L'analyse démarre avec l'entretien.</p>
      ) : (
        <>
          <span className={`inline-flex w-fit rounded-full px-3 py-1 font-semibold ${couleur}`}>{libelle}</span>
          {regard.evenements.length > 0 && (
            <ul className="flex flex-col gap-1 text-xs text-muted">
              {regard.evenements.map((e, i) => <li key={i}>{e.a.toLocaleTimeString('fr-FR')} · {LIBELLES_ALERTE[e.type] || e.type}</li>)}
            </ul>
          )}
          <p className="text-xs text-muted">Indicateur seulement : il ne décide de rien. Les images ne sont pas conservées.</p>
        </>
      )}
    </Carte>
  );
}

function CarteBilanRegard({ entretien }) {
  const b = entretien.bilan_regard;
  const alertes = entretien.alertes.filter((a) => LIBELLES_ALERTE[a.type]);
  return (
    <Carte className="flex flex-col gap-3 text-sm">
      <h2 className="flex items-center gap-2 font-semibold text-navy-900"><Eye className="size-4" aria-hidden /> Regard et mouvements de tête</h2>
      {!b ? (
        <p className="text-muted">Aucune analyse pour cet entretien (pas de consentement, ou aucune image analysée).</p>
      ) : (
        <>
          <p className="text-2xl font-bold text-navy-900">{Math.round(entretien.score_regard)}<span className="text-sm font-medium text-muted"> / 100</span></p>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1">
            <dt className="text-muted">Face à l'écran</dt><dd>{b.part_attentif} %</dd>
            <dt className="text-muted">Regard détourné</dt><dd>{b.part_regard_detourne} %</dd>
            <dt className="text-muted">Visage absent</dt><dd>{b.part_visage_absent} %</dd>
            <dt className="text-muted">Plusieurs visages</dt><dd>{b.part_plusieurs_visages} %</dd>
            <dt className="text-muted">Agitation de la tête</dt><dd>{b.agitation_tete_deg_par_min} °/min</dd>
          </dl>
          {alertes.length > 0 && (
            <ul className="flex flex-col gap-1 border-t border-line pt-2 text-xs text-muted">
              {alertes.map((a) => <li key={a.id}>{formaterDateHeure(a.horodatage)} · {LIBELLES_ALERTE[a.type]}</li>)}
            </ul>
          )}
          <p className="text-xs text-muted">Indicateur seulement : il ne modifie ni le score du CV ni votre décision.</p>
        </>
      )}
    </Carte>
  );
}
