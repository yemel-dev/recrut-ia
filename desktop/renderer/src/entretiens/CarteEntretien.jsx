import { ArrowRight, CalendarClock, CalendarPlus, Check, MapPin, Pencil, TriangleAlert, Video, X } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api.js';
import { useAgent } from '../agent/ContexteAgent.jsx';
import { Alerte, Badge, Bouton, Carte, Champ, Confirmation, Liste, Saisie, Segments, ZoneTexte, cx } from '../components/ui.jsx';
import { STATUTS_ENTRETIEN } from '../constantes.js';
import { formaterDateHeure } from '../format.js';

export const DUREES = [30, 45, 60, 90, 120];

const deuxChiffres = (n) => String(n).padStart(2, '0');
const jourLocal = (d) => `${d.getFullYear()}-${deuxChiffres(d.getMonth() + 1)}-${deuxChiffres(d.getDate())}`;
const heureLocale = (d) => `${deuxChiffres(d.getHours())}:${deuxChiffres(d.getMinutes())}`;

export const formaterDuree = (minutes) => {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (!h) return `${m} min`;
  return m ? `${h} h ${deuxChiffres(m)}` : `${h} h`;
};

/**
 * Entretien d'une candidature : planification (date, durée, en ligne ou sur site), confirmation par le candidat,
 * accès à la salle de visio, historique. Planifier ou replanifier n'envoie aucun mail : l'invitation part depuis le
 * poste (« Envoyer les invitations ») ou la carte « Mails au candidat », après aperçu.
 */
export default function CarteEntretien({ candidatureId, decision, onChange }) {
  const { notifier } = useAgent();
  const [entretiens, setEntretiens] = useState(null);
  const [erreur, setErreur] = useState('');
  const [edition, setEdition] = useState(false);
  const [annulation, setAnnulation] = useState(false);
  const [occupe, setOccupe] = useState(false);

  const charger = useCallback(() => {
    api.get(`/candidatures/${candidatureId}/entretiens`).then(setEntretiens, (err) => setErreur(err.message));
  }, [candidatureId]);
  useEffect(charger, [charger]);

  if (!entretiens) return erreur ? <Alerte>{erreur}</Alerte> : <div className="squelette h-36 rounded-lg" />;
  const actif = entretiens.find((e) => ['planifie', 'en_cours'].includes(e.statut));
  const historique = entretiens.filter((e) => e !== actif);

  const apres = (message) => {
    setEdition(false);
    charger();
    if (message) notifier(message, 'succes');
    onChange?.();
  };

  const executer = async (requete, message) => {
    setOccupe(true);
    setErreur('');
    try {
      await requete();
      apres(message);
    } catch (err) {
      setErreur(err.message);
    } finally {
      setOccupe(false);
      setAnnulation(false);
    }
  };

  return (
    <Carte className="flex flex-col gap-3 text-base">
      <div className="flex items-center justify-between gap-3">
        <h2 className="titre-section flex items-center gap-2">
          <CalendarClock className="size-4 text-doux" aria-hidden /> Entretien
        </h2>
        {actif && (
          <Badge ton={actif.statut === 'en_cours' ? 'danger' : actif.confirme_le ? 'accent' : 'neutre'} point>
            {actif.statut === 'en_cours' ? STATUTS_ENTRETIEN.en_cours : actif.confirme_le ? 'Confirmé' : STATUTS_ENTRETIEN.planifie}
          </Badge>
        )}
      </div>
      {erreur && <Alerte>{erreur}</Alerte>}

      {edition ? (
        <FormulaireEntretien
          candidatureId={candidatureId}
          entretien={actif}
          onEnregistre={() => apres(actif ? 'Entretien replanifié. Aucun mail ne part : prévenez le candidat depuis « Mails au candidat ».' : 'Entretien planifié. Aucun mail ne part avant votre confirmation.')}
          onAnnuler={() => setEdition(false)}
        />
      ) : actif ? (
        <>
          <ResumeEntretien entretien={actif} />
          {actif.mode === 'en_ligne' && (
            <Link
              to={`/entretiens/${actif.id}`}
              className={cx(
                'appui geste-hote flex items-center gap-3 rounded-md border px-3.5 py-3',
                actif.statut === 'en_cours' ? 'border-danger-trait bg-danger-doux' : 'border-accent-trait bg-accent-doux hover:shadow-halo',
              )}
            >
              <span className={cx('size-2 shrink-0 rounded-full', actif.statut === 'en_cours' ? 'ia-pulsation bg-danger' : 'bg-accent')} aria-hidden />
              <span className="min-w-0 flex-1 font-semibold text-fort">{actif.statut === 'en_cours' ? "Reprendre l'entretien" : 'Ouvrir la salle de visio'}</span>
              <ArrowRight className="size-4 text-fort" aria-hidden data-geste="avancer" />
            </Link>
          )}
          {actif.statut === 'planifie' && (
            <div className="flex flex-wrap gap-1.5">
              <Bouton
                variante="secondaire"
                taille="sm"
                icone={Check}
                chargement={occupe}
                onClick={() =>
                  executer(
                    () => api.put(`/entretiens/${actif.id}/confirmation`, { confirme: !actif.confirme_le }),
                    actif.confirme_le ? 'Confirmation retirée.' : 'Entretien marqué confirmé par le candidat.',
                  )
                }
              >
                {actif.confirme_le ? 'Retirer la confirmation' : 'Marquer confirmé'}
              </Bouton>
              <Bouton variante="discret" taille="sm" icone={Pencil} onClick={() => setEdition(true)}>Replanifier</Bouton>
              <Bouton variante="discret" taille="sm" icone={X} onClick={() => setAnnulation(true)}>Annuler</Bouton>
            </div>
          )}
          {actif.statut === 'planifie' && !actif.confirme_le && (
            <p className="text-sm text-doux">Le candidat confirme en répondant au mail d'invitation ; marquez ensuite l'entretien comme confirmé.</p>
          )}
        </>
      ) : (
        <>
          <Bouton icone={CalendarPlus} geste="grandir" onClick={() => setEdition(true)}>Planifier un entretien</Bouton>
          {decision?.etat !== 'retenu' && <p className="text-sm text-doux">Ce candidat n'est pas marqué « Retenu » : vous pouvez tout de même planifier un entretien.</p>}
        </>
      )}

      {historique.length > 0 && (
        <ul className="flex flex-col border-t border-trait pt-1">
          {historique.map((e) => (
            <li key={e.id} className="flex items-center justify-between gap-3 py-2">
              <Link to={`/entretiens/${e.id}`} className="font-medium text-fort hover:underline">{STATUTS_ENTRETIEN[e.statut]}</Link>
              <span className="text-sm text-doux tabular-nums">{formaterDateHeure(e.fin_le || e.cree_le || e.date_entretien)}</span>
            </li>
          ))}
        </ul>
      )}
      <Confirmation
        ouverte={annulation}
        titre="Annuler l'entretien ?"
        libelleConfirmer="Annuler l'entretien"
        chargement={occupe}
        onConfirmer={() => executer(() => api.put(`/entretiens/${actif.id}/statut`, { statut: 'annule' }), 'Entretien annulé.')}
        onAnnuler={() => setAnnulation(false)}
      >
        Le lien de la visio ne fonctionnera plus. Aucun mail n'est envoyé au candidat.
      </Confirmation>
    </Carte>
  );
}

function ResumeEntretien({ entretien }) {
  return (
    <div className="flex flex-col gap-1.5">
      <p className="font-semibold text-fort first-letter:uppercase">
        {entretien.date_entretien
          ? new Date(entretien.date_entretien).toLocaleString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })
          : 'Date à fixer'}
      </p>
      <p className="flex items-center gap-1.5 text-sm text-doux">
        {entretien.mode === 'en_ligne' ? <Video className="size-3.5" aria-hidden /> : <MapPin className="size-3.5" aria-hidden />}
        {formaterDuree(entretien.duree_minutes || 60)} · {entretien.mode === 'en_ligne' ? 'En ligne, visio INJARA' : entretien.adresse}
      </p>
      {entretien.message && <p className="rounded-md bg-enfonce px-3 py-2 text-sm text-texte">{entretien.message}</p>}
      {entretien.chevauchements?.length > 0 && (
        <p className="flex gap-2 text-sm text-alerte">
          <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          Chevauche {entretien.chevauchements.map((c) => `l'entretien de ${c.candidat || 'un candidat'}${c.poste_intitule ? ` (${c.poste_intitule})` : ''}`).join(', ')}.
        </p>
      )}
    </div>
  );
}

function FormulaireEntretien({ candidatureId, entretien, onEnregistre, onAnnuler }) {
  const depart = entretien?.date_entretien ? new Date(entretien.date_entretien) : null;
  const [jour, setJour] = useState(depart ? jourLocal(depart) : '');
  const [heure, setHeure] = useState(depart ? heureLocale(depart) : '09:00');
  const [duree, setDuree] = useState(entretien?.duree_minutes || 60);
  const [mode, setMode] = useState(entretien?.mode || 'en_ligne');
  const [adresse, setAdresse] = useState(entretien?.adresse || '');
  const [message, setMessage] = useState(entretien?.message || '');
  const [erreurs, setErreurs] = useState({});
  const [envoi, setEnvoi] = useState(false);

  const enregistrer = async (e) => {
    e.preventDefault();
    if (!jour || !heure) {
      setErreurs({ date_entretien: 'Choisissez une date et une heure.' });
      return;
    }
    setEnvoi(true);
    setErreurs({});
    const corps = {
      date_entretien: new Date(`${jour}T${heure}`).toISOString(), // heure locale du poste, envoyée en UTC
      duree_minutes: Number(duree),
      mode,
      adresse,
      message,
    };
    try {
      if (entretien) await api.put(`/entretiens/${entretien.id}`, corps);
      else await api.post(`/candidatures/${candidatureId}/entretiens`, corps);
      onEnregistre();
    } catch (err) {
      setErreurs(Object.keys(err.champs || {}).length ? err.champs : { date_entretien: err.message });
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <form onSubmit={enregistrer} className="flex flex-col gap-3">
      <Segments
        libelle="Mode de l'entretien"
        valeur={mode}
        onChange={setMode}
        options={[
          { valeur: 'en_ligne', libelle: 'En ligne (visio)' },
          { valeur: 'sur_site', libelle: 'Sur site' },
        ]}
        className="self-start"
      />
      <div className="grid grid-cols-2 gap-2">
        <Champ label="Date" erreur={erreurs.date_entretien} obligatoire>
          {(a) => <Saisie {...a} type="date" min={jourLocal(new Date())} value={jour} onChange={(e) => setJour(e.target.value)} />}
        </Champ>
        <Champ label="Heure" obligatoire>
          {(a) => <Saisie {...a} type="time" value={heure} onChange={(e) => setHeure(e.target.value)} />}
        </Champ>
      </div>
      <Champ label="Durée" erreur={erreurs.duree_minutes}>
        {(a) => (
          <Liste {...a} vide={null} value={duree} onChange={(e) => setDuree(e.target.value)} options={Object.fromEntries(DUREES.map((d) => [d, formaterDuree(d)]))} />
        )}
      </Champ>
      {mode === 'sur_site' ? (
        <Champ label="Adresse" erreur={erreurs.adresse} obligatoire>
          {(a) => <Saisie {...a} value={adresse} maxLength={300} onChange={(e) => setAdresse(e.target.value)} placeholder="Immeuble, quartier, ville" />}
        </Champ>
      ) : (
        <p className="text-sm text-doux">Le lien de la visio est ajouté à l'invitation (accès à distance activé).</p>
      )}
      <Champ label="Message au candidat (facultatif)" erreur={erreurs.message}>
        {(a) => <ZoneTexte {...a} rows={2} maxLength={1000} value={message} onChange={(e) => setMessage(e.target.value)} />}
      </Champ>
      <div className="flex gap-2">
        <Bouton type="submit" chargement={envoi}>{entretien ? 'Enregistrer' : 'Planifier'}</Bouton>
        <Bouton variante="discret" onClick={onAnnuler}>Annuler</Bouton>
      </div>
    </form>
  );
}
