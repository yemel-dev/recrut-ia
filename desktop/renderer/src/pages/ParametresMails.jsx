// Mails aux candidats : envoi (Gmail ou SMTP), mode test et modèles (invitation, réponse négative).
import { Eye, FlaskConical, RotateCcw, Save } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { useAgent } from '../agent/ContexteAgent.jsx';
import { Alerte, Badge, Bouton, Carte, Champ, Chargement, Confirmation, EnTetePage, Interrupteur, Saisie, ZoneTexte } from '../components/ui.jsx';
import { AutorisationEnvoi } from '../mails/AutorisationEnvoi.jsx';
import { ApercuMail } from '../mails/elements.jsx';

const TITRES = { invitation: 'Invitation à un entretien', refus: 'Réponse négative' };

/** Prévient la mise en page (bandeau du mode test, état de l'envoi) qu'un réglage a changé. */
export const signalerReglagesMails = () => window.dispatchEvent(new Event('injara:reglages-mails'));

export default function ParametresMails() {
  const [reglages, setReglages] = useState(null);
  const [erreur, setErreur] = useState('');

  useEffect(() => {
    api.get('/parametres/mails').then(setReglages, (err) => setErreur(err.message));
  }, []);

  const mettreAJour = (nouveaux) => {
    setReglages(nouveaux);
    signalerReglagesMails();
  };

  if (!reglages) return erreur ? <Alerte>{erreur}</Alerte> : <Chargement />;

  return (
    <>
      <EnTetePage
        titre="Mails aux candidats"
        description="Aucun mail ne part automatiquement : vous préparez l'envoi, vous voyez un aperçu, puis vous confirmez."
      />
      <div className="flex flex-col gap-6">
        <AutorisationEnvoi onChange={signalerReglagesMails} />
        <ModeTest modeTest={reglages.mode_test} environnement={reglages.environnement} onEnregistre={mettreAJour} />
        {Object.keys(TITRES).map((type) => (
          <EditeurModele key={type} type={type} modele={reglages.modeles[type]} variables={reglages.variables} onEnregistre={mettreAJour} />
        ))}
      </div>
    </>
  );
}

function ModeTest({ modeTest, environnement, onEnregistre }) {
  const { notifier } = useAgent();
  const [actif, setActif] = useState(modeTest.actif);
  const [adresse, setAdresse] = useState(modeTest.adresse || '');
  const [erreurs, setErreurs] = useState({});
  const [envoi, setEnvoi] = useState(false);

  const enregistrer = async () => {
    setEnvoi(true);
    setErreurs({});
    try {
      onEnregistre(await api.put('/parametres/mails/mode-test', { actif, adresse }));
      notifier(actif ? `Mode test actif : les mails partiront vers ${adresse}.` : 'Mode test désactivé : les mails partiront aux candidats.', 'succes');
    } catch (err) {
      setErreurs(err.champs || { adresse: err.message });
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <Carte className="flex flex-col gap-4">
      <div className="flex items-start gap-3">
        <FlaskConical className="mt-0.5 size-5 shrink-0 text-alerte" aria-hidden />
        <div className="text-base">
          <h2 className="titre-section">Mode test</h2>
          <p className="mt-1 text-doux">
            Tous les mails partent vers l'adresse ci-dessous, avec le vrai destinataire rappelé au début de l'objet. Les envois de test
            ne comptent pas comme des envois aux candidats.
            {modeTest.par_defaut && environnement !== 'production' && ' Actif par défaut en développement.'}
          </p>
        </div>
      </div>
      <Interrupteur actif={actif} onChange={setActif} libelle="Activer le mode test" />
      <Champ label="Adresse de redirection" erreur={erreurs.adresse} aide="Une adresse à vous, pour recevoir les mails de test.">
        {(a) => <Saisie {...a} type="email" value={adresse} onChange={(e) => setAdresse(e.target.value)} placeholder="vous@exemple.cm" />}
      </Champ>
      <div>
        <Bouton icone={Save} chargement={envoi} onClick={enregistrer}>Enregistrer le mode test</Bouton>
      </div>
    </Carte>
  );
}

function EditeurModele({ type, modele, variables, onEnregistre }) {
  const { notifier } = useAgent();
  const [objet, setObjet] = useState(modele.objet);
  const [corps, setCorps] = useState(modele.corps);
  const [apercu, setApercu] = useState(null);
  const [erreurs, setErreurs] = useState({});
  const [envoi, setEnvoi] = useState(false);
  const [retablir, setRetablir] = useState(false);

  useEffect(() => {
    setObjet(modele.objet);
    setCorps(modele.corps);
  }, [modele]);

  const voirApercu = async () => {
    setErreurs({});
    try {
      setApercu(await api.post(`/parametres/mails/modeles/${type}/apercu`, { objet, corps }));
    } catch (err) {
      setErreurs(err.champs || {});
    }
  };

  const enregistrer = async () => {
    setEnvoi(true);
    setErreurs({});
    try {
      onEnregistre(await api.put(`/parametres/mails/modeles/${type}`, { objet, corps }));
      notifier(`Modèle « ${TITRES[type]} » enregistré.`, 'succes');
    } catch (err) {
      setErreurs(err.champs || {});
    } finally {
      setEnvoi(false);
    }
  };

  const remettre = async () => {
    setEnvoi(true);
    try {
      onEnregistre(await api.delete(`/parametres/mails/modeles/${type}`));
      setApercu(null);
      notifier(`Modèle « ${TITRES[type]} » rétabli.`, 'succes');
    } finally {
      setEnvoi(false);
      setRetablir(false);
    }
  };

  return (
    <Carte className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="titre-section">{TITRES[type]}</h2>
        <Badge ton={modele.par_defaut ? 'neutre' : 'info'}>{modele.par_defaut ? 'Modèle par défaut' : 'Modèle personnalisé'}</Badge>
      </div>
      <Champ label="Objet" erreur={erreurs.objet}>
        {(a) => <Saisie {...a} value={objet} maxLength={200} onChange={(e) => setObjet(e.target.value)} />}
      </Champ>
      <Champ label="Texte du mail" erreur={erreurs.corps}>
        {(a) => <ZoneTexte {...a} rows={12} value={corps} maxLength={5000} onChange={(e) => setCorps(e.target.value)} className="font-mono text-sm" />}
      </Champ>
      <div className="text-sm text-doux">
        <p className="flex flex-wrap gap-1.5">
          Variables :
          {variables.map((v) => (
            <code key={v} className="rounded-sm border border-trait bg-enfonce px-1.5 text-xs text-fort">{`{${v}}`}</code>
          ))}
        </p>
        <p className="mt-1.5 text-tenu">
          Sans nom fiable dans le CV, {'{civilite_nom}'} devient « Madame, Monsieur ». Une ligne réduite à {'{message}'} disparaît si le
          message est vide. Pour un entretien en ligne, {'{lieu}'} contient le lien de la visio.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Bouton icone={Save} chargement={envoi} onClick={enregistrer}>Enregistrer</Bouton>
        <Bouton variante="secondaire" icone={Eye} onClick={voirApercu}>Aperçu</Bouton>
        {!modele.par_defaut && <Bouton variante="discret" icone={RotateCcw} onClick={() => setRetablir(true)}>Rétablir le modèle par défaut</Bouton>}
      </div>
      {apercu && <ApercuMail objet={apercu.objet} corps={apercu.corps} note="Aperçu avec des valeurs d'exemple." />}
      <Confirmation
        ouverte={retablir}
        titre="Rétablir le modèle par défaut ?"
        libelleConfirmer="Rétablir"
        chargement={envoi}
        onConfirmer={remettre}
        onAnnuler={() => setRetablir(false)}
      >
        Votre texte personnalisé sera remplacé par le modèle d'origine.
      </Confirmation>
    </Carte>
  );
}
