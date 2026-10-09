import { ArrowLeft, Check, ExternalLink, FileDown, Gauge, Mail, Phone, RefreshCw, RotateCcw, ScanText } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { api } from '../api.js';
import { useAgent } from '../agent/ContexteAgent.jsx';
import {
  BadgeDecision,
  BadgePotentiel,
  BadgeStatutCandidature,
  DECISIONS,
  DetailPotentiel,
  DetailScore,
  MENTION_POTENTIEL,
  MODES_ASSIGNATION,
  PastilleScore,
  formaterExperience,
} from '../candidatures/elements.jsx';
import { Alerte, Badge, Bouton, CHAMP_SAISIE, Carte, Champ, ZoneTexte } from '../components/ui.jsx';
import { STATUTS } from '../constantes.js';
import CarteEntretien from '../entretiens/CarteEntretien.jsx';
import { formaterDateHeure } from '../format.js';

export default function FicheCandidature() {
  const { id } = useParams();
  const retour = useLocation().state?.retour; // venu du classement d'un poste : on y revient
  const { notifier } = useAgent();
  const [fiche, setFiche] = useState(null);
  const [postes, setPostes] = useState([]);
  const [erreur, setErreur] = useState('');
  const [envoi, setEnvoi] = useState(false);

  const charger = useCallback(() => {
    api.get(`/candidatures/${id}`).then(setFiche, (err) => setErreur(err.message));
  }, [id]);

  useEffect(() => {
    charger();
    api.get('/postes').then(setPostes, () => {});
  }, [charger]);

  // En cours de lecture : on recharge jusqu'à la fin du traitement.
  const enTraitement = fiche && (fiche.statut_lecture === 'en_attente' || fiche.statut_classement === 'a_traiter') && fiche.statut_lecture !== 'illisible';
  useEffect(() => {
    if (!enTraitement) return undefined;
    const minuteur = setInterval(charger, 3000);
    return () => clearInterval(minuteur);
  }, [enTraitement, charger]);

  const action = async (requete, message) => {
    setEnvoi(true);
    setErreur('');
    try {
      setFiche(await requete());
      if (message) notifier(message, 'succes');
    } catch (err) {
      setErreur(err.message);
    } finally {
      setEnvoi(false);
    }
  };

  const changerPoste = (valeur) =>
    action(
      () => api.put(`/candidatures/${id}/poste`, { poste_id: valeur === '' ? null : Number(valeur) }),
      'Poste enregistré. Ce choix ne sera pas modifié par le classement automatique.',
    );

  const ouvrirCV = async () => {
    const message = await window.injara.fichiers.ouvrirCV(fiche.id);
    if (message) setErreur(message);
  };

  const [exportEnCours, setExportEnCours] = useState(false);
  const exporterRapport = async () => {
    setErreur('');
    setExportEnCours(true);
    try {
      const resultat = await window.injara.fichiers.exporterRapport(fiche.id);
      if (resultat.ok) notifier(`Rapport enregistré : ${resultat.chemin}`, 'succes');
      else if (!resultat.annule) setErreur(resultat.message);
    } catch (err) {
      setErreur(err.message);
    } finally {
      setExportEnCours(false);
    }
  };

  if (!fiche) {
    return erreur ? <Alerte>{erreur}</Alerte> : <SqueletteFiche />;
  }

  const scorePoste = fiche.scores.find((s) => s.poste_id === fiche.poste_id);
  const autres = fiche.scores.filter((s) => s.poste_id !== fiche.poste_id);
  const illisible = fiche.statut_lecture === 'illisible';

  return (
    <>
      <Link
        to={retour?.chemin || '/candidatures'}
        className="geste-hote mb-5 inline-flex items-center gap-1.5 text-sm font-medium text-doux transition-colors hover:text-fort"
      >
        <ArrowLeft className="size-4" aria-hidden data-geste="reculer" /> {retour?.libelle || 'Toutes les candidatures'}
      </Link>

      {/* En-tête : score, identité, actions */}
      <header className="mb-6 flex items-center gap-6">
        <PastilleScore score={fiche.score} taille="grande" anime />
        <div className="min-w-0 flex-1">
          <h1 className="titre-ecran truncate">{fiche.nom || fiche.email || fiche.nom_fichier_cv}</h1>
          <p className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-base text-doux">
            {fiche.email && <span className="inline-flex items-center gap-1.5"><Mail className="size-3.5" aria-hidden /> {fiche.email}</span>}
            {fiche.telephone && <span className="inline-flex items-center gap-1.5 tabular-nums"><Phone className="size-3.5" aria-hidden /> {fiche.telephone}</span>}
            <span className="tabular-nums">Reçue le {formaterDateHeure(fiche.recue_le)}</span>
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <BadgeStatutCandidature candidature={fiche} />
            <BadgeDecision decision={fiche.decision.etat} />
            {scorePoste?.potentiel && <BadgePotentiel niveau={scorePoste.potentiel.niveau} />}
            {enTraitement && (
              <span className="inline-flex items-center gap-2 text-sm" role="status">
                <span className="ia-pulsation size-2 rounded-full bg-accent shadow-[0_0_8px_var(--halo)]" aria-hidden />
                <span className="ia-reflet font-medium">L'IA lit ce CV…</span>
              </span>
            )}
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap justify-end gap-2 self-start">
          <Bouton variante="secondaire" icone={ExternalLink} geste="decoller" onClick={ouvrirCV}>Ouvrir le CV</Bouton>
          <Bouton icone={FileDown} geste="descendre" chargement={exportEnCours} onClick={exporterRapport}>Exporter le rapport</Bouton>
        </div>
      </header>

      {erreur && <Alerte className="mb-4">{erreur}</Alerte>}

      {illisible && (
        <Alerte
          className="mb-6"
          titre="Ce CV n'a pas pu être lu automatiquement : il n'est pas noté."
          action={
            <Bouton variante="secondaire" taille="sm" icone={RefreshCw} geste="tourner" chargement={envoi} onClick={() => action(() => api.post(`/candidatures/${id}/relire`), null)}>
              Relire le fichier
            </Bouton>
          }
        >
          {fiche.motif_lecture}
        </Alerte>
      )}

      {!illisible && fiche.motif_lecture && (
        <p className="mb-6 flex items-start gap-2 rounded-md border border-trait bg-survol px-3.5 py-2.5 text-sm text-doux">
          <ScanText className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>{fiche.motif_lecture}</span>
        </p>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex min-w-0 flex-col gap-6">
          <Carte className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="titre-section">Poste</h2>
              {fiche.mode_assignation && fiche.mode_assignation !== 'manuel' && <span className="text-sm text-doux">{MODES_ASSIGNATION[fiche.mode_assignation]}</span>}
            </div>
            {fiche.motif_classement && <p className="text-base text-doux">{fiche.motif_classement}</p>}
            <div className="flex flex-wrap items-center gap-3">
              <select
                value={fiche.poste_id ?? ''}
                disabled={envoi}
                onChange={(e) => changerPoste(e.target.value)}
                aria-label="Poste de la candidature"
                className={`${CHAMP_SAISIE} h-9 w-auto min-w-72 pr-8`}
              >
                <option value="">Aucun poste</option>
                {postes.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.intitule}{p.statut !== 'actif' ? ` (${STATUTS[p.statut].toLowerCase()})` : ''}
                  </option>
                ))}
              </select>
              {fiche.mode_assignation === 'manuel' && (
                <Bouton
                  variante="discret"
                  icone={RotateCcw}
                  geste="reculer"
                  chargement={envoi}
                  onClick={() => action(() => api.post(`/candidatures/${id}/automatique`), 'La candidature est reclassée automatiquement.')}
                >
                  Revenir au classement automatique
                </Bouton>
              )}
            </div>
          </Carte>

          {scorePoste && (
            <CarteIA titre={<>Score pour « {scorePoste.poste_intitule} »</>} droite={<span className="chiffre text-3xl text-fort">{Math.round(scorePoste.score)}<span className="font-sans text-sm font-normal tracking-normal text-doux"> / 100</span></span>}>
              <DetailScore detail={{ ...scorePoste.detail, adequation_ignoree: scorePoste.adequation_ignoree }} />
              <p className="mt-4 text-sm text-doux">Le score est un indicateur d'aide à la décision : il ne remplace pas la lecture du CV.</p>
            </CarteIA>
          )}

          {scorePoste?.potentiel && (
            <CarteIA titre="Potentiel" droite={<BadgePotentiel niveau={scorePoste.potentiel.niveau} />}>
              <DetailPotentiel potentiel={scorePoste.potentiel} />
              <p className="mt-4 text-sm text-doux">
                {MENTION_POTENTIEL} Il ne modifie ni le score ni le classement.
                {scorePoste.potentiel.niveau === 'Non évaluable' && ' Trop peu de signaux évaluables dans ce CV (au moins trois sont nécessaires).'}
              </p>
            </CarteIA>
          )}

          {autres.length > 0 && (
            <Carte sansMarge>
              <h2 className="titre-section px-5 pt-5 pb-2">Autres postes</h2>
              <ul>
                {autres.map((s) => (
                  <li key={s.poste_id} className="flex items-center justify-between gap-4 border-t border-trait px-5 py-2.5 text-base">
                    <span className="min-w-0 truncate text-fort">
                      {s.poste_intitule}
                      {s.poste_statut !== 'actif' && <span className="text-doux"> ({STATUTS[s.poste_statut].toLowerCase()})</span>}
                    </span>
                    <span className="flex shrink-0 items-center gap-4 text-sm text-doux">
                      <span title="Correspondance du CV avec le métier (compétences et adéquation)" className="tabular-nums">pertinence {Math.round(s.pertinence)}</span>
                      <PastilleScore score={s.score} taille="petite" />
                    </span>
                  </li>
                ))}
              </ul>
            </Carte>
          )}
        </div>

        <div className="flex flex-col gap-6">
          <CarteDecision
            key={fiche.id}
            decision={fiche.decision}
            envoi={envoi}
            onEnregistrer={(decision, note) =>
              action(() => api.put(`/candidatures/${id}/decision`, { decision, note }), 'Décision enregistrée. Le score et le classement ne changent pas.')
            }
          />
          <CarteEntretien candidatureId={fiche.id} decision={fiche.decision} />
          <Carte className="flex flex-col gap-3 text-base">
            <h2 className="titre-section">Lu dans le CV</h2>
            {fiche.statut_lecture !== 'lue' ? (
              <p className="text-doux">{illisible ? 'Rien : le fichier est illisible.' : 'Lecture en cours…'}</p>
            ) : (
              <>
                <dl className="flex flex-col gap-2">
                  <Ligne libelle="Expérience" valeur={formaterExperience(fiche.experience_mois)} />
                  <Ligne libelle="Stages (à part)" valeur={formaterExperience(fiche.stages_mois)} />
                  <Ligne libelle="Diplôme retenu" valeur={fiche.diplome_niveau || 'Non trouvé'} />
                </dl>
                {fiche.extraction.diplome?.ligne && <p className="text-sm text-doux">« {fiche.extraction.diplome.ligne} »</p>}
                {fiche.extraction.diplome?.ignores?.map((d) => (
                  <p key={d.ligne} className="text-sm text-tenu">Non retenu ({d.raison}) : « {d.ligne} »</p>
                ))}
                {fiche.extraction.periodes.length > 0 && (
                  <div className="border-t border-trait pt-3">
                    <p className="etiquette mb-2">Périodes d'expérience retenues</p>
                    <ol className="relative flex flex-col gap-2 border-l border-trait-fort pl-4 text-sm">
                      {fiche.extraction.periodes.map((p, i) => (
                        <li key={i} className="relative text-texte tabular-nums">
                          <span className={`absolute top-1.5 -left-[21px] size-2 rounded-full ring-2 ring-[var(--surface)] ${p.stage ? 'bg-info' : 'bg-accent'}`} aria-hidden />
                          {p.debut} → {p.en_cours ? "aujourd'hui" : p.fin} <span className="text-doux">· {formaterExperience(p.mois)}</span>
                          {p.stage && <Badge ton="info" className="ml-2">stage</Badge>}
                        </li>
                      ))}
                    </ol>
                  </div>
                )}
                {!fiche.extraction.section_experience_trouvee && (
                  <p className="text-sm text-alerte">Section « expérience » non repérée : l'expérience est une estimation.</p>
                )}
              </>
            )}
          </Carte>
          <Carte className="flex flex-col gap-2.5 text-base">
            <h2 className="titre-section">Le mail</h2>
            <dl className="flex flex-col gap-2">
              <Ligne libelle="Fichier" valeur={fiche.nom_fichier_cv} />
              {fiche.objet && <Ligne libelle="Objet" valeur={fiche.objet} />}
            </dl>
            {fiche.corps && <p className="max-h-40 overflow-y-auto rounded-md border border-trait bg-enfonce p-3 text-sm whitespace-pre-line text-texte">{fiche.corps}</p>}
            {fiche.pieces_jointes.length > 0 && (
              <p className="text-sm text-doux">Autres pièces jointes : {fiche.pieces_jointes.map((p) => p.nom).join(', ')}</p>
            )}
          </Carte>
        </div>
      </div>
    </>
  );
}

/** Bloc produit par l'analyse automatique : jauge et liseré vert, pour le distinguer de ce que saisit le recruteur. */
function CarteIA({ titre, droite, children }) {
  return (
    <Carte className="relative overflow-hidden border-accent-trait/60 before:absolute before:inset-y-0 before:left-0 before:w-[3px] before:bg-gradient-to-b before:from-accent before:to-transparent">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
        <h2 className="titre-section flex items-center gap-2">
          <Gauge className="size-4 text-accent-texte" aria-label="Analyse automatique" />
          {titre}
        </h2>
        {droite}
      </div>
      {children}
    </Carte>
  );
}

function CarteDecision({ decision, envoi, onEnregistrer }) {
  const [etat, setEtat] = useState(decision.etat);
  const [note, setNote] = useState(decision.note || '');
  const [confirmee, setConfirmee] = useState(false);
  useEffect(() => {
    setEtat(decision.etat);
    setNote(decision.note || '');
  }, [decision]);
  // Retour visuel juste après l'enregistrement (la décision vient d'arriver du serveur).
  const premiere = useRef(true);
  useEffect(() => {
    if (premiere.current) {
      premiere.current = false;
      return undefined;
    }
    setConfirmee(true);
    const minuteur = setTimeout(() => setConfirmee(false), 1800);
    return () => clearTimeout(minuteur);
  }, [decision.le]);
  const modifiee = etat !== decision.etat || note.trim() !== (decision.note || '');

  return (
    <Carte className="flex flex-col gap-4 text-base">
      <div className="flex items-center justify-between gap-3">
        <h2 className="titre-section">Décision</h2>
        <BadgeDecision decision={decision.etat} />
      </div>
      <div className="grid grid-cols-2 gap-1.5 rounded-md border border-trait bg-enfonce p-1" role="radiogroup" aria-label="Décision du recruteur">
        {Object.entries(DECISIONS).map(([cle, libelle]) => (
          <button
            key={cle}
            type="button"
            role="radio"
            aria-checked={etat === cle}
            onClick={() => setEtat(cle)}
            className={`appui h-8 rounded-[5px] text-sm font-medium ${
              etat === cle ? 'bg-surface-2 text-fort shadow-[0_1px_2px_rgb(0_0_0/0.2)] ring-1 ring-accent-trait' : 'text-doux hover:bg-survol hover:text-fort'
            }`}
          >
            {libelle}
          </button>
        ))}
      </div>
      <Champ label="Note (facultative)">
        {(a) => (
          <ZoneTexte {...a} rows={3} maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Pour vous : impressions, prochaine étape…" />
        )}
      </Champ>
      <Bouton disabled={!modifiee && !confirmee} chargement={envoi} onClick={() => onEnregistrer(etat, note)} icone={confirmee && !modifiee ? Check : undefined}>
        {confirmee && !modifiee ? 'Décision enregistrée' : 'Enregistrer la décision'}
      </Bouton>
      <p className="text-sm text-doux">
        {decision.le ? `Décision du ${formaterDateHeure(decision.le)}. ` : ''}
        Modifiable à tout moment ; elle ne change ni le score ni le classement.
      </p>
    </Carte>
  );
}

function Ligne({ libelle, valeur }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-doux">{libelle}</dt>
      <dd className="min-w-0 truncate text-right font-medium text-fort" title={valeur}>{valeur}</dd>
    </div>
  );
}

function SqueletteFiche() {
  return (
    <div aria-busy="true" aria-label="Chargement de la fiche">
      <div className="squelette mb-6 h-4 w-40" />
      <div className="mb-6 flex items-center gap-6">
        <div className="squelette size-[88px] rounded-full" />
        <div className="flex-1"><div className="squelette mb-3 h-8 w-72" /><div className="squelette h-4 w-96" /></div>
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex flex-col gap-6"><div className="squelette h-32 rounded-lg" /><div className="squelette h-72 rounded-lg" /></div>
        <div className="flex flex-col gap-6"><div className="squelette h-64 rounded-lg" /><div className="squelette h-40 rounded-lg" /></div>
      </div>
    </div>
  );
}
