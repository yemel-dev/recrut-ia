// Sous-titres en différé : le son de chaque participant est découpé en extraits de quelques secondes, décodés en
// mono 16 kHz (le format de Whisper) et envoyés au backend local, qui renvoie le texte. Rien ne sort de l'ordinateur
// et le son n'est pas conservé.
//
// Une piste par personne (micro du recruteur, voix du candidat) : on sait qui parle sans analyse de voix.
// Les extraits sont traités un par un, dans l'ordre : si la transcription est plus lente que la parole, le retard
// grandit (indiqué par `enAttente`) mais rien n'est perdu, sauf au-delà de FILE_MAX extraits.

const FREQUENCE = 16000;
const DUREE_EXTRAIT = 10; // secondes
const SEUIL_SILENCE = 0.005; // niveau efficace sous lequel l'extrait n'est pas envoyé
const DUREE_MIN = 1; // secondes : le reste de fin d'entretien en dessous n'est pas envoyé
const FILE_MAX = 30;

export function creerSousTitreur({ entretienId, onSegments, onEtat, onErreur }) {
  const t0 = Date.now();
  const pistes = {
    recruteur: { tampon: [], echantillons: 0, source: null, processeur: null, contexte: null },
    candidat: { tampon: [], echantillons: 0, source: null, processeur: null, contexte: null },
  };
  let file = Promise.resolve();
  let enAttente = 0;
  let arrete = false;
  let erreurSignalee = false;

  const secondes = () => (Date.now() - t0) / 1000;

  function signaler(message) {
    if (erreurSignalee) return;
    erreurSignalee = true;
    onErreur(message);
  }

  function envoyer(locuteur, pcm, debut) {
    let somme = 0;
    for (let i = 0; i < pcm.length; i++) somme += pcm[i] * pcm[i];
    if (Math.sqrt(somme / pcm.length) < SEUIL_SILENCE) return; // silence : rien à transcrire
    if (enAttente >= FILE_MAX) {
      signaler('Les sous-titres ont pris trop de retard : certains passages ne seront pas transcrits.');
      return;
    }
    enAttente += 1;
    onEtat?.({ enAttente });
    file = file
      .then(() => window.injara.entretien.envoyerSousTitres(entretienId, locuteur, debut, pcm.buffer))
      .then((reponse) => {
        if (reponse.ok) onSegments(reponse.donnees.segments);
        else if (reponse.statut === 503) signaler(reponse.donnees?.detail || 'Les sous-titres ne sont pas disponibles.');
        else if (reponse.statut !== 409) signaler('Un extrait n\'a pas pu être transcrit.');
      })
      .catch(() => signaler('Un extrait n\'a pas pu être transcrit.'))
      .finally(() => {
        enAttente -= 1;
        onEtat?.({ enAttente });
      });
  }

  function vider(locuteur, forcer) {
    const piste = pistes[locuteur];
    const minimum = forcer ? DUREE_MIN * FREQUENCE : DUREE_EXTRAIT * FREQUENCE;
    if (piste.echantillons < minimum) return;
    const pcm = new Float32Array(piste.echantillons);
    let position = 0;
    for (const bloc of piste.tampon) {
      pcm.set(bloc, position);
      position += bloc.length;
    }
    piste.tampon = [];
    piste.echantillons = 0;
    envoyer(locuteur, pcm, Math.max(0, secondes() - pcm.length / FREQUENCE));
  }

  function debrancher(locuteur) {
    const piste = pistes[locuteur];
    piste.processeur?.disconnect();
    piste.source?.disconnect();
    piste.contexte?.close();
    piste.processeur = piste.source = piste.contexte = null;
  }

  return {
    /** Branche (ou rebranche, si le candidat se reconnecte) le flux d'un participant : 'recruteur' ou 'candidat'. */
    brancher(locuteur, flux) {
      if (arrete) return;
      vider(locuteur, true);
      debrancher(locuteur);
      if (!flux || flux.getAudioTracks().length === 0) return;
      const piste = pistes[locuteur];
      const contexte = new AudioContext({ sampleRate: FREQUENCE }); // le navigateur rééchantillonne
      const source = contexte.createMediaStreamSource(flux);
      const processeur = contexte.createScriptProcessor(4096, 1, 1);
      processeur.onaudioprocess = (e) => {
        if (arrete) return;
        const bloc = new Float32Array(e.inputBuffer.getChannelData(0)); // copie : le navigateur réutilise son tampon
        piste.tampon.push(bloc);
        piste.echantillons += bloc.length;
        vider(locuteur, false);
      };
      const muet = contexte.createGain(); // le processeur ne tourne que branché à la sortie ; le gain nul évite tout écho
      muet.gain.value = 0;
      source.connect(processeur);
      processeur.connect(muet);
      muet.connect(contexte.destination);
      Object.assign(piste, { contexte, source, processeur });
    },
    /** Envoie ce qui reste et attend la fin des transcriptions : à appeler avant de terminer l'entretien. */
    async arreter() {
      if (arrete) return file;
      for (const locuteur of Object.keys(pistes)) vider(locuteur, true);
      arrete = true;
      for (const locuteur of Object.keys(pistes)) debrancher(locuteur);
      return file;
    },
  };
}
