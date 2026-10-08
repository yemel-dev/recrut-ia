// Enregistrement de l'entretien : le candidat (image) et les deux voix (son), envoyés au backend par morceaux
// qui sont chiffrés à mesure. Rien n'est jamais écrit en clair sur le disque pendant l'entretien.
//
// L'image passe par un canvas plutôt que par la piste vidéo du candidat : si le candidat se reconnecte, la piste change,
// mais le canvas reste le même, donc l'enregistrement continue dans un seul fichier.

const LARGEUR = 1280;
const HAUTEUR = 720;
const IMAGES_PAR_SECONDE = 25;
const DUREE_MORCEAU_MS = 5000;
// MP4 (H.264) d'abord : lisible partout et encodé par le matériel quand il existe, donc plus fluide. WebM en repli.
const TYPES_MIME = ['video/mp4;codecs=avc1.640028,opus', 'video/mp4;codecs=avc1.42E01E,opus', 'video/mp4;codecs=avc1,mp4a.40.2', 'video/mp4', 'video/webm;codecs=vp8,opus'];

const typeMime = () => (typeof MediaRecorder === 'undefined' ? undefined : TYPES_MIME.find((t) => MediaRecorder.isTypeSupported(t)));

export const enregistrementPossible = () => typeMime() !== undefined;

export function creerEnregistreur({ entretienId, onErreur }) {
  const canvas = document.createElement('canvas');
  canvas.width = LARGEUR;
  canvas.height = HAUTEUR;
  const ctx = canvas.getContext('2d');

  const audio = new AudioContext();
  const sortieAudio = audio.createMediaStreamDestination();
  const sources = { local: null, distant: null };

  let video = null; // élément <video> qui affiche le candidat
  let minuteur = null;
  let enregistreur = null;
  let file = Promise.resolve(); // envoi des morceaux, un par un et dans l'ordre
  let enErreur = false;

  function dessiner() {
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, LARGEUR, HAUTEUR);
    if (video && video.readyState >= 2 && video.videoWidth) {
      const echelle = Math.min(LARGEUR / video.videoWidth, HAUTEUR / video.videoHeight);
      const l = video.videoWidth * echelle;
      const h = video.videoHeight * echelle;
      ctx.drawImage(video, (LARGEUR - l) / 2, (HAUTEUR - h) / 2, l, h);
    } else {
      ctx.fillStyle = '#94a3b8';
      ctx.font = '32px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Candidat non connecté', LARGEUR / 2, HAUTEUR / 2);
    }
  }

  function signaler(err) {
    if (enErreur) return;
    enErreur = true;
    onErreur?.(err);
  }

  function envoyer(blob) {
    file = file.then(async () => {
      const reponse = await window.injara.entretien.envoyerMorceau(entretienId, await blob.arrayBuffer());
      if (!reponse.ok) throw new Error(reponse.donnees?.detail || "Un morceau de l'enregistrement n'a pas pu être enregistré.");
    }).catch(signaler);
  }

  return {
    /** Branche (ou remplace) une source de son : 'local' (micro du recruteur) ou 'distant' (candidat). */
    brancherAudio(role, flux) {
      sources[role]?.disconnect();
      sources[role] = null;
      if (flux?.getAudioTracks().length) {
        sources[role] = audio.createMediaStreamSource(flux);
        sources[role].connect(sortieAudio);
      }
    },
    /** Élément <video> qui montre le candidat. */
    definirVideo(element) {
      video = element;
    },
    demarrer() {
      if (enregistreur) return;
      audio.resume();
      minuteur = setInterval(dessiner, 1000 / IMAGES_PAR_SECONDE);
      const flux = new MediaStream([...canvas.captureStream(IMAGES_PAR_SECONDE).getVideoTracks(), ...sortieAudio.stream.getAudioTracks()]);
      enregistreur = new MediaRecorder(flux, { mimeType: typeMime(), videoBitsPerSecond: 2_500_000, audioBitsPerSecond: 128_000 });
      enregistreur.ondataavailable = (e) => {
        if (e.data.size > 0) envoyer(e.data);
      };
      enregistreur.onerror = (e) => signaler(e.error);
      enregistreur.start(DUREE_MORCEAU_MS);
    },
    /** Arrête et attend que le dernier morceau soit enregistré : à faire AVANT de terminer l'entretien (le backend refuse ensuite). */
    async arreter() {
      if (enregistreur && enregistreur.state !== 'inactive') {
        await new Promise((resolve) => {
          enregistreur.addEventListener('stop', resolve, { once: true });
          enregistreur.stop();
        });
      }
      enregistreur = null;
      clearInterval(minuteur);
      await file;
      sources.local?.disconnect();
      sources.distant?.disconnect();
      await audio.close().catch(() => {});
      return !enErreur;
    },
    get actif() {
      return enregistreur !== null;
    },
  };
}
