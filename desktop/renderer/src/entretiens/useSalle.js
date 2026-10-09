// Salle de visio côté recruteur : caméra locale, signalisation (relayée par le processus principal) et connexion WebRTC.
// Le recruteur lance la négociation dès que le candidat est présent ; il relance à chaque reconnexion du candidat.

import { useCallback, useEffect, useRef, useState } from 'react';

export function useSalle(entretienId) {
  const [etat, setEtat] = useState('fermee'); // fermee | ouverture | ouverte
  const [candidatPresent, setCandidatPresent] = useState(false);
  const [candidatConnecte, setCandidatConnecte] = useState(false); // le flux vidéo arrive
  const [erreur, setErreur] = useState('');
  const [fluxLocal, setFluxLocal] = useState(null);
  const [fluxDistant, setFluxDistant] = useState(null);
  const [etatConnexion, setEtatConnexion] = useState('new'); // état WebRTC réel : new | connecting | connected | disconnected | failed | closed
  const [microActif, setMicroActif] = useState(true);
  const [cameraActive, setCameraActive] = useState(true);

  const salle = useRef({ pc: null, ice: [], local: null, file: Promise.resolve(), desabonner: [], pret: Promise.resolve() });

  const fermerPair = useCallback(() => {
    salle.current.pc?.close();
    salle.current.pc = null;
    setFluxDistant(null);
    setCandidatConnecte(false);
    setEtatConnexion('new');
  }, []);

  const envoyer = (type, donnees) => window.injara.entretien.envoyer(JSON.stringify({ type, donnees }));

  const proposer = useCallback(async () => {
    fermerPair();
    const s = salle.current;
    const pc = new RTCPeerConnection({ iceServers: s.ice });
    s.pc = pc;
    s.local.getTracks().forEach((piste) => pc.addTrack(piste, s.local));
    pc.onicecandidate = (e) => e.candidate && envoyer('ice', e.candidate.toJSON());
    pc.ontrack = (e) => setFluxDistant(e.streams[0]);
    pc.onconnectionstatechange = () => {
      if (salle.current.pc !== pc) return; // une ancienne connexion ne doit pas écraser l'état de la nouvelle
      setCandidatConnecte(pc.connectionState === 'connected');
      setEtatConnexion(pc.connectionState);
    };
    await pc.setLocalDescription(await pc.createOffer());
    await envoyer('offre', pc.localDescription.toJSON());
  }, [fermerPair]);

  const traiter = useCallback(
    async (texte) => {
      await salle.current.pret; // la présence du candidat arrive avant que les serveurs ICE soient connus
      const { type, donnees, candidat } = JSON.parse(texte);
      const { pc } = salle.current;
      if (type === 'presence') {
        setCandidatPresent(Boolean(candidat));
        if (candidat) await proposer();
        else fermerPair();
      } else if (type === 'reponse' && pc) {
        await pc.setRemoteDescription(donnees);
      } else if (type === 'ice' && pc?.remoteDescription) {
        await pc.addIceCandidate(donnees);
      }
    },
    [proposer, fermerPair],
  );

  const fermer = useCallback(() => {
    const s = salle.current;
    s.desabonner.forEach((f) => f());
    s.desabonner = [];
    fermerPair();
    s.local?.getTracks().forEach((t) => t.stop());
    s.local = null;
    setFluxLocal(null);
    setCandidatPresent(false);
    setMicroActif(true);
    setCameraActive(true);
    setEtat('fermee');
    window.injara.entretien.fermerSalle();
  }, [fermerPair]);

  const ouvrir = useCallback(async () => {
    const s = salle.current;
    setErreur('');
    setEtat('ouverture');
    try {
      s.local = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 } }, audio: { echoCancellation: true, noiseSuppression: true } });
    } catch {
      setErreur("Impossible d'accéder à votre caméra et à votre micro. Vérifiez qu'ils sont branchés et non utilisés par un autre logiciel.");
      setEtat('fermee');
      return;
    }
    setFluxLocal(s.local);
    let pret;
    s.pret = new Promise((resolve) => (pret = resolve));
    s.desabonner = [
      // Messages traités un par un, dans l'ordre (offre, réponse puis candidats ICE).
      window.injara.entretien.surMessage((texte) => {
        s.file = s.file.then(() => traiter(texte)).catch(() => setErreur('Un problème est survenu avec la connexion vidéo.'));
      }),
      window.injara.entretien.surFermeture(() => {
        setErreur((e) => e || "La salle d'entretien a été fermée.");
        fermer();
      }),
    ];
    const reponse = await window.injara.entretien.ouvrirSalle(entretienId);
    if (!reponse.ok) {
      setErreur(reponse.donnees?.detail || "La salle d'entretien n'a pas pu être ouverte.");
      pret();
      fermer();
      return;
    }
    s.ice = reponse.donnees.ice;
    pret();
    setEtat('ouverte');
  }, [entretienId, traiter, fermer]);

  // Couper le micro ou la caméra : la piste reste dans la connexion (pas de renégociation), elle envoie du silence ou du noir.
  const basculerPiste = useCallback((type, setActif) => {
    const pistes = salle.current.local?.[type === 'audio' ? 'getAudioTracks' : 'getVideoTracks']() ?? [];
    if (pistes.length === 0) return;
    const actif = !pistes[0].enabled;
    pistes.forEach((p) => (p.enabled = actif));
    setActif(actif);
  }, []);
  const basculerMicro = useCallback(() => basculerPiste('audio', setMicroActif), [basculerPiste]);
  const basculerCamera = useCallback(() => basculerPiste('video', setCameraActive), [basculerPiste]);

  // Quitter la page ferme la salle (caméra éteinte, connexion coupée).
  useEffect(() => () => fermer(), [fermer]);

  return {
    etat, candidatPresent, candidatConnecte, etatConnexion, erreur, fluxLocal, fluxDistant, ouvrir, fermer,
    microActif, cameraActive, basculerMicro, basculerCamera,
  };
}
