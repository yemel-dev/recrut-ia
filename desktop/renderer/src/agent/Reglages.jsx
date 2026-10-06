// Compte lié et réglages de l'agent (profils + réglages avancés).
import { Check, LogOut, TriangleAlert } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { Alerte, Bouton, Carte, Champ, Chargement, Confirmation, Interrupteur, Liste, Saisie, SaisieListe } from '../components/ui.jsx';
import { formaterDateHeure } from '../format.js';
import { useAgent } from './ContexteAgent.jsx';
import Diagnostic from './Diagnostic.jsx';
import { FOURNISSEURS, MODES_PERIODE } from './libelles.js';

export default function Reglages() {
  return (
    <div className="flex flex-col gap-6">
      <CompteLie />
      <ReglagesAgent />
      <Diagnostic />
    </div>
  );
}

function CompteLie() {
  const { statut, rafraichir, reconnexionConseillee, oublierErreursSync } = useAgent();
  const [confirmation, setConfirmation] = useState(false);
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState('');

  const deconnecter = async () => {
    setEnvoi(true);
    try {
      await api.post('/gmail/disconnect');
      oublierErreursSync();
      setConfirmation(false);
      await rafraichir();
    } catch (err) {
      setErreur(err.message);
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <Carte>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold tracking-wide text-muted uppercase">Boîte mail liée</p>
          <p className="mt-1 text-lg font-semibold text-navy-900">{statut.account_email || FOURNISSEURS[statut.provider]}</p>
          <p className="text-sm text-muted">
            {statut.account_email && `${FOURNISSEURS[statut.provider]} · `}{statut.total_cvs} CV · Dernière vérification : {formaterDateHeure(statut.last_sync_at)}
          </p>
        </div>
        <Bouton variante="secondaire" icone={LogOut} onClick={() => setConfirmation(true)}>Déconnecter le compte</Bouton>
      </div>
      {reconnexionConseillee && (
        <p className="mt-4 flex items-start gap-2 rounded-lg bg-danger-50 px-4 py-3 text-sm text-danger">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          Les dernières vérifications ont échoué. Déconnectez le compte, puis liez-le de nouveau avec le mot de passe ou
          l'autorisation à jour.
        </p>
      )}
      {erreur && <div className="mt-4"><Alerte>{erreur}</Alerte></div>}
      <Confirmation
        ouverte={confirmation}
        titre="Déconnecter ce compte ?"
        libelleConfirmer="Déconnecter"
        chargement={envoi}
        onConfirmer={deconnecter}
        onAnnuler={() => setConfirmation(false)}
      >
        Les CV déjà importés sont conservés. Le mot de passe ou l'autorisation enregistrés sont supprimés de cet ordinateur.
      </Confirmation>
    </Carte>
  );
}

function ReglagesAgent() {
  const { notifier, rafraichir } = useAgent();
  const [profils, setProfils] = useState(null);
  const [config, setConfig] = useState(null);
  const [formulaire, setFormulaire] = useState(null);
  const [erreurs, setErreurs] = useState({});
  const [erreur, setErreur] = useState('');
  const [envoi, setEnvoi] = useState(false);

  useEffect(() => {
    Promise.all([api.get('/gmail/profiles'), api.get('/gmail/config')]).then(([p, c]) => {
      setProfils(p);
      appliquer(c);
    }, (err) => setErreur(err.message));
  }, []);

  const appliquer = (c) => {
    setConfig(c);
    setFormulaire({ ...c, since_date: c.since_date || '', folder: c.folder || '' });
  };

  const enregistre = (c) => {
    appliquer(c);
    setErreurs({});
    notifier('Réglages enregistrés. Cliquez sur « Vérifier maintenant » (page Candidatures) pour les appliquer.', 'succes');
    rafraichir();
  };

  const choisirProfil = async (nom) => {
    setErreur('');
    try {
      enregistre(await api.put(`/gmail/config/profile/${nom}`));
    } catch (err) {
      setErreur(err.message);
    }
  };

  const enregistrer = async (e) => {
    e.preventDefault();
    setErreur('');
    setErreurs({});
    setEnvoi(true);
    try {
      enregistre(
        await api.put('/gmail/config', {
          ...formulaire,
          days: Number(formulaire.days),
          max_attachment_mb: Number(formulaire.max_attachment_mb),
          since_date: formulaire.since_date || null,
          folder: formulaire.folder.trim() || null,
        }),
      );
    } catch (err) {
      setErreurs(err.champs);
      setErreur(err.champs.requete || (Object.keys(err.champs).length ? 'Certains réglages sont à corriger.' : err.message));
    } finally {
      setEnvoi(false);
    }
  };

  if (!config) return erreur ? <Alerte>{erreur}</Alerte> : <Carte><Chargement /></Carte>;
  const champ = (nom) => ({ value: formulaire[nom], onChange: (e) => setFormulaire((f) => ({ ...f, [nom]: e.target.value })) });
  const extension = (ext, actif) =>
    setFormulaire((f) => ({ ...f, allowed_extensions: actif ? [...new Set([...f.allowed_extensions, ext])] : f.allowed_extensions.filter((x) => x !== ext) }));

  return (
    <Carte className="flex flex-col gap-5">
      <div>
        <h2 className="font-semibold text-navy-900">Réglages de l'agent</h2>
        <p className="mt-1 text-sm text-muted">{config.description}</p>
      </div>
      <Alerte>{erreur}</Alerte>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {profils.map((p) => {
          const actif = config.profile === p.name;
          return (
            <button
              key={p.name}
              type="button"
              onClick={() => !actif && choisirProfil(p.name)}
              className={`rounded-xl border p-4 text-left transition-colors ${actif ? 'border-brand-500 bg-brand-50' : 'border-line hover:border-navy-200'}`}
            >
              <span className="flex items-center gap-2 font-semibold text-navy-900">
                {actif && <Check className="size-4 text-brand-700" aria-hidden />}
                {p.label}
              </span>
              <span className="mt-1 block text-sm text-muted">{p.description}</span>
            </button>
          );
        })}
      </div>
      {config.profile === 'custom' && <p className="text-sm text-muted">Réglages personnalisés (voir les réglages avancés).</p>}

      <details className="rounded-xl border border-line">
        <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-navy-800">Réglages avancés</summary>
        <form onSubmit={enregistrer} noValidate className="flex flex-col gap-5 border-t border-line p-4">
          {config.warnings?.length > 0 && (
            <div className="rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-900">
              {config.warnings.map((w) => <p key={w} className="flex gap-2"><TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />{w}</p>)}
            </div>
          )}
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            <Champ label="Période" erreur={erreurs.mode}>
              {(a) => <Liste {...a} options={MODES_PERIODE} vide={null} {...champ('mode')} />}
            </Champ>
            {formulaire.mode === 'last_days' && (
              <Champ label="Nombre de jours" erreur={erreurs.days} aide="De 1 à 3650 jours.">
                {(a) => <Saisie {...a} type="number" min={1} max={3650} {...champ('days')} />}
              </Champ>
            )}
            {formulaire.mode === 'since_date' && (
              <Champ label="Depuis le" erreur={erreurs.since_date} obligatoire>
                {(a) => <Saisie {...a} type="date" {...champ('since_date')} />}
              </Champ>
            )}
          </div>

          <div className="flex flex-col gap-3">
            <Interrupteur
              actif={formulaire.ignore_automatic}
              onChange={(v) => setFormulaire((f) => ({ ...f, ignore_automatic: v }))}
              libelle="Ignorer les emails automatiques (newsletters, notifications, réponses automatiques)"
            />
            <Interrupteur
              actif={formulaire.unread_only}
              onChange={(v) => setFormulaire((f) => ({ ...f, unread_only: v }))}
              libelle="Seulement les emails non lus"
            />
            {formulaire.unread_only && (
              <p className="ml-14 text-sm text-amber-800">
                Attention : un email ouvert avant la prochaine vérification n'est plus « non lu » et sera manqué.
              </p>
            )}
          </div>

          <Champ label="Expéditeurs ou domaines à ignorer" erreur={erreurs.ignored_senders} aide="Une adresse (rh@exemple.com) ou un domaine (linkedin.com, qui couvre aussi ses sous-domaines).">
            {(a) => (
              <SaisieListe {...a} placeholder="ex. linkedin.com" valeur={formulaire.ignored_senders} onChange={(v) => setFormulaire((f) => ({ ...f, ignored_senders: v }))} />
            )}
          </Champ>

          <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
            <fieldset className="flex flex-col gap-1.5">
              <legend className="mb-1.5 text-sm font-medium text-navy-800">Types de fichiers acceptés</legend>
              {['pdf', 'docx'].map((ext) => (
                <label key={ext} className="flex items-center gap-2 text-sm text-navy-800">
                  <input
                    type="checkbox"
                    className="size-4 accent-brand-600"
                    checked={formulaire.allowed_extensions.includes(ext)}
                    disabled={formulaire.allowed_extensions.length === 1 && formulaire.allowed_extensions.includes(ext)}
                    onChange={(e) => extension(ext, e.target.checked)}
                  />
                  {ext.toUpperCase()}
                </label>
              ))}
            </fieldset>
            <Champ label="Taille maximale d'une pièce jointe (Mo)" erreur={erreurs.max_attachment_mb} aide="De 1 à 50 Mo.">
              {(a) => <Saisie {...a} type="number" min={1} max={50} {...champ('max_attachment_mb')} />}
            </Champ>
            <Champ label="Dossier ou étiquette à lire" erreur={erreurs.folder} aide="Vide : boîte de réception.">
              {(a) => <Saisie {...a} placeholder="ex. Candidatures" {...champ('folder')} />}
            </Champ>
          </div>

          <div className="flex justify-end gap-2">
            <Bouton variante="secondaire" onClick={() => appliquer(config)}>Annuler les modifications</Bouton>
            <Bouton type="submit" chargement={envoi}>Enregistrer les réglages</Bouton>
          </div>
        </form>
      </details>
    </Carte>
  );
}
