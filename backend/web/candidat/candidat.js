// Page du candidat : rejoint l'entretien par WebRTC. Le recruteur lance la négociation ; ici on ne fait que répondre.
(() => {
  'use strict';
  const code = decodeURIComponent(location.pathname.split('/').filter(Boolean).pop() || '');
  const $ = (id) => document.getElementById(id);
  const ecrans = ['message', 'accueil', 'entretien'];
  const montrer = (nom) => ecrans.forEach((e) => ($(`ecran-${e}`).hidden = e !== nom));
  const message = (titre, texte) => {
    $('message-titre').textContent = titre;
    $('message-texte').textContent = texte;
    montrer('message');
  };

  let infos = null;
  let flux = null;
  let ws = null;
  let pc = null;
  let termine = false;
  let tentatives = 0;
  let file = Promise.resolve(); // les messages de signalisation sont traités un par un, dans l'ordre

  async function init() {
    try {
      const reponse = await fetch(`/public/api/${encodeURIComponent(code)}`, { cache: 'no-store' });
      if (!reponse.ok) throw new Error();
      infos = await reponse.json();
    } catch {
      message('Lien invalide', "Ce lien d'entretien est invalide ou a expiré. Contactez le recruteur pour en obtenir un nouveau.");
      return;
    }
    const contexte = [infos.poste && `Poste : ${infos.poste}`, infos.entreprise && `Entreprise : ${infos.entreprise}`].filter(Boolean);
    $('accueil-contexte').textContent = contexte.join(' · ');
    $('consentement').checked = Boolean(infos.consentement_enregistrement);
    montrer('accueil');
  }

  $('rejoindre').addEventListener('click', async () => {
    const erreur = $('erreur-acces');
    erreur.hidden = true;
    if (!navigator.mediaDevices?.getUserMedia) {
      erreur.textContent = "Ce navigateur ne permet pas la visioconférence. Utilisez Chrome, Edge ou Firefox à jour, en connexion sécurisée (https).";
      erreur.hidden = false;
      return;
    }
    try {
      flux = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 } }, audio: { echoCancellation: true, noiseSuppression: true } });
    } catch {
      erreur.textContent = "Impossible d'accéder à la caméra et au micro. Autorisez-les dans votre navigateur (icône à gauche de l'adresse), puis réessayez.";
      erreur.hidden = false;
      return;
    }
    try {
      const r = await fetch(`/public/api/${encodeURIComponent(code)}/consentement`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ accepte: $('consentement').checked }),
      });
      if (!r.ok) throw new Error();
    } catch {
      erreur.textContent = "Votre choix n'a pas pu être enregistré. Vérifiez votre connexion et réessayez.";
      erreur.hidden = false;
      flux.getTracks().forEach((t) => t.stop());
      return;
    }
    $('video-local').srcObject = flux;
    montrer('entretien');
    connecter();
  });

  $('micro').addEventListener('click', () => {
    const piste = flux?.getAudioTracks()[0];
    if (!piste) return;
    piste.enabled = !piste.enabled;
    $('micro').textContent = piste.enabled ? 'Couper le micro' : 'Réactiver le micro';
  });

  $('quitter').addEventListener('click', () => {
    if (!confirm("Quitter l'entretien ? Vous pourrez le rejoindre de nouveau avec le même lien tant qu'il n'est pas terminé.")) return;
    arreter();
    message('Vous avez quitté l\'entretien', 'Vous pouvez fermer cette page ou rouvrir votre lien pour revenir.');
  });

  function etat(texte) { $('etat').textContent = texte; }

  function connecter() {
    const protocole = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${protocole}://${location.host}/public/ws/candidat/${encodeURIComponent(code)}`);
    ws.onopen = () => { tentatives = 0; etat('Connecté. En attente du recruteur…'); };
    ws.onmessage = (e) => { file = file.then(() => traiter(JSON.parse(e.data))).catch(() => etat('Un problème est survenu avec la connexion vidéo.')); };
    ws.onclose = (e) => {
      if (termine) return;
      if (e.code === 4001) { arreter(); message('Entretien terminé', 'Merci pour votre temps. Vous pouvez fermer cette page.'); return; }
      if (e.code === 4404) { arreter(); message('Lien invalide', "Ce lien d'entretien est invalide ou a expiré."); return; }
      etat('Connexion perdue, nouvelle tentative…');
      fermerPair();
      setTimeout(connecter, Math.min(1000 * 2 ** tentatives++, 8000));
    };
  }

  function envoyer(type, donnees) {
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type, donnees }));
  }

  function fermerPair() {
    if (pc) { pc.close(); pc = null; }
    $('video-recruteur').srcObject = null;
    $('attente').hidden = false;
  }

  function nouveauPair() {
    fermerPair();
    pc = new RTCPeerConnection({ iceServers: infos.ice });
    flux.getTracks().forEach((piste) => pc.addTrack(piste, flux));
    pc.onicecandidate = (e) => { if (e.candidate) envoyer('ice', e.candidate.toJSON()); };
    pc.ontrack = (e) => { $('video-recruteur').srcObject = e.streams[0]; $('attente').hidden = true; };
    pc.onconnectionstatechange = () => {
      if (pc?.connectionState === 'connected') etat('Entretien en cours.');
      if (pc?.connectionState === 'failed') etat("La connexion vidéo a échoué. Rechargez la page ; si le problème persiste, essayez un autre réseau.");
    };
  }

  // Sous-titres (en différé) : la dernière phrase, effacée après quelques secondes de silence.
  let effacement = null;
  function sousTitre({ locuteur, texte }) {
    const zone = $('sous-titres');
    zone.replaceChildren();
    const qui = document.createElement('small');
    qui.textContent = locuteur === 'candidat' ? 'Vous' : 'Recruteur';
    zone.append(qui, document.createTextNode(String(texte).slice(0, 400)));  // textContent seulement : jamais de HTML
    zone.hidden = false;
    clearTimeout(effacement);
    effacement = setTimeout(() => { zone.hidden = true; }, 8000);
  }

  async function traiter({ type, donnees, recruteur, ...reste }) {
    if (type === 'soustitre') { sousTitre(reste); return; }
    if (type === 'presence') {
      if (!recruteur) { fermerPair(); etat('En attente du recruteur…'); }
      return;
    }
    if (type === 'offre') {
      nouveauPair();
      await pc.setRemoteDescription(donnees);
      await pc.setLocalDescription(await pc.createAnswer());
      envoyer('reponse', pc.localDescription.toJSON());
    } else if (type === 'ice' && pc?.remoteDescription) {
      await pc.addIceCandidate(donnees);
    }
  }

  function arreter() {
    termine = true;
    if (ws) ws.close();
    fermerPair();
    flux?.getTracks().forEach((t) => t.stop());
  }

  window.addEventListener('beforeunload', () => { if (ws) ws.close(); });
  init();
})();
