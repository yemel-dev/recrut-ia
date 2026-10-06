// Rapport PDF d'un candidat (module 7).
//
// Les données viennent du backend en une seule requête (GET /candidatures/{id}/rapport). Le gabarit HTML est construit
// ici, section par section, puis imprimé en PDF par webContents.printToPDF dans une fenêtre cachée : JavaScript
// désactivé, aucune navigation, CSP stricte, toutes les valeurs échappées. Aucune bibliothèque PDF.
//
// Pour ajouter une section (ex. : « Entretien »), écrire une fonction (donnees) => HTML et l'ajouter à SECTIONS ;
// une section qui renvoie une chaîne vide n'est pas affichée.

const { BrowserWindow } = require('electron');

const COULEURS = { navy: '#031e40', navy700: '#1b3b66', brand: '#00a656', brand50: '#e8faf0', muted: '#5b6b7f', line: '#e2e8f0', mist: '#f4f7fa' };

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

function entretien(d) {
  if (!d.entretien) return ''; // module entretien à venir : rien tant qu'il n'y a pas d'entretien
  return section('Entretien', `<p>${esc(d.entretien.resume || '')}</p>`);
}

function mention(d) {
  return `<footer>${esc(d.mention)}</footer>`;
}

const SECTIONS = [entete, candidat, score, profil, potentiel, decision, entretien, mention];

// --- Gabarit ------------------------------------------------------------------------------------------------------

const STYLE = `
  @page { size: A4; margin: 14mm 14mm 16mm; }
  * { box-sizing: border-box; }
  body { font-family: "Segoe UI", system-ui, "Noto Sans", sans-serif; color: ${COULEURS.navy}; font-size: 10pt; line-height: 1.4; margin: 0; }
  header { display: flex; justify-content: space-between; align-items: center; border-bottom: 3px solid ${COULEURS.brand}; padding-bottom: 8px; }
  h1 { font-size: 20pt; margin: 2px 0; }
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
  .etiquette.ok { background: ${COULEURS.brand50}; color: #007a3f; }
  .etiquette.manque { background: ${COULEURS.mist}; color: ${COULEURS.navy700}; border: 1px solid ${COULEURS.line}; }
  ul { margin: 2px 0; padding-left: 16px; }
  .signaux { list-style: none; padding: 0; } .signaux li { margin: 3px 0; }
  .note { display: inline-block; min-width: 30px; font-weight: 700; color: ${COULEURS.brand}; }
  .recommandation { background: ${COULEURS.brand50}; color: #007a3f; padding: 5px 8px; border-radius: 6px; }
  .avertissement { background: ${COULEURS.mist}; border-left: 3px solid ${COULEURS.navy700}; padding: 5px 8px; margin: 6px 0; }
  .discret, small { color: ${COULEURS.muted}; }
  footer { margin-top: 16px; padding-top: 6px; border-top: 1px solid ${COULEURS.line}; font-size: 8.5pt; color: ${COULEURS.muted}; font-style: italic; }
`;

function gabaritRapport(donnees) {
  const corps = SECTIONS.map((s) => s(donnees)).filter(Boolean).join('\n');
  return `<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>Rapport ${esc(donnees.candidat.nom || '')}</title>
<style>${STYLE}</style></head>
<body>${corps}</body></html>`;
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
