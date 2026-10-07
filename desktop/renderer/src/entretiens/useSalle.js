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

  const salle = useRef({ pc: null, ice: [], local: null, file: Promise.resolve(), desabonner: [], pret: Promise.resolve() });

  const fermerPair = useCallback(() => {
    salle.current.pc?.close();
    salle.current.pc = null;
    setFluxDistant(null);
    setCandidatConnecte(false);
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
    pc.onconnectionstatechange = () => setCandidatConnecte(pc.connectionState === 'connected');
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

  // Quitter la page ferme la salle (caméra éteinte, connexion coupée).
  useEffect(() => () => fermer(), [fermer]);

  return { etat, candidatPresent, candidatConnecte, erreur, fluxLocal, fluxDistant, ouvrir, fermer };
}
