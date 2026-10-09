import { Activity, ClipboardCheck, Info, UserPlus } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api.js';
import { useAgent } from '../agent/ContexteAgent.jsx';
import { Alerte, Chargement, Confirmation } from '../components/ui.jsx';
import { creerEnregistreur, enregistrementPossible } from '../entretiens/enregistreur.js';
import { creerAnalyseurRegard } from '../entretiens/regard.js';
import { AlerteSalle } from '../entretiens/salle/elements.jsx';
import PanneauLateral from '../entretiens/salle/PanneauLateral.jsx';
import { compterSignaux } from '../entretiens/salle/panneaux.jsx';
import { BarreCommandes, BarreSuperieure } from '../entretiens/salle/Barres.jsx';
import { formaterDuree, phaseSalle, secondesDepuis } from '../entretiens/salle/phase.js';
import Scene from '../entretiens/salle/Scene.jsx';
import { useSalle } from '../entretiens/useSalle.js';

/** Salle d'entretien vidéo : la logique (salle WebRTC, enregistrement, regard, fin d'entretien) est ici ; la présentation est dans entretiens/salle/. */
export default function Entretien() {
  const entretienId = Number(useParams().id);
  const { notifier } = useAgent();
  const [entretien, setEntretien] = useState(null);
  const [candidature, setCandidature] = useState(null);
  const [erreur, setErreur] = useState('');
  const [occupe, setOccupe] = useState(false);
  const [confirmerFin, setConfirmerFin] = useState(false);
  const [enregistrement, setEnregistrement] = useState('inactif'); // inactif | actif | erreur
  const [panneau, setPanneau] = useState({ ouvert: false, onglet: 'details' });
  const [imageRecue, setImageRecue] = useState(false); // le flux du candidat affiche réellement une image
  const [maintenant, setMaintenant] = useState(Date.now());
  const salle = useSalle(entretienId);
  const enregistreur = useRef(null);
  const analyseur = useRef(null);
  const panneauInitialise = useRef(false);
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
      setPanneau((p) => (p.onglet === 'invitation' ? { ...p, ouvert: false } : p)); // l'entretien commence : la vidéo reprend la place
      const complet = await charger();
      if (!complet) setEntretien((prev) => ({ ...prev, ...e })); // relecture impossible : au moins le nouveau statut, sans perdre les alertes
      const courant = complet || e; // la fiche complète (alertes, consentement le plus récent) remplace la réponse du statut
      if (courant.consentement_enregistrement) {
        demarrerRegard();
      }
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

  const DELAI_ENREGISTREMENT_MS = 30_000;
  /** Résultat de la promesse, ou `false` si elle dépasse le délai (elle continue alors en arrière-plan). */
  const attendreAuPlus = (promesse, ms) =>
    Promise.race([promesse.then((v) => (v === undefined ? true : v)), new Promise((r) => setTimeout(() => r(false), ms))]);

  const terminer = async () => {
    setOccupe(true);
    setErreur('');
    try {
      analyseur.current?.arreter(); // plus d'images : le backend calcule le bilan à la fin de l'entretien
      analyseur.current = null;
      setRegard((r) => ({ ...r, actif: false }));
      // L'enregistrement est clos avant l'entretien : le backend refuse les morceaux d'un entretien terminé.
      if (enregistreur.current) {
        const complet = await attendreAuPlus(enregistreur.current.arreter(), DELAI_ENREGISTREMENT_MS);
        enregistreur.current = null;
        setEnregistrement('inactif');
        if (complet !== true) setErreur("L'enregistrement est incomplet : un morceau n'a pas pu être enregistré.");
      }
      setEntretien(await api.put(`/entretiens/${entretienId}/statut`, { statut: 'termine' }));
      setPanneau({ ouvert: true, onglet: 'bilan' });
      salle.fermer();
      setConfirmerFin(false);
      notifier('Entretien terminé.', 'succes');
    } catch (err) {
      setErreur(err.message);
    } finally {
      setOccupe(false);
    }
  };

  const [rapportEnCours, setRapportEnCours] = useState(false);
  const exporterRapport = async () => {
    setErreur('');
    setRapportEnCours(true);
    try {
      const resultat = await window.injara.fichiers.exporterRapport(entretien.candidature_id);
      if (resultat.ok) notifier(`Rapport enregistré : ${resultat.chemin}`, 'succes');
      else if (!resultat.annule) setErreur(resultat.message);
    } catch (err) {
      setErreur(err.message);
    } finally {
      setRapportEnCours(false);
    }
  };

  const exporter = async () => {
    setErreur('');
    const resultat = await window.injara.entretien.exporterEnregistrement(entretienId);
    if (resultat.ok) notifier(`Enregistrement exporté : ${resultat.chemin}`, 'succes');
    else if (!resultat.annule) setErreur(resultat.message);
  };

  // Panneau latéral : ouvert d'emblée quand il y a quelque chose à faire (inviter, consulter le bilan).
  useEffect(() => {
    if (!entretien || panneauInitialise.current) return;
    panneauInitialise.current = true;
    const large = window.matchMedia('(min-width: 1024px)').matches; // sur fenêtre étroite, le panneau est un tiroir : fermé au départ
    if (entretien.statut === 'planifie') setPanneau({ ouvert: large, onglet: 'invitation' });
    else if (entretien.statut === 'termine') setPanneau({ ouvert: large, onglet: 'bilan' });
    else setPanneau({ ouvert: false, onglet: entretien.statut === 'en_cours' ? 'suivi' : 'details' });
  }, [entretien]);

  // Image réellement reçue du candidat : seule preuve que la vidéo arrive (l'état WebRTC seul ne suffit pas).
  useEffect(() => {
    setImageRecue(false);
    const video = refDistant.current;
    if (!video || !salle.fluxDistant) return undefined;
    const arrivee = () => setImageRecue(true);
    video.addEventListener('playing', arrivee);
    video.addEventListener('loadeddata', arrivee);
    return () => {
      video.removeEventListener('playing', arrivee);
      video.removeEventListener('loadeddata', arrivee);
    };
  }, [salle.fluxDistant]);

  const enCoursChrono = entretien?.statut === 'en_cours';
  useEffect(() => {
    if (!enCoursChrono) return undefined;
    const minuteur = setInterval(() => setMaintenant(Date.now()), 1000);
    return () => clearInterval(minuteur);
  }, [enCoursChrono]);

  if (!entretien) return <div className="p-8">{erreur ? <Alerte>{erreur}</Alerte> : <Chargement />}</div>;

  const nom = candidature?.nom || candidature?.email || `Candidature ${entretien.candidature_id}`;
  const ouvertAuxEchanges = ['planifie', 'en_cours'].includes(entretien.statut);
  const phase = phaseSalle({ entretien, salle, imageRecue });
  const duree = enCoursChrono ? formaterDuree(secondesDepuis(entretien.debut_le, maintenant)) : null;

  const onglets = ouvertAuxEchanges
    ? [
        { id: 'invitation', libelle: 'Invitation', icone: UserPlus },
        { id: 'suivi', libelle: 'Suivi', icone: Activity, badge: compterSignaux(entretien) },
        { id: 'details', libelle: 'Infos', icone: Info },
      ]
    : entretien.statut === 'termine'
      ? [
          { id: 'bilan', libelle: 'Bilan', icone: ClipboardCheck },
          { id: 'details', libelle: 'Infos', icone: Info },
        ]
      : [{ id: 'details', libelle: 'Infos', icone: Info }];
  const ongletActif = (onglets.find((o) => o.id === panneau.onglet) ?? onglets[0]).id;
  const choisirOnglet = (id) => setPanneau((p) => (p.ouvert && p.onglet === id ? { ...p, ouvert: false } : { ouvert: true, onglet: id }));
  const ouvrirOnglet = (id) => setPanneau({ ouvert: true, onglet: id });

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 bg-nuit-900 p-3 sm:p-4">
      <BarreSuperieure
        entretien={entretien}
        nom={nom}
        poste={candidature?.poste_intitule}
        phase={phase}
        duree={duree}
        enregistrement={enregistrement}
        panneauOuvert={panneau.ouvert}
        onPanneau={() => setPanneau((p) => ({ ...p, ouvert: !p.ouvert }))}
      />

      {(erreur || salle.erreur) && (
        <div className="flex flex-col gap-2">
          {erreur && <AlerteSalle>{erreur}</AlerteSalle>}
          {salle.erreur && <AlerteSalle>{salle.erreur}</AlerteSalle>}
        </div>
      )}

      <div className="relative flex min-h-0 flex-1 gap-3">
        <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-3">
          <Scene
            phase={phase}
            nom={nom}
            entretien={entretien}
            salle={salle}
            refDistant={refDistant}
            refLocal={refLocal}
            onOuvrir={salle.ouvrir}
            onInviter={() => ouvrirOnglet('invitation')}
            onAide={() => ouvrirOnglet('invitation')}
            onBilan={() => ouvrirOnglet('bilan')}
          />
          <BarreCommandes
            entretien={entretien}
            salle={salle}
            occupe={occupe}
            onOuvrirSalle={salle.ouvrir}
            onDemarrer={demarrer}
            onTerminer={() => setConfirmerFin(true)}
            onglets={onglets}
            ongletActif={ongletActif}
            panneauOuvert={panneau.ouvert}
            onChoisirOnglet={choisirOnglet}
          />
        </div>

        {panneau.ouvert && (
          <PanneauLateral
            onglet={ongletActif}
            onglets={onglets}
            onChoisir={(id) => setPanneau({ ouvert: true, onglet: id })}
            onFermer={() => setPanneau((p) => ({ ...p, ouvert: false }))}
            entretien={entretien}
            regard={regard}
            enregistrement={enregistrement}
            salle={salle}
            rapportEnCours={rapportEnCours}
            onRapport={exporterRapport}
            onExporter={exporter}
          />
        )}
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
    </div>
  );
}
