// Écran de confirmation d'un envoi : destinataires et aperçu de chaque mail, exclus avec la raison, puis résultat
// ligne par ligne. Rien ne part avant le clic sur « Envoyer ».
import { CheckCircle2, ChevronDown, CircleAlert, Send, TriangleAlert, X } from 'lucide-react';
import { useEffect, useId, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Alerte, Bouton, cx } from '../components/ui.jsx';
import { ApercuMail } from './elements.jsx';

/**
 * charger() -> préparation { destinataires, exclus, mode_test, autorisation, blocages }
 * envoyer(ids, echecsSeulement) -> résultat { resultats, envoyes, echecs, ignores }
 */
export default function FenetreEnvoi({ ouverte, titre, charger, envoyer, onFerme }) {
  const dialogue = useRef(null);
  const idTitre = useId();
  const [preparation, setPreparation] = useState(null);
  const [resultat, setResultat] = useState(null);
  const [ouvert, setOuvert] = useState(null);
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState('');

  useEffect(() => {
    const d = dialogue.current;
    if (!d) return;
    if (ouverte && !d.open) {
      d.showModal();
      setPreparation(null);
      setResultat(null);
      setOuvert(null);
      setErreur('');
      charger().then(setPreparation, (err) => setErreur(err.message));
    }
    if (!ouverte && d.open) d.close();
  }, [ouverte]); // eslint-disable-line react-hooks/exhaustive-deps

  const lancer = async (echecsSeulement = false) => {
    setEnvoi(true);
    setErreur('');
    try {
      const ids = echecsSeulement
        ? resultat.resultats.filter((r) => r.statut === 'echec').map((r) => r.candidature_id)
        : preparation.destinataires.map((d) => d.candidature_id);
      const nouveau = await envoyer(ids, echecsSeulement);
      setResultat(echecsSeulement ? fusionner(resultat, nouveau) : nouveau);
    } catch (err) {
      setErreur(err.message);
    } finally {
      setEnvoi(false);
    }
  };

  const fermer = () => {
    if (!envoi) onFerme(Boolean(resultat));
  };

  const n = preparation?.destinataires.length ?? 0;
  const bloque = (preparation?.blocages.length ?? 0) > 0;
  const autorisation = preparation?.autorisation;

  return (
    <dialog
      ref={dialogue}
      aria-labelledby={idTitre}
      onCancel={(e) => {
        e.preventDefault();
        fermer();
      }}
      className="modale-native m-auto flex max-h-[88vh] w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-trait-fort bg-surface-2 p-0 text-texte shadow-flottante"
    >
      <div className="flex items-start justify-between gap-4 border-b border-trait px-6 py-4">
        <div>
          <h2 id={idTitre} className="titre-section">{titre}</h2>
          {preparation && !resultat && (
            <p className="mt-1 font-affichage text-2xl font-medium text-fort tabular-nums">
              {n} destinataire{n > 1 ? 's' : ''}
              {preparation.exclus.length > 0 && (
                <span className="ml-2 font-sans text-sm font-normal text-doux">
                  · {preparation.exclus.length} non concerné{preparation.exclus.length > 1 ? 's' : ''}
                </span>
              )}
            </p>
          )}
        </div>
        <Bouton variante="discret" taille="sm" icone={X} onClick={fermer} aria-label="Fermer" />
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4 text-sm">
        {erreur && <Alerte className="mb-3">{erreur}</Alerte>}
        {!preparation && !erreur && <div className="squelette h-24 rounded-md" />}
        {preparation && (
          <div className="flex flex-col gap-3">
            {preparation.mode_test.actif && (
              <Alerte ton="alerte">
                Mode test : les mails partiront vers {preparation.mode_test.adresse || "l'adresse de test (non renseignée)"}, pas aux candidats.
              </Alerte>
            )}
            {preparation.blocages.map((b) => (
              <Alerte key={b}>{b}</Alerte>
            ))}
            {autorisation && !autorisation.autorise && (
              <p>
                <Link to="/parametres/mails" onClick={() => onFerme(false)} className="font-semibold text-accent-texte underline underline-offset-4">
                  {autorisation.transport === 'smtp'
                    ? "Vérifier le serveur d'envoi"
                    : autorisation.reconnexion
                      ? 'Reconnecter le compte'
                      : 'Reconnecter la boîte'}
                </Link>{' '}
                <span className="text-doux">dans Mails aux candidats.</span>
              </p>
            )}

            {resultat ? (
              <Resultats resultat={resultat} />
            ) : (
              <>
                {n === 0 && <p className="rounded-md bg-enfonce px-4 py-5 text-center text-doux">Aucun destinataire pour cet envoi.</p>}
                <ul className="flex flex-col">
                  {preparation.destinataires.map((d) => {
                    const deplie = ouvert === d.candidature_id;
                    return (
                      <li key={d.candidature_id} className="border-t border-trait first:border-t-0">
                        <button
                          type="button"
                          onClick={() => setOuvert(deplie ? null : d.candidature_id)}
                          className="flex w-full items-center justify-between gap-3 py-2.5 text-left"
                          aria-expanded={deplie}
                        >
                          <span className="min-w-0">
                            <span className="font-semibold text-fort">{d.nom}</span>
                            <span className="ml-2 text-doux">{d.destinataire}</span>
                            {d.dans_le_fil && <span className="ml-2 text-xs text-tenu">· réponse dans le fil</span>}
                          </span>
                          <ChevronDown className={cx('size-4 shrink-0 text-doux transition-transform duration-200', deplie && 'rotate-180')} aria-hidden />
                        </button>
                        {deplie && (
                          <div className="pb-3">
                            <ApercuMail objet={d.objet} corps={d.corps} destinataire={d.destinataire_effectif} />
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
                {preparation.exclus.length > 0 && (
                  <div className="border-t border-trait pt-3">
                    <p className="etiquette mb-2">Non concernés par cet envoi</p>
                    <ul className="flex flex-col gap-1.5">
                      {preparation.exclus.map((e) => (
                        <li key={e.candidature_id} className="flex gap-2 text-doux">
                          <TriangleAlert className="mt-0.5 size-3.5 shrink-0 text-alerte" aria-hidden />
                          <span>
                            <span className="font-medium text-fort">{e.nom}</span> : {e.raison}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>

      <div className="flex justify-end gap-2 border-t border-trait bg-survol px-6 py-3.5">
        {resultat ? (
          <>
            {resultat.resultats.some((r) => r.statut === 'echec') && (
              <Bouton variante="secondaire" chargement={envoi} onClick={() => lancer(true)}>Relancer les échecs</Bouton>
            )}
            <Bouton onClick={fermer}>Fermer</Bouton>
          </>
        ) : (
          <>
            <Bouton variante="secondaire" onClick={fermer} disabled={envoi}>Annuler</Bouton>
            <Bouton icone={Send} geste="avancer" chargement={envoi} disabled={!preparation || n === 0 || bloque} onClick={() => lancer(false)}>
              Envoyer {n} mail{n > 1 ? 's' : ''}
            </Bouton>
          </>
        )}
      </div>
    </dialog>
  );
}

function Resultats({ resultat }) {
  return (
    <>
      <p className="font-semibold text-fort">
        {resultat.envoyes} envoyé{resultat.envoyes > 1 ? 's' : ''}
        {resultat.echecs > 0 && ` · ${resultat.echecs} échec${resultat.echecs > 1 ? 's' : ''}`}
        {resultat.ignores > 0 && ` · ${resultat.ignores} ignoré${resultat.ignores > 1 ? 's' : ''}`}
        {resultat.mode_test && ' (mode test)'}
      </p>
      <ul className="flex flex-col gap-1.5">
        {resultat.resultats.map((r) => (
          <li key={r.candidature_id} className="flex items-start gap-2">
            {r.statut === 'envoye' ? (
              <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-accent-texte" aria-hidden />
            ) : (
              <CircleAlert className={cx('mt-0.5 size-4 shrink-0', r.statut === 'echec' ? 'text-danger' : 'text-alerte')} aria-hidden />
            )}
            <span>
              <span className="font-medium text-fort">{r.nom}</span>
              <span className="text-doux">
                {r.statut === 'envoye' && ` : envoyé à ${r.destinataire_effectif}`}
                {r.statut === 'echec' && ` : échec, ${r.erreur}`}
                {r.statut === 'ignore' && ` : non envoyé, ${r.raison}`}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </>
  );
}

/** Après « Relancer les échecs » : on remplace les lignes relancées dans le résultat affiché. */
function fusionner(avant, relance) {
  const parId = Object.fromEntries(relance.resultats.map((r) => [r.candidature_id, r]));
  const resultats = avant.resultats.map((r) => parId[r.candidature_id] || r);
  return {
    ...avant,
    resultats,
    envoyes: resultats.filter((r) => r.statut === 'envoye').length,
    echecs: resultats.filter((r) => r.statut === 'echec').length,
    ignores: resultats.filter((r) => r.statut === 'ignore').length,
  };
}
