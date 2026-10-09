import { ChevronDown, FileUp, Inbox, Mail, MailX, RefreshCw, RotateCcw, Upload, X } from 'lucide-react';
import { AnimatePresence, m } from 'motion/react';
import { useCallback, useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { api } from '../api.js';
import { useAgent } from '../agent/ContexteAgent.jsx';
import ListeCandidatures from '../candidatures/ListeCandidatures.jsx';
import { FOURNISSEURS, REGLES_IGNORE, resumeSynchro } from '../agent/libelles.js';
import EtatVide from '../components/EtatVide.jsx';
import { Alerte, Badge, Bouton, Carte, Chargement, EnTetePage, Interrupteur, Onglets } from '../components/ui.jsx';
import { COURBE_SORTIE } from '../components/mouvement.js';
import { formaterDateHeure } from '../format.js';
import { useCommande } from '../commandes.js';

export default function Candidatures() {
  const { statut, etat, rafraichir, notifier, version, signalerNouveauxCV } = useAgent();
  const filtreInitial = useLocation().state?.filtre; // venu du tableau de bord
  const [onglet, setOnglet] = useState('candidatures');
  const [compteurs, setCompteurs] = useState(null);
  const [traitement, setTraitement] = useState(null);

  useEffect(() => {
    api.get('/traitement/etat').then(setTraitement, () => {});
  }, []);
  const [resultat, setResultat] = useState(null); // { titre, resume, details }
  const [verification, setVerification] = useState(false);
  const [importEnCours, setImportEnCours] = useState(false);
  const [surDepot, setSurDepot] = useState(false);
  const [erreur, setErreur] = useState('');

  const importer = useCallback(
    async (chemins) => {
      if (!chemins.length) return;
      setImportEnCours(true);
      setErreur('');
      try {
        const reponse = await window.injara.fichiers.importerCV(chemins);
        if (!reponse.ok) throw new Error(reponse.donnees?.detail || "L'import a échoué.");
        const r = reponse.donnees;
        const morceaux = [`${r.imported.length} importé${r.imported.length > 1 ? 's' : ''}`];
        if (r.duplicates_skipped) morceaux.push(`${r.duplicates_skipped} doublon${r.duplicates_skipped > 1 ? 's' : ''}`);
        if (r.rejected.length) morceaux.push(`${r.rejected.length} rejeté${r.rejected.length > 1 ? 's' : ''}`);
        setResultat({
          titre: 'Import de CV',
          resume: morceaux.join(' · '),
          details: r.rejected.map((x) => ({ fichier: x.filename, raison: x.reason })),
        });
        signalerNouveauxCV();
        rafraichir();
      } catch (err) {
        setErreur(err.message);
      } finally {
        setImportEnCours(false);
      }
    },
    [rafraichir, signalerNouveauxCV],
  );

  const choisirFichiers = async () => importer(await window.injara.fichiers.choisirCV());

  const verifier = async () => {
    setVerification(true);
    setErreur('');
    try {
      const r = await api.post('/gmail/sync');
      setResultat({
        titre: 'Vérification de la boîte mail',
        resume: resumeSynchro(r),
        details: r.skipped.map((x) => ({ fichier: x.filename, raison: `${x.reason}${x.sender_email ? ` (${x.sender_email})` : ''}` })),
        erreurs: r.errors,
        tronque: r.truncated,
      });
      signalerNouveauxCV();
      rafraichir();
    } catch (err) {
      setErreur(err.message);
    } finally {
      setVerification(false);
    }
  };

  // Palette de commandes et raccourcis (Ctrl+I) : mêmes actions que les boutons de l'en-tête.
  useCommande('importer-cv', () => !importEnCours && choisirFichiers());
  useCommande('verifier-boite', () => statut?.connected && !statut.needs_setup && !verification && verifier());

  const basculerSurveillance = async (active) => {
    try {
      await api.put('/agent/surveillance', { active });
      notifier(active ? 'Surveillance automatique activée.' : 'Surveillance automatique arrêtée.', 'info');
      rafraichir();
    } catch (err) {
      setErreur(err.message);
    }
  };

  // Glisser-déposer sur toute la page
  const auDepot = (e) => {
    e.preventDefault();
    setSurDepot(false);
    const chemins = [...e.dataTransfer.files].map((f) => window.injara.fichiers.cheminDe(f)).filter(Boolean);
    importer(chemins);
  };

  if (!statut) return <Chargement />;
  const connecte = statut.connected;

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setSurDepot(true);
      }}
      onDragLeave={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) setSurDepot(false);
      }}
      onDrop={auDepot}
      className="relative min-h-[60vh]"
    >
      <AnimatePresence>
        {surDepot && (
          <m.div
            className="pointer-events-none absolute -inset-4 z-30 flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-accent bg-fond/90 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
          >
            <m.span
              className="grid size-14 place-items-center rounded-xl border border-accent-trait bg-accent-doux text-accent-texte shadow-halo"
              initial={{ transform: 'translateY(6px)' }}
              animate={{ transform: 'translateY(0px)' }}
              transition={{ duration: 0.25, ease: COURBE_SORTIE }}
            >
              <Upload className="size-6" aria-hidden />
            </m.span>
            <p className="titre-section">Déposez vos CV ici</p>
            <p className="text-sm text-doux">PDF, DOCX ou ZIP : ils seront lus, notés et classés.</p>
          </m.div>
        )}
      </AnimatePresence>

      <EnTetePage
        titre="Candidatures"
        description="Chaque CV reçu est lu, noté et rattaché au poste le plus proche. Le score aide à décider : rien n'est écarté automatiquement."
        actions={
          <>
            <Bouton variante="secondaire" icone={FileUp} geste="soulever" onClick={choisirFichiers} chargement={importEnCours} aria-keyshortcuts="Control+I">
              Importer des CV
            </Bouton>
            {connecte && !statut.needs_setup && (
              <Bouton icone={RefreshCw} geste="tourner" onClick={verifier} chargement={verification}>Vérifier maintenant</Bouton>
            )}
          </>
        }
      />

      <BarreEtat statut={statut} etat={etat} onSurveillance={basculerSurveillance} />

      {erreur && <Alerte className="mb-4">{erreur}</Alerte>}
      <AnimatePresence>{resultat && <Resultat key={resultat.titre + resultat.resume} resultat={resultat} onFermer={() => setResultat(null)} />}</AnimatePresence>
      {traitement && !traitement.adequation.disponible && (
        <Alerte ton="info" className="mb-5" titre={traitement.adequation.en_chargement ? "Le moteur d'analyse se charge" : 'Analyse sans le moteur sémantique'}>
          {traitement.adequation.en_chargement ? (
            <>
              Cela prend jusqu'à deux minutes. En attendant, les scores reposent sur les compétences, l'expérience et la
              formation ; ils seront complétés automatiquement.
            </>
          ) : (
            <>
              Le critère « adéquation globale » est désactivé : les scores reposent sur les compétences, l'expérience et
              la formation. <span className="text-xs text-doux">({(traitement.adequation.motif || '').split(' : [')[0]})</span>
            </>
          )}
        </Alerte>
      )}

      <Onglets
        valeur={onglet}
        onChange={setOnglet}
        onglets={[
          { valeur: 'candidatures', libelle: 'Candidatures', compteur: compteurs?.total ?? 0 },
          { valeur: 'ignores', libelle: 'Ignorés', compteur: statut.ignored_count },
        ]}
      />
      {onglet === 'candidatures' ? (
        <ListeCandidatures version={version} onImporter={choisirFichiers} onCompteurs={setCompteurs} filtreInitial={filtreInitial} />
      ) : (
        <ListeIgnores connecte={connecte} onRecupere={() => { signalerNouveauxCV(); rafraichir(); }} />
      )}
    </div>
  );
}

function BarreEtat({ statut, etat, onSurveillance }) {
  if (!statut.connected) {
    return (
      <Carte className="mb-5 flex flex-wrap items-center justify-between gap-4 py-3.5">
        <div className="flex items-center gap-3">
          <span className="grid size-8 shrink-0 place-items-center rounded-md bg-survol-fort text-doux"><MailX className="size-4" aria-hidden /></span>
          <p className="text-base text-texte">
            Aucune boîte mail n'est liée. Liez la boîte de recrutement pour récupérer les CV automatiquement ; l'import
            manuel fonctionne déjà.
          </p>
        </div>
        <Link to="/boite-mail" className="shrink-0 text-sm font-semibold text-accent-texte hover:underline">Lier une boîte mail</Link>
      </Carte>
    );
  }
  if (statut.needs_setup) {
    return (
      <Alerte
        ton="succes"
        className="mb-5"
        action={<Link to="/boite-mail" className="shrink-0 self-center text-sm font-semibold text-fort hover:underline">Terminer la configuration</Link>}
      >
        La boîte <strong className="text-fort">{statut.account_email || FOURNISSEURS[statut.provider]}</strong> est liée. Choisissez maintenant les candidatures à reprendre.
      </Alerte>
    );
  }
  return (
    <Carte className="mb-5 flex flex-wrap items-center justify-between gap-x-8 gap-y-3 py-3.5">
      <div className="flex min-w-0 items-center gap-3">
        <span className="relative grid size-8 shrink-0 place-items-center rounded-md bg-accent-doux text-accent-texte">
          <Mail className="size-4" aria-hidden />
          {statut.watching && <span className="ia-pulsation absolute -top-0.5 -right-0.5 size-2 rounded-full bg-accent ring-2 ring-[var(--surface)]" aria-hidden />}
        </span>
        <div className="min-w-0 text-base">
          <p className="truncate font-semibold text-fort">{statut.account_email || FOURNISSEURS[statut.provider]}</p>
          <p className="text-sm text-doux">
            {statut.account_email && `${FOURNISSEURS[statut.provider]} · `}Dernière vérification : {formaterDateHeure(statut.last_sync_at)}
          </p>
        </div>
      </div>
      <div className="flex flex-col items-end gap-1">
        <Interrupteur
          actif={statut.watching}
          onChange={onSurveillance}
          libelle={`Surveillance automatique${statut.watching ? ` (toutes les ${statut.poll_minutes} min)` : ''}`}
        />
        {etat?.surveillance_souhaitee && !statut.watching && <p className="text-xs text-doux">Reprise en cours…</p>}
      </div>
    </Carte>
  );
}

function Resultat({ resultat, onFermer }) {
  const { titre, resume, details = [], erreurs = [], tronque } = resultat;
  return (
    <m.div
      initial={{ opacity: 0, transform: 'translateY(-4px)' }}
      animate={{ opacity: 1, transform: 'translateY(0px)' }}
      exit={{ opacity: 0, transition: { duration: 0.12 } }}
      transition={{ duration: 0.22, ease: COURBE_SORTIE }}
      className="mb-5"
    >
      <Carte className="border-accent-trait py-4" role="status">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="etiquette">{titre}</p>
            <p className="mt-1 text-lg font-semibold text-fort">{resume}</p>
          </div>
          <Bouton variante="discret" taille="sm" icone={X} onClick={onFermer} aria-label="Fermer le résultat" />
        </div>
        {tronque && <p className="mt-2 text-base text-alerte">Il reste des emails à traiter. Cliquez de nouveau sur « Vérifier maintenant ».</p>}
        {erreurs.length > 0 && (
          <Alerte className="mt-3">{erreurs.map((e) => <p key={e}>{e}</p>)}</Alerte>
        )}
        {details.length > 0 && (
          <details className="group mt-3 text-base">
            <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 font-medium text-texte hover:text-fort">
              <ChevronDown className="size-4 transition-transform group-open:rotate-180" aria-hidden />
              Fichiers écartés ({details.length})
            </summary>
            <ul className="mt-2 flex flex-col gap-1 border-l border-trait pl-4">
              {details.map((d, i) => (
                <li key={i} className="text-sm text-doux"><span className="font-medium text-texte">{d.fichier}</span> : {d.raison}</li>
              ))}
            </ul>
          </details>
        )}
      </Carte>
    </m.div>
  );
}

function ListeIgnores({ connecte, onRecupere }) {
  const { notifier } = useAgent();
  const [elements, setElements] = useState(null);
  const [erreur, setErreur] = useState('');
  const [enCours, setEnCours] = useState(null);
  const [messages, setMessages] = useState({});

  const charger = useCallback(() => {
    api.get('/gmail/ignored?limit=200').then(setElements, (err) => setErreur(err.message));
  }, []);
  useEffect(charger, [charger]);

  const recuperer = async (element) => {
    setEnCours(element.id);
    try {
      const r = await api.post(`/gmail/ignored/${element.id}/recover`);
      onRecupere();
      if (r.imported) {
        notifier(`${element.filename} : ${r.detail}`, 'succes');
        setElements((liste) => liste.filter((x) => x.id !== element.id));
      } else {
        // Non importé (ex. : déjà présent) : la ligne peut disparaître, le message reste visible.
        notifier(`${element.filename} : ${r.detail}`, 'info');
        charger();
      }
    } catch (err) {
      setMessages((m) => ({
        ...m,
        [element.id]: err.statut === 410 ? "Cet email n'est plus dans la boîte (supprimé ou déplacé)." : err.message,
      }));
      if (err.statut === 404) charger();
    } finally {
      setEnCours(null);
    }
  };

  if (!elements) return erreur ? <Alerte>{erreur}</Alerte> : <Chargement />;
  if (elements.length === 0) {
    return (
      <EtatVide icone={Inbox} titre="Aucun email ignoré" compact>
        Les pièces jointes écartées par vos règles (emails automatiques, expéditeurs ignorés, fichiers trop lourds)
        apparaîtront ici. Vous pourrez les récupérer une par une.
      </EtatVide>
    );
  }
  return (
    <>
      <p className="mb-4 text-base text-doux">
        Ces pièces jointes ont été écartées par vos règles. Rien n'est ignoré en silence : vous pouvez les récupérer
        une par une. <Link to="/boite-mail" className="font-medium text-accent-texte hover:underline">Modifier les règles</Link>
      </p>
      <ul className="overflow-hidden rounded-lg border border-trait bg-surface">
        {elements.map((x) => (
          <li key={x.id} className="flex flex-wrap items-center gap-4 border-b border-trait p-4 last:border-b-0">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="truncate font-medium text-fort">{x.filename}</p>
                <Badge ton="alerte">{REGLES_IGNORE[x.rule] || x.rule}</Badge>
              </div>
              <p className="mt-1 truncate text-sm text-doux">
                {x.sender_name ? `${x.sender_name} · ` : ''}{x.sender_email} · {x.subject || 'Sans objet'} · {formaterDateHeure(x.received_at)}
              </p>
              <p className="mt-1 text-sm text-texte">{x.reason}</p>
              {messages[x.id] && <p className="mt-1 text-sm font-medium text-alerte">{messages[x.id]}</p>}
            </div>
            <Bouton
              variante="secondaire"
              icone={RotateCcw}
              geste="reculer"
              onClick={() => recuperer(x)}
              chargement={enCours === x.id}
              disabled={!connecte}
              title={connecte ? undefined : 'Liez une boîte mail pour récupérer cet email'}
            >
              Récupérer quand même
            </Bouton>
          </li>
        ))}
      </ul>
    </>
  );
}
