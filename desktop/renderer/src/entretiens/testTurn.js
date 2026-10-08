// Vérifie qu'un serveur TURN fonctionne vraiment : le navigateur lui demande de relayer, et s'il accepte il obtient un
// « candidat relais » (type relay). Un TURN dont l'adresse, le port ou les identifiants sont faux n'en donne aucun.

const DELAI_MS = 10000;

/** Renvoie { ok, message }. */
export function testerTurn(iceServers) {
  return new Promise((resolve) => {
    const erreurs = [];
    let relais = false;
    let termine = false;
    const pc = new RTCPeerConnection({ iceServers });

    const finir = () => {
      if (termine) return;
      termine = true;
      clearTimeout(minuteur);
      pc.close();
      if (relais) return resolve({ ok: true, message: 'Le serveur TURN répond et accepte de relayer la vidéo.' });
      const refus = erreurs.find((e) => e.code === 401 || e.code === 403);
      if (refus) return resolve({ ok: false, message: 'Le serveur TURN a refusé les identifiants (nom d\'utilisateur ou mot de passe).' });
      resolve({ ok: false, message: erreurs.length ? `Le serveur TURN n'a pas répondu correctement (${erreurs[0].texte || `erreur ${erreurs[0].code}`}). Vérifiez l'adresse et le port.` : "Aucune réponse du serveur TURN : adresse ou port incorrect, ou bloqué par ce réseau." });
    };
    const minuteur = setTimeout(finir, DELAI_MS);

    pc.onicecandidate = (e) => {
      if (!e.candidate) return finir(); // collecte terminée
      if (e.candidate.type === 'relay') {
        relais = true;
        finir();
      }
    };
    pc.onicecandidateerror = (e) => erreurs.push({ code: e.errorCode, texte: e.errorText });
    pc.createDataChannel('test');
    pc.createOffer().then((o) => pc.setLocalDescription(o)).catch(finir);
  });
}
