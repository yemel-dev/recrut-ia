import { ArrowLeft, ExternalLink, FileDown, FileWarning, Mail, Phone, RefreshCw, RotateCcw, ScanText } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
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
import { Alerte, Bouton, Carte, Champ, Chargement, ZoneTexte } from '../components/ui.jsx';
import { STATUTS } from '../constantes.js';
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
    return erreur ? <Alerte>{erreur}</Alerte> : <Chargement />;
  }

  const scorePoste = fiche.scores.find((s) => s.poste_id === fiche.poste_id);
  const autres = fiche.scores.filter((s) => s.poste_id !== fiche.poste_id);
  const illisible = fiche.statut_lecture === 'illisible';

  return (
    <>
      <Link to={retour?.chemin || '/candidatures'} className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-muted hover:text-navy-900">
        <ArrowLeft className="size-4" aria-hidden /> {retour?.libelle || 'Toutes les candidatures'}
      </Link>

      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <PastilleScore score={fiche.score} taille="grande" />
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-navy-900">{fiche.nom || fiche.email || fiche.nom_fichier_cv}</h1>
            <p className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted">
              {fiche.email && <span className="inline-flex items-center gap-1.5"><Mail className="size-3.5" aria-hidden /> {fiche.email}</span>}
              {fiche.telephone && <span className="inline-flex items-center gap-1.5"><Phone className="size-3.5" aria-hidden /> {fiche.telephone}</span>}
              <span>Reçue le {formaterDateHeure(fiche.recue_le)}</span>
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Bouton variante="secondaire" icone={ExternalLink} onClick={ouvrirCV}>Ouvrir le CV</Bouton>
          <Bouton icone={FileDown} chargement={exportEnCours} onClick={exporterRapport}>Exporter le rapport</Bouton>
        </div>
      </div>

      {erreur && <div className="mb-4"><Alerte>{erreur}</Alerte></div>}

      {illisible && (
        <Carte className="mb-6 flex flex-wrap items-start justify-between gap-4 border-danger/20 bg-danger-50">
          <div className="flex gap-3 text-sm text-danger">
            <FileWarning className="mt-0.5 size-5 shrink-0" aria-hidden />
            <div>
              <p className="font-semibold">Ce CV n'a pas pu être lu automatiquement : il n'est pas noté.</p>
              <p className="mt-1">{fiche.motif_lecture}</p>
            </div>
          </div>
          <Bouton variante="secondaire" icone={RefreshCw} chargement={envoi} onClick={() => action(() => api.post(`/candidatures/${id}/relire`), null)}>
            Relire le fichier
          </Bouton>
        </Carte>
      )}

      {!illisible && fiche.motif_lecture && (
        <p className="mb-6 flex items-start gap-2 rounded-lg border border-line bg-white px-4 py-3 text-sm text-muted">
          <ScanText className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>{fiche.motif_lecture}</span>
        </p>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="flex flex-col gap-6 lg:col-span-2">
          <Carte className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="font-semibold text-navy-900">Poste</h2>
              <BadgeStatutCandidature candidature={fiche} />
            </div>
            {fiche.motif_classement && <p className="text-sm text-muted">{fiche.motif_classement}</p>}
            <div className="flex flex-wrap items-center gap-3">
              <select
                value={fiche.poste_id ?? ''}
                disabled={envoi}
                onChange={(e) => changerPoste(e.target.value)}
                aria-label="Poste de la candidature"
                className="min-w-64 rounded-lg border border-line bg-white px-3 py-2 text-sm"
              >
                <option value="">Aucun poste</option>
                {postes.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.intitule}{p.statut !== 'actif' ? ` (${STATUTS[p.statut].toLowerCase()})` : ''}
                  </option>
                ))}
              </select>
              {fiche.mode_assignation === 'manuel' ? (
                <Bouton
                  variante="discret"
                  icone={RotateCcw}
                  chargement={envoi}
                  onClick={() => action(() => api.post(`/candidatures/${id}/automatique`), 'La candidature est reclassée automatiquement.')}
                >
                  Revenir au classement automatique
                </Bouton>
              ) : (
                fiche.mode_assignation && <span className="text-xs text-muted">{MODES_ASSIGNATION[fiche.mode_assignation]}</span>
              )}
            </div>
          </Carte>

          {scorePoste && (
            <Carte>
              <div className="mb-4 flex items-baseline justify-between gap-4">
                <h2 className="font-semibold text-navy-900">Score pour « {scorePoste.poste_intitule} »</h2>
                <span className="text-2xl font-bold text-navy-900">{Math.round(scorePoste.score)}<span className="text-sm font-normal text-muted"> / 100</span></span>
              </div>
              <DetailScore detail={{ ...scorePoste.detail, adequation_ignoree: scorePoste.adequation_ignoree }} />
              <p className="mt-4 text-xs text-muted">Le score est un indicateur d'aide à la décision : il ne remplace pas la lecture du CV.</p>
            </Carte>
          )}

          {scorePoste?.potentiel && (
            <Carte>
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <h2 className="font-semibold text-navy-900">Potentiel</h2>
                <BadgePotentiel niveau={scorePoste.potentiel.niveau} />
              </div>
              <DetailPotentiel potentiel={scorePoste.potentiel} />
              <p className="mt-4 text-xs text-muted">
                {MENTION_POTENTIEL} Il ne modifie ni le score ni le classement.
                {scorePoste.potentiel.niveau === 'Non évaluable' && ' Trop peu de signaux évaluables dans ce CV (au moins trois sont nécessaires).'}
              </p>
            </Carte>
          )}

          {autres.length > 0 && (
            <Carte>
              <h2 className="mb-3 font-semibold text-navy-900">Autres postes</h2>
              <ul className="flex flex-col divide-y divide-line">
                {autres.map((s) => (
                  <li key={s.poste_id} className="flex items-center justify-between gap-4 py-2 text-sm">
                    <span className="text-navy-900">
                      {s.poste_intitule}
                      {s.poste_statut !== 'actif' && <span className="text-muted"> ({STATUTS[s.poste_statut].toLowerCase()})</span>}
                    </span>
                    <span className="flex items-center gap-4 text-muted">
                      <span title="Correspondance du CV avec le métier (compétences et adéquation)">pertinence {Math.round(s.pertinence)}</span>
                      <PastilleScore score={s.score} />
                    </span>
                  </li>
                ))}
              </ul>
            </Carte>
          )}
        </div>

        <div className="flex flex-col gap-6">
          <CarteDecision
            decision={fiche.decision}
            envoi={envoi}
            onEnregistrer={(decision, note) =>
              action(() => api.put(`/candidatures/${id}/decision`, { decision, note }), 'Décision enregistrée. Le score et le classement ne changent pas.')
            }
          />
          <Carte className="flex flex-col gap-3 text-sm">
            <h2 className="font-semibold text-navy-900">Lu dans le CV</h2>
            {fiche.statut_lecture !== 'lue' ? (
              <p className="text-muted">{illisible ? 'Rien : le fichier est illisible.' : 'Lecture en cours…'}</p>
            ) : (
              <>
                <Ligne libelle="Expérience" valeur={formaterExperience(fiche.experience_mois)} />
                <Ligne libelle="Stages (à part)" valeur={formaterExperience(fiche.stages_mois)} />
                <Ligne libelle="Diplôme retenu" valeur={fiche.diplome_niveau || 'Non trouvé'} />
                {fiche.extraction.diplome?.ligne && <p className="text-xs text-muted">« {fiche.extraction.diplome.ligne} »</p>}
                {fiche.extraction.diplome?.ignores?.map((d) => (
                  <p key={d.ligne} className="text-xs text-muted">Non retenu ({d.raison}) : « {d.ligne} »</p>
                ))}
                {fiche.extraction.periodes.length > 0 && (
                  <div>
                    <p className="mb-1 font-medium text-navy-800">Périodes d'expérience retenues</p>
                    <ul className="flex flex-col gap-1 text-xs text-muted">
                      {fiche.extraction.periodes.map((p, i) => (
                        <li key={i}>
                          {p.debut} → {p.en_cours ? "aujourd'hui" : p.fin} · {formaterExperience(p.mois)}
                          {p.stage && <span className="ml-1 rounded bg-navy-50 px-1.5 text-navy-700">stage</span>}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {!fiche.extraction.section_experience_trouvee && (
                  <p className="text-xs text-amber-800">Section « expérience » non repérée : l'expérience est une estimation.</p>
                )}
              </>
            )}
          </Carte>
          <Carte className="flex flex-col gap-2 text-sm">
            <h2 className="font-semibold text-navy-900">Le mail</h2>
            <Ligne libelle="Fichier" valeur={fiche.nom_fichier_cv} />
            {fiche.objet && <Ligne libelle="Objet" valeur={fiche.objet} />}
            {fiche.corps && <p className="max-h-40 overflow-y-auto rounded-lg bg-mist p-3 text-xs whitespace-pre-line text-navy-800">{fiche.corps}</p>}
            {fiche.pieces_jointes.length > 0 && (
              <p className="text-xs text-muted">Autres pièces jointes : {fiche.pieces_jointes.map((p) => p.nom).join(', ')}</p>
            )}
          </Carte>
        </div>
      </div>
    </>
  );
}

function CarteDecision({ decision, envoi, onEnregistrer }) {
  const [etat, setEtat] = useState(decision.etat);
  const [note, setNote] = useState(decision.note || '');
  useEffect(() => {
    setEtat(decision.etat);
    setNote(decision.note || '');
  }, [decision]);
  const modifiee = etat !== decision.etat || note.trim() !== (decision.note || '');

  return (
    <Carte className="flex flex-col gap-3 text-sm">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-semibold text-navy-900">Décision</h2>
        <BadgeDecision decision={decision.etat} />
      </div>
      <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="Décision du recruteur">
        {Object.entries(DECISIONS).map(([cle, libelle]) => (
          <button
            key={cle}
            type="button"
            role="radio"
            aria-checked={etat === cle}
            onClick={() => setEtat(cle)}
            className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
              etat === cle ? 'border-navy-900 bg-navy-900 text-white' : 'border-line bg-white text-navy-800 hover:border-navy-200'
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
      <Bouton disabled={!modifiee} chargement={envoi} onClick={() => onEnregistrer(etat, note)}>
        Enregistrer la décision
      </Bouton>
      <p className="text-xs text-muted">
        {decision.le ? `Décision du ${formaterDateHeure(decision.le)}. ` : ''}
        Modifiable à tout moment ; elle ne change ni le score ni le classement.
      </p>
    </Carte>
  );
}

function Ligne({ libelle, valeur }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-muted">{libelle}</span>
      <span className="text-right font-medium text-navy-900">{valeur}</span>
    </div>
  );
}
