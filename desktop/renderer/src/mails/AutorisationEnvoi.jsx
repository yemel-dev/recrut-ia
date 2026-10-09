// Envoi des mails : API Gmail (boîte liée avec Google, autorisation séparée de la lecture) ou SMTP (boîte liée par
// IMAP, mêmes identifiants que la lecture). Le mode démo simule l'envoi.
import { CheckCircle2, KeyRound, LogOut, PlugZap, RefreshCw, Server, ShieldAlert } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useAgent } from '../agent/ContexteAgent.jsx';
import { Alerte, Bouton, Carte, Champ, Confirmation, Saisie } from '../components/ui.jsx';

function EnTete({ etat, children }) {
  const Icone = etat.autorise || etat.simule ? CheckCircle2 : etat.reconnexion || etat.transport === 'smtp' ? ShieldAlert : KeyRound;
  const couleur = etat.autorise || etat.simule ? 'text-accent-texte' : etat.reconnexion || etat.transport === 'smtp' ? 'text-danger' : 'text-doux';
  return (
    <div className="flex items-start gap-3">
      <Icone className={`mt-0.5 size-5 shrink-0 ${couleur}`} aria-hidden />
      <div className="min-w-0 text-base">
        <h2 className="titre-section">Envoi des mails</h2>
        {children}
      </div>
    </div>
  );
}

export function AutorisationEnvoi({ onChange }) {
  const { notifier } = useAgent();
  const [etat, setEtat] = useState(null);
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState('');
  const [retrait, setRetrait] = useState(false);

  useEffect(() => {
    api.get('/mails/autorisation').then(setEtat, (err) => setErreur(err.message));
  }, []);

  const autoriser = async () => {
    setEnvoi(true);
    setErreur('');
    try {
      const nouveau = await api.post('/mails/autorisation');
      setEtat(nouveau);
      notifier(`Envoi de mails autorisé pour ${nouveau.compte}.`, 'succes');
      onChange?.();
    } catch (err) {
      setErreur(err.message);
    } finally {
      setEnvoi(false);
    }
  };

  const retirer = async () => {
    setEnvoi(true);
    try {
      setEtat(await api.delete('/mails/autorisation'));
      notifier("L'autorisation d'envoi a été retirée de cet ordinateur.", 'succes');
      onChange?.();
    } catch (err) {
      setErreur(err.message);
    } finally {
      setEnvoi(false);
      setRetrait(false);
    }
  };

  if (!etat) return erreur ? <Alerte>{erreur}</Alerte> : <div className="squelette h-28 rounded-lg" />;
  if (etat.transport === 'smtp') return <EnvoiSmtp etat={etat} setEtat={setEtat} onChange={onChange} />;

  return (
    <Carte className="flex flex-col gap-3">
      <EnTete etat={etat}>
        {etat.simule ? (
          <p className="mt-1 text-doux">Mode démo : l'envoi est simulé, aucun mail ne part réellement.</p>
        ) : etat.autorise ? (
          <p className="mt-1 text-doux">
            Les mails partent depuis <strong className="text-fort">{etat.compte}</strong>, en réponse au mail de candidature quand c'est possible.
          </p>
        ) : (
          <p className={`mt-1 ${etat.reconnexion ? 'text-danger' : 'text-doux'}`}>{etat.motif}</p>
        )}
        {!etat.simule && !etat.autorise && (
          <p className="mt-1.5 text-sm text-tenu">
            INJARA lit les candidatures avec une autorisation en lecture seule. Pour répondre aux candidats, Google demande une
            autorisation de plus : envoyer des mails, et lire les en-têtes du mail de candidature pour répondre dans le même fil.
            Votre navigateur va s'ouvrir sur la page Google ; choisissez le compte qui reçoit les candidatures.
          </p>
        )}
      </EnTete>
      {erreur && <Alerte>{erreur}</Alerte>}
      {!etat.simule && (
        <div className="flex flex-wrap items-center gap-2">
          {!etat.autorise && (
            <Bouton icone={etat.reconnexion ? RefreshCw : KeyRound} chargement={envoi} onClick={autoriser}>
              {etat.reconnexion ? 'Reconnecter le compte' : "Autoriser l'envoi"}
            </Bouton>
          )}
          {envoi && <span className="text-sm text-doux">Terminez l'autorisation dans votre navigateur…</span>}
          {etat.autorise && <Bouton variante="discret" icone={LogOut} onClick={() => setRetrait(true)}>Retirer l'autorisation</Bouton>}
        </div>
      )}
      <Confirmation
        ouverte={retrait}
        titre="Retirer l'autorisation d'envoi ?"
        libelleConfirmer="Retirer"
        chargement={envoi}
        onConfirmer={retirer}
        onAnnuler={() => setRetrait(false)}
      >
        Plus aucun mail ne pourra partir tant que l'envoi n'est pas de nouveau autorisé. La lecture des candidatures n'est pas touchée.
      </Confirmation>
    </Carte>
  );
}

/** Boîte liée par IMAP : envoi par SMTP avec les mêmes identifiants, serveur détecté ou saisi. */
function EnvoiSmtp({ etat, setEtat, onChange }) {
  const { notifier } = useAgent();
  const [edition, setEdition] = useState(false);
  const [hote, setHote] = useState(etat.serveur?.auto ? '' : etat.serveur?.hote || '');
  const [port, setPort] = useState(etat.serveur?.port || 465);
  const [erreurs, setErreurs] = useState({});
  const [envoi, setEnvoi] = useState(false);

  const executer = async (requete, succes) => {
    setEnvoi(true);
    setErreurs({});
    try {
      const nouveau = await requete();
      setEtat(nouveau);
      if (nouveau.autorise) notifier(succes, 'succes');
      setEdition(false);
      onChange?.();
    } catch (err) {
      setErreurs(err.champs || { hote: err.message });
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <Carte className="flex flex-col gap-3">
      <EnTete etat={etat}>
        {etat.autorise ? (
          <p className="mt-1 text-doux">
            Les mails partent depuis <strong className="text-fort">{etat.compte}</strong>, avec le mot de passe déjà enregistré pour la
            lecture de la boîte.
          </p>
        ) : (
          <p className="mt-1 text-danger">{etat.motif}</p>
        )}
        {etat.serveur && (
          <p className="mt-1.5 flex items-center gap-1.5 text-sm text-tenu">
            <Server className="size-3.5" aria-hidden />
            Serveur d'envoi : {etat.serveur.hote}, port {etat.serveur.port}
            {etat.serveur.auto ? ' (détecté automatiquement)' : ' (saisi à la main)'}
          </p>
        )}
      </EnTete>
      {edition ? (
        <div className="flex flex-col gap-3 rounded-md border border-trait bg-enfonce p-3">
          <p className="text-sm text-doux">Votre hébergeur indique l'adresse du serveur d'envoi (SMTP), souvent « smtp.votredomaine » ou « mail.votredomaine ».</p>
          <div className="grid grid-cols-3 gap-2">
            <Champ label="Serveur d'envoi (SMTP)" erreur={erreurs.hote} className="col-span-2">
              {(a) => <Saisie {...a} value={hote} onChange={(e) => setHote(e.target.value)} placeholder="smtp.mondomaine.cm" />}
            </Champ>
            <Champ label="Port" erreur={erreurs.port}>
              {(a) => <Saisie {...a} type="number" value={port} onChange={(e) => setPort(e.target.value)} />}
            </Champ>
          </div>
          <div className="flex flex-wrap gap-2">
            <Bouton chargement={envoi} onClick={() => executer(() => api.put('/mails/smtp', { hote, port: Number(port) }), "Serveur d'envoi accepté.")}>
              Enregistrer et tester
            </Bouton>
            <Bouton variante="discret" onClick={() => executer(() => api.put('/mails/smtp', { hote: '' }), 'Détection automatique rétablie.')}>
              Détection automatique
            </Bouton>
            <Bouton variante="discret" onClick={() => setEdition(false)}>Annuler</Bouton>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Bouton variante="secondaire" icone={PlugZap} chargement={envoi} onClick={() => executer(() => api.post('/mails/autorisation'), "Connexion au serveur d'envoi réussie.")}>
            Tester la connexion
          </Bouton>
          <Bouton variante="discret" icone={Server} onClick={() => setEdition(true)}>Modifier le serveur d'envoi</Bouton>
        </div>
      )}
      {erreurs.hote && !edition && <Alerte>{erreurs.hote}</Alerte>}
    </Carte>
  );
}
