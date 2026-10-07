// Analyse du regard : quelques images par seconde de la vidéo du candidat, réduites, envoyées au backend local.
// Rien ne sort de l'ordinateur et rien n'est conservé : le backend n'enregistre que les événements et le bilan final.
//
// Une seule image est en vol à la fois : si le backend est lent, on saute des images plutôt que d'accumuler du retard.

const IMAGES_PAR_SECONDE = 4;
const LARGEUR = 480;
const ECHECS_MAX = 5;

export function creerAnalyseurRegard({ entretienId, onResultat, onErreur }) {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  let video = null;
  let minuteur = null;
  let enVol = false;
  let echecs = 0;

  async function echantillonner() {
    if (enVol || !video || video.readyState < 2 || !video.videoWidth) return;
    enVol = true;
    try {
      canvas.width = LARGEUR;
      canvas.height = Math.round((LARGEUR * video.videoHeight) / video.videoWidth);
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.7));
      if (!blob) return;
      const reponse = await window.injara.entretien.envoyerImageRegard(entretienId, await blob.arrayBuffer());
      if (!minuteur) return; // arrêté pendant l'envoi
      if (reponse.ok) {
        echecs = 0;
        onResultat(reponse.donnees);
      } else if (reponse.statut === 503 || reponse.statut === 409) {
        arreter(); // modèle absent, ou entretien clos / sans consentement : inutile d'insister
        onErreur(reponse.donnees?.detail || "L'analyse du regard n'est pas disponible.");
      } else if (++echecs >= ECHECS_MAX) {
        arreter();
        onErreur("L'analyse du regard s'est interrompue. L'entretien peut continuer.");
      }
    } catch {
      if (minuteur && ++echecs >= ECHECS_MAX) {
        arreter();
        onErreur("L'analyse du regard s'est interrompue. L'entretien peut continuer.");
      }
    } finally {
      enVol = false;
    }
  }

  function arreter() {
    clearInterval(minuteur);
    minuteur = null;
  }

  return {
    /** L'élément <video> qui affiche le candidat. */
    definirVideo(element) {
      video = element;
    },
    demarrer() {
      if (!minuteur) minuteur = setInterval(echantillonner, 1000 / IMAGES_PAR_SECONDE);
    },
    arreter,
  };
}
