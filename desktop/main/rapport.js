// Rapport PDF d'un candidat (module 7).
//
// Les données viennent du backend en une seule requête (GET /candidatures/{id}/rapport). Le gabarit HTML est construit
// ici, section par section, puis imprimé en PDF par webContents.printToPDF dans une fenêtre cachée : JavaScript
// désactivé, aucune navigation, CSP stricte, toutes les valeurs échappées. Aucune bibliothèque PDF.
//
// Pour ajouter une section, écrire une fonction (donnees) => HTML et l'ajouter à SECTIONS ;
// une section qui renvoie une chaîne vide n'est pas affichée.

const fs = require('node:fs');
const path = require('node:path');
const { BrowserWindow } = require('electron');

const COULEURS = { navy: '#031e40', navy700: '#1b3b66', brand: '#2c9653', brand50: '#e1f5e8', muted: '#5b6b7f', line: '#e2e8f0', mist: '#f4f7fa' };

const esc = (valeur) =>
  String(valeur ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

const date = (iso, avecHeure = false) =>
  iso
    ? new Date(iso).toLocaleString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric', ...(avecHeure ? { hour: '2-digit', minute: '2-digit' } : {}) })
    : '';

function duree(mois) {
  if (mois === null || mois === undefined) return 'non déterminée';
  const ans = Math.floor(mois / 12);
  const reste = mois % 12;
  if (!ans) return `${reste} mois`;
  return `${ans} an${ans > 1 ? 's' : ''}${reste ? ` ${reste} mois` : ''}`;
}

/** Une durée en minutes : « 40 min », « 1 h 05 ». (`duree` ci-dessus compte en mois, pour l'expérience.) */
function minutes(n) {
  if (n === null || n === undefined) return '';
  return n < 60 ? `${Math.max(1, n)} min` : `${Math.floor(n / 60)} h ${String(n % 60).padStart(2, '0')}`;
}

const section = (titre, contenu) => `<section><h2>${esc(titre)}</h2>${contenu}</section>`;
const ligne = (libelle, valeur) => `<tr><th>${esc(libelle)}</th><td>${valeur}</td></tr>`;

// --- Sections ----------------------------------------------------------------------------------------------------

function entete(d) {
  return `
    <header>
      <div>
        <p class="surtitre">${esc(d.entreprise.nom || 'Entreprise')}${d.entreprise.ville ? ` · ${esc(d.entreprise.ville)}` : ''}</p>
        <h1>${esc(d.candidat.nom || d.candidat.email || d.candidat.fichier_cv)}</h1>
        <p class="sous-titre">Rapport de candidature · ${d.poste?.intitule ? `Poste : ${esc(d.poste.intitule)}${d.poste.reference ? ` (${esc(d.poste.reference)})` : ''}` : 'Aucun poste'}</p>
      </div>
      <div class="pastille ${d.score ? '' : 'vide'}">${d.score ? Math.round(d.score.valeur) : '—'}<span>/ 100</span></div>
    </header>
    <p class="date">Rapport établi le ${esc(date(d.genere_le, true))}</p>
    ${d.poste?.mention ? `<p class="avertissement">${esc(d.poste.mention)}</p>` : ''}`;
}

function candidat(d) {
  const c = d.candidat;
  return section(
    'Candidat',
    `<table>
      ${ligne('Nom', esc(c.nom || 'Non trouvé dans le CV'))}
      ${ligne('Email', esc(c.email || '—'))}
      ${ligne('Téléphone', esc(c.telephone || '—'))}
      ${ligne('Candidature reçue le', esc(date(c.recue_le, true)))}
      ${ligne('Poste', `${esc(d.poste?.intitule || 'Aucun')} · ${esc(d.assignation.mode_libelle || d.assignation.statut_libelle)}`)}
    </table>`,
  );
}

function score(d) {
  if (!d.score) {
    const motif = d.lecture.statut === 'illisible' ? `Le CV n'a pas pu être lu : ${esc(d.lecture.motif)}` : 'Aucun score calculé pour cette candidature.';
    return section('Score', `<p class="avertissement">${motif}</p>`);
  }
  const lignes = d.score.criteres
    .map((c) => {
      const valeur = c.score === null ? 'non calculé' : `${Math.round(c.score)} %`;
      const largeur = c.score === null ? 0 : Math.max(0, Math.min(100, c.score));
      return `<tr>
        <th>${esc(c.nom)}</th>
        <td class="barre"><span style="width:${largeur}%"></span></td>
        <td class="nombre">${valeur}</td>
        <td class="nombre">poids ${Math.round(c.poids)}${Math.round(c.poids) !== c.poids_demande ? ` <small>(demandé ${esc(c.poids_demande)})</small>` : ''}</td>
      </tr>
      <tr class="message"><td colspan="4">${esc(c.message)}</td></tr>`;
    })
    .join('');
  return section(
    `Score global : ${Math.round(d.score.valeur)} / 100`,
    `${d.score.mention_adequation ? `<p class="avertissement">${esc(d.score.mention_adequation)}</p>` : ''}
     <table class="criteres">${lignes}</table>`,
  );
}

function profil(d) {
  const etiquettes = (liste, classe) => (liste?.length ? liste.map((x) => `<span class="etiquette ${classe}">${esc(x)}</span>`).join(' ') : '<span class="discret">aucune</span>');
  const periodes = d.experience.periodes.length
    ? `<ul>${d.experience.periodes
        .map((p) => `<li>${esc(p.debut)} → ${p.en_cours ? "aujourd'hui" : esc(p.fin)} · ${esc(duree(p.mois))}${p.stage ? ' · stage' : ''}</li>`)
        .join('')}</ul>`
    : '<p class="discret">Aucune période datée trouvée.</p>';
  return section(
    'Lu dans le CV',
    `<div class="colonnes">
      <div>
        <h3>Compétences demandées</h3>
        ${d.competences
          ? `<p>Trouvées : ${etiquettes(d.competences.trouvees, 'ok')}</p><p>Manquantes : ${etiquettes(d.competences.manquantes, 'manque')}</p>`
          : '<p class="discret">Non évaluées.</p>'}
        <h3>Diplôme retenu</h3>
        <p>${esc(d.diplome.niveau || 'Aucun diplôme obtenu trouvé')}${d.diplome.ligne ? `<br><small>« ${esc(d.diplome.ligne)} »</small>` : ''}</p>
      </div>
      <div>
        <h3>Expérience retenue : ${esc(duree(d.experience.total_mois))}</h3>
        ${d.experience.stages_mois ? `<p class="discret">Stages comptés à part : ${esc(duree(d.experience.stages_mois))}</p>` : ''}
        ${periodes}
        ${d.experience.estimation ? '<p class="discret">Section « expérience » non repérée : estimation.</p>' : ''}
      </div>
    </div>`,
  );
}

function potentiel(d) {
  const p = d.potentiel;
  if (!p.calcule) return section('Potentiel', '<p class="discret">Indicateur non calculé pour cette candidature.</p>');
  return section(
    `Potentiel : ${p.niveau}`,
    `<ul class="signaux">${p.signaux
      .map((s) => `<li><span class="note">${s.evaluable ? `${s.note}/2` : 'n.é.'}</span> ${esc(s.phrase)}</li>`)
      .join('')}</ul>
     ${p.recommandation ? `<p class="recommandation">${esc(p.recommandation)}</p>` : ''}
     <p class="discret">${esc(p.mention)} « n.é. » : non évaluable, exclu du calcul.</p>`,
  );
}

function decision(d) {
  return section(
    'Décision du recruteur',
    `<table>
      ${ligne('Décision', `<strong>${esc(d.decision.libelle)}</strong>`)}
      ${d.decision.le ? ligne('Le', esc(date(d.decision.le, true))) : ''}
      ${ligne('Note', d.decision.note ? esc(d.decision.note).replace(/\n/g, '<br>') : '<span class="discret">aucune</span>')}
    </table>`,
  );
}

const note = (valeur) => (valeur === null || valeur === undefined ? '<span class="discret">non évalué</span>' : `<strong>${Math.round(valeur)}</strong> / 100`);

function entretien(d) {
  const e = d.entretien;
  if (!e) return ''; // pas d'entretien terminé : rien dans le rapport
  const r = e.regard;
  const comportement = r.calcule
    ? `<table>
        ${ligne('Face à l\'écran', `${esc(r.part_attentif)} % du temps observé`)}
        ${ligne('Regard détourné', `${esc(r.part_regard_detourne)} %`)}
        ${ligne('Visage absent', `${esc(r.part_visage_absent)} %`)}
        ${ligne('Plusieurs visages', `${esc(r.part_plusieurs_visages)} %`)}
        ${ligne('Mouvements de la tête', `${esc(r.agitation_tete_deg_par_min)} °/min`)}
        ${ligne('Observation', `${esc(minutes(Math.round(r.duree_observee_s / 60)))}${r.calibre ? '' : ' · posture de référence non établie'}`)}
      </table>`
    : '<p class="discret">Regard non analysé (le candidat n\'a pas consenti, ou aucune image n\'a pu être analysée).</p>';
  const v = e.vigilance;
  const horsRegard = e.signaux.filter((x) => !x.regard);
  const signaux = (liste) =>
    liste.length
      ? `<ul>${liste
          .map((x) => `<li>${esc(x.a || '—')} · ${esc(x.libelle)}${x.duree_s != null ? ` pendant ${esc(x.duree_s)} s` : ''}${x.raison ? ` (${esc(x.raison)})` : ''}</li>`)
          .join('')}</ul>`
      : '<p class="discret">Aucun.</p>';
  return section(
    'Entretien vidéo',
    `<table>
      ${ligne('Déroulement', `${esc(date(e.debut_le, true))}${e.duree_min !== null ? ` · ${esc(minutes(e.duree_min))}` : ''}`)}
      ${ligne('Enregistrement', e.enregistre ? 'Oui, conservé chiffré sur l\'ordinateur du recruteur' : 'Non enregistré')}
      ${ligne('Score d\'entretien', note(e.scores.entretien))}
      ${ligne('Regard (30 %)', note(e.scores.regard))}
      ${ligne('Contenu (40 %)', note(e.scores.contenu))}
      ${ligne('Confiance (30 %)', note(e.scores.confiance))}
    </table>
    ${e.resume ? `<h3>Résumé</h3><p>${esc(e.resume).replace(/\n/g, '<br>')}</p>` : ''}
    <h3>Comportement : regard et mouvements de tête</h3>
    ${comportement}
    ${e.signaux.some((x) => x.regard) ? `<h3>Événements relevés par l'analyse du regard</h3>${signaux(e.signaux.filter((x) => x.regard))}` : ''}
    <h3>Vigilance</h3>
    <table>
      ${ligne('Consignes', v.consignes_acceptees_le ? `Le candidat s'est engagé à les respecter (${esc(date(v.consignes_acceptees_le, true))})` : 'Engagement non enregistré')}
      ${ligne('Consentement', v.consentement ? 'Donné : enregistrement et analyse' : 'Non donné : ni enregistrement, ni analyse')}
    </table>
    ${v.consentement ? `<p>Signalements de la page du candidat :</p>${signaux(horsRegard)}` : ''}
    <p class="avertissement">${esc(e.mention)}</p>`,
  );
}

function mention(d) {
  return `<footer>${esc(d.mention)}</footer>`;
}

const SECTIONS = [entete, candidat, score, profil, potentiel, decision, entretien, mention];

// --- Gabarit ------------------------------------------------------------------------------------------------------

const STYLE = `
  @page { size: A4; margin: 14mm 14mm 16mm; }
  * { box-sizing: border-box; }
  body { font-family: "PT Sans", "Segoe UI", system-ui, sans-serif; color: ${COULEURS.navy}; font-size: 10pt; line-height: 1.4; margin: 0; }
  header { display: flex; justify-content: space-between; align-items: center; border-bottom: 3px solid ${COULEURS.brand}; padding-bottom: 8px; }
  h1 { font-family: "Paytone One", "Segoe UI", sans-serif; font-weight: 400; font-synthesis: none; font-size: 20pt; margin: 2px 0; }
  h2 { font-size: 11.5pt; margin: 0 0 6px; padding-bottom: 3px; border-bottom: 1px solid ${COULEURS.line}; }
  h3 { font-size: 10pt; margin: 6px 0 3px; }
  .surtitre { text-transform: uppercase; letter-spacing: .06em; font-size: 8.5pt; color: ${COULEURS.muted}; margin: 0; }
  .sous-titre, .date { color: ${COULEURS.muted}; margin: 0; }
  .date { font-size: 8.5pt; margin-top: 4px; }
  .pastille { width: 62px; height: 62px; border-radius: 50%; background: ${COULEURS.brand}; color: #fff; font-size: 19pt; font-weight: 700;
    display: flex; flex-direction: column; align-items: center; justify-content: center; line-height: 1; }
  .pastille span { font-size: 7pt; font-weight: 400; margin-top: 2px; }
  .pastille.vide { background: ${COULEURS.line}; color: ${COULEURS.muted}; }
  section { margin-top: 12px; break-inside: avoid; }
  pre { white-space: pre-wrap; font-family: inherit; font-size: 9pt; line-height: 1.5; margin: 0; }
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; font-weight: 600; width: 32%; padding: 2px 8px 2px 0; vertical-align: top; }
  td { padding: 2px 0; vertical-align: top; }
  .criteres th { width: 22%; }
  .criteres .barre { width: 40%; padding-right: 10px; vertical-align: middle; }
  .criteres .barre span { display: block; height: 6px; border-radius: 3px; background: ${COULEURS.brand}; }
  .criteres .barre { background-clip: content-box; }
  .nombre { text-align: right; white-space: nowrap; width: 12%; }
  .message td { color: ${COULEURS.muted}; font-size: 8.5pt; padding-bottom: 5px; }
  .colonnes { display: flex; gap: 18px; } .colonnes > div { flex: 1; }
  .etiquette { display: inline-block; border-radius: 9px; padding: 0 7px; margin: 1px 0; font-size: 8.5pt; }
  .etiquette.ok { background: ${COULEURS.brand50}; color: #1e6438; }
  .etiquette.manque { background: ${COULEURS.mist}; color: ${COULEURS.navy700}; border: 1px solid ${COULEURS.line}; }
  ul { margin: 2px 0; padding-left: 16px; }
  .signaux { list-style: none; padding: 0; } .signaux li { margin: 3px 0; }
  .note { display: inline-block; min-width: 30px; font-weight: 700; color: ${COULEURS.brand}; }
  .recommandation { background: ${COULEURS.brand50}; color: #1e6438; padding: 5px 8px; border-radius: 6px; }
  .avertissement { background: ${COULEURS.mist}; border-left: 3px solid ${COULEURS.navy700}; padding: 5px 8px; margin: 6px 0; }
  .discret, small { color: ${COULEURS.muted}; }
  footer { margin-top: 16px; padding-top: 6px; border-top: 1px solid ${COULEURS.line}; font-size: 8.5pt; color: ${COULEURS.muted}; font-style: italic; }
`;

function gabaritRapport(donnees) {
  const corps = SECTIONS.map((s) => s(donnees)).filter(Boolean).join('\n');
  return `<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; font-src data:">
<title>Rapport ${esc(donnees.candidat.nom || '')}</title>
<style>${polices()}\n${STYLE}</style></head>
<body>${corps}</body></html>`;
}

// Polices de l'application (PT Sans, Paytone One), embarquées en data: : le rapport ne charge rien depuis le disque
// ni le réseau. Lues une fois, au premier rapport.
let policesCss = null;
function polices() {
  if (policesCss === null) {
    const face = (famille, fichier, graisse) => {
      const donnees = fs.readFileSync(path.join(__dirname, 'polices', fichier)).toString('base64');
      return `@font-face { font-family: '${famille}'; src: url(data:font/woff2;base64,${donnees}) format('woff2'); font-weight: ${graisse}; font-display: block; }`;
    };
    policesCss = [face('PT Sans', 'pt-sans-400.woff2', 400), face('PT Sans', 'pt-sans-700.woff2', 700), face('Paytone One', 'paytone-one.woff2', 400)].join('\n');
  }
  return policesCss;
}

/** Imprime le gabarit en PDF (A4) dans une fenêtre cachée, sans JavaScript ni navigation. */
async function genererPdf(html) {
  const fenetre = new BrowserWindow({
    show: false,
    webPreferences: { javascript: false, sandbox: true, contextIsolation: true, nodeIntegration: false, webSecurity: true },
  });
  fenetre.webContents.on('will-navigate', (event) => event.preventDefault());
  fenetre.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  try {
    await fenetre.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    return await fenetre.webContents.printToPDF({ pageSize: 'A4', printBackground: true, preferCSSPageSize: true });
  } finally {
    fenetre.destroy();
  }
}

/** Nom de fichier proposé : « Rapport - Awa Ndong - Développeur Python.pdf », sans caractères interdits. */
function nomDeFichier(donnees) {
  const morceaux = ['Rapport', donnees.candidat.nom || donnees.candidat.email || 'candidat', donnees.poste?.intitule].filter(Boolean);
  return `${morceaux.join(' - ').replace(/[<>:"/\\|?*\u0000-\u001f]/g, '_').slice(0, 150)}.pdf`;
}

module.exports = { gabaritRapport, genererPdf, nomDeFichier, SECTIONS };
