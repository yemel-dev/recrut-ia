// Page du candidat : rejoint l'entretien par WebRTC. Le recruteur lance la négociation ; ici on ne fait que répondre.
(() => {
  'use strict';
  const code = decodeURIComponent(location.pathname.split('/').filter(Boolean).pop() || '');
  const $ = (id) => document.getElementById(id);
  const ecrans = ['message', 'accueil', 'entretien'];
  const montrer = (nom) => {
    ecrans.forEach((e) => ($(`ecran-${e}`).hidden = e !== nom));
    document.body.dataset.ecran = nom;
  };
  // ton : 'alerte' (lien invalide), 'ok' (entretien terminé), 'neutre' (le candidat est parti de lui-même)
  const ICONES_MESSAGE = { alerte: ['i-alert', 'pastille alerte'], ok: ['i-check', 'pastille'], neutre: ['i-user', 'pastille neutre'] };
  const message = (titre, texte, ton = 'alerte') => {
    const [icone, classes] = ICONES_MESSAGE[ton];
    $('message-icone-use').setAttribute('href', `#${icone}`);
    $('message-icone').className = classes;
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

  // Rien ne démarre sans l'engagement : la case commande le bouton.
  $('engagement').addEventListener('change', () => { $('rejoindre').disabled = !$('engagement').checked; });

  $('rejoindre').addEventListener('click', async () => {
    const erreur = $('erreur-acces');
    const vigilance = $('consentement').checked;
    if (vigilance) entrerPleinEcran(); // tout de suite : le navigateur n'accepte le plein écran qu'après un clic
    erreur.hidden = true;
    if (!navigator.mediaDevices?.getUserMedia) {
      erreur.textContent = "Ce navigateur ne permet pas la visioconférence. Utilisez Chrome, Edge ou Firefox à jour, en connexion sécurisée (https).";
      erreur.hidden = false;
      sortirPleinEcran();
      return;
    }
    try {
      flux = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 } }, audio: { echoCancellation: true, noiseSuppression: true } });
    } catch {
      erreur.textContent = "Impossible d'accéder à la caméra et au micro. Autorisez-les dans votre navigateur (icône à gauche de l'adresse), puis réessayez.";
      erreur.hidden = false;
      sortirPleinEcran();
      return;
    }
    try {
      const r = await fetch(`/public/api/${encodeURIComponent(code)}/consentement`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ accepte: vigilance, consignes: $('engagement').checked }),
      });
      if (!r.ok) throw new Error();
    } catch {
      erreur.textContent = "Votre choix n'a pas pu être enregistré. Vérifiez votre connexion et réessayez.";
      erreur.hidden = false;
      flux.getTracks().forEach((t) => t.stop());
      sortirPleinEcran();
      return;
    }
    $('video-local').srcObject = flux;
    montrer('entretien');
    connecter();
    if (vigilance) surveiller();
  });

  $('micro').addEventListener('click', () => {
    const piste = flux?.getAudioTracks()[0];
    if (!piste) return;
    piste.enabled = !piste.enabled;
    const libelle = piste.enabled ? 'Couper le micro' : 'Réactiver le micro';
    $('micro').setAttribute('aria-pressed', String(!piste.enabled));
    $('micro').setAttribute('aria-label', libelle);
    $('micro').title = libelle;
    $('micro').querySelector('.icone-actif').hidden = !piste.enabled;
    $('micro').querySelector('.icone-coupe').hidden = piste.enabled;
  });

  $('quitter').addEventListener('click', () => {
    if (!confirm("Quitter l'entretien ? Vous pourrez le rejoindre de nouveau avec le même lien tant qu'il n'est pas terminé.")) return;
    arreter();
    message('Vous avez quitté l\'entretien', 'Vous pouvez fermer cette page ou rouvrir votre lien pour revenir.', 'neutre');
  });

  function etat(texte) { $('etat').textContent = texte; }

  function connecter() {
    const protocole = location.protocol === 'https:' ? 'wss' : 'ws';
    ws = new WebSocket(`${protocole}://${location.host}/public/ws/candidat/${encodeURIComponent(code)}`);
    ws.onopen = () => { tentatives = 0; etat('Connecté. En attente du recruteur…'); };
    ws.onmessage = (e) => { file = file.then(() => traiter(JSON.parse(e.data))).catch(() => etat('Un problème est survenu avec la connexion vidéo.')); };
    ws.onclose = (e) => {
      if (termine) return;
      if (e.code === 4001) { arreter(); message('Entretien terminé', 'Merci pour votre temps. Vous pouvez fermer cette page.', 'ok'); return; }
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

  async function traiter({ type, donnees, recruteur }) {
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

  // --- Vigilance (seulement avec l'accord du candidat) -----------------------------------------------------
  // Une page web ne voit ni les autres programmes ni les autres fenêtres : elle sait seulement quand elle perd la
  // vue (onglet changé, fenêtre inactive), quand le plein écran est quitté et si l'ordinateur a plusieurs écrans.
  // Les signaux vont au recruteur ; ils sont indicatifs (une notification qui passe peut les déclencher).
  const DUREE_MIN_ABSENCE = 2000;
  let surveillance = false;
  let parti = null;

  function signaler(type, details = {}) {
    fetch(`/public/api/${encodeURIComponent(code)}/signal`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type, ...details }), keepalive: true,
    }).catch(() => {});  // un signal perdu ne doit jamais gêner l'entretien
  }

  function entrerPleinEcran() {
    try { document.documentElement.requestFullscreen?.()?.catch(() => {}); } catch { /* non pris en charge */ }
  }
  function sortirPleinEcran() {
    try { if (document.fullscreenElement) document.exitFullscreen(); } catch { /* déjà sorti */ }
  }
  $('plein-ecran').addEventListener('click', entrerPleinEcran);

  function absent(raison) { if (surveillance && parti === null) parti = { debut: Date.now(), raison }; }
  function revenu() {
    if (!surveillance || parti === null) return;
    const { debut, raison } = parti;
    parti = null;
    if (Date.now() - debut >= DUREE_MIN_ABSENCE) signaler('perte_focus', { duree_s: Math.round((Date.now() - debut) / 100) / 10, raison });
  }

  function surveiller() {
    surveillance = true;
    const peutPleinEcran = Boolean(document.documentElement.requestFullscreen);
    let etaitPleinEcran = Boolean(document.fullscreenElement);  // déjà entré avant que la surveillance démarre
    document.addEventListener('visibilitychange', () => (document.hidden ? absent('onglet_masque') : revenu()));
    window.addEventListener('blur', () => absent('fenetre_inactive'));
    window.addEventListener('focus', revenu);
    document.addEventListener('fullscreenchange', () => {
      const actif = Boolean(document.fullscreenElement);
      if (actif) etaitPleinEcran = true;
      if (surveillance && etaitPleinEcran && !actif) signaler('sortie_plein_ecran');
      $('rappel-plein-ecran').hidden = !surveillance || actif || !peutPleinEcran;
    });
    // Second écran : Chrome et Edge l'indiquent sans demander de permission ; ailleurs on ne peut pas le savoir.
    if (window.screen?.isExtended) signaler('plusieurs_ecrans');
    if (window.screen) window.screen.addEventListener?.('change', () => { if (window.screen.isExtended) signaler('plusieurs_ecrans'); });
  }

  function arreter() {
    surveillance = false;
    $('rappel-plein-ecran').hidden = true;
    sortirPleinEcran();
    termine = true;
    if (ws) ws.close();
    fermerPair();
    flux?.getTracks().forEach((t) => t.stop());
  }

  window.addEventListener('beforeunload', () => { if (ws) ws.close(); });
  init();
})();
