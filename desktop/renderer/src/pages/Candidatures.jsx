import { ExternalLink, FileText, Inbox, Mail, RefreshCw, RotateCcw, Upload, X } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api.js';
import { useAgent } from '../agent/ContexteAgent.jsx';
import { FOURNISSEURS, REGLES_IGNORE, resumeSynchro } from '../agent/libelles.js';
import { Alerte, Bouton, Carte, Chargement, EnTetePage, Interrupteur, Onglets } from '../components/ui.jsx';
import { formaterDateHeure, formaterTaille } from '../format.js';

const PAR_PAGE = 50;

export default function Candidatures() {
  const { statut, etat, rafraichir, notifier, version, signalerNouveauxCV } = useAgent();
  const [onglet, setOnglet] = useState('cv');
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
      {surDepot && (
        <div className="pointer-events-none absolute -inset-4 z-10 flex items-center justify-center rounded-2xl border-2 border-dashed border-brand-500 bg-brand-50/90">
          <p className="flex items-center gap-2 text-lg font-semibold text-brand-700">
            <Upload className="size-5" aria-hidden /> Déposez vos CV ici (PDF, DOCX ou ZIP)
          </p>
        </div>
      )}

      <EnTetePage
        titre="Candidatures"
        description="Les CV reçus dans la boîte mail de recrutement, et ceux que vous importez vous-même."
        actions={
          <>
            <Bouton variante="secondaire" icone={Upload} onClick={choisirFichiers} chargement={importEnCours}>Importer des CV</Bouton>
            {connecte && !statut.needs_setup && (
              <Bouton icone={RefreshCw} onClick={verifier} chargement={verification}>Vérifier maintenant</Bouton>
            )}
          </>
        }
      />

      <BarreEtat statut={statut} etat={etat} onSurveillance={basculerSurveillance} />

      {erreur && <div className="mb-4"><Alerte>{erreur}</Alerte></div>}
      {resultat && <Resultat resultat={resultat} onFermer={() => setResultat(null)} />}

      <Onglets
        valeur={onglet}
        onChange={setOnglet}
        onglets={[
          { valeur: 'cv', libelle: 'CV reçus', compteur: statut.total_cvs },
          { valeur: 'ignores', libelle: 'Ignorés', compteur: statut.ignored_count },
        ]}
      />
      {onglet === 'cv' ? (
        <ListeCV version={version} onImporter={choisirFichiers} />
      ) : (
        <ListeIgnores connecte={connecte} onRecupere={() => { signalerNouveauxCV(); rafraichir(); }} />
      )}
    </div>
  );
}

function BarreEtat({ statut, etat, onSurveillance }) {
  if (!statut.connected) {
    return (
      <Carte className="mb-6 flex flex-wrap items-center justify-between gap-4 py-4">
        <div className="flex items-center gap-3">
          <Mail className="size-5 text-muted" aria-hidden />
          <p className="text-sm text-navy-800">
            Aucune boîte mail n'est liée. Liez la boîte de recrutement pour récupérer les CV automatiquement ; l'import
            manuel fonctionne déjà.
          </p>
        </div>
        <Link to="/boite-mail" className="text-sm font-semibold text-brand-700 hover:underline">Lier une boîte mail</Link>
      </Carte>
    );
  }
  if (statut.needs_setup) {
    return (
      <Carte className="mb-6 flex flex-wrap items-center justify-between gap-4 border-brand-100 bg-brand-50 py-4">
        <p className="text-sm text-navy-800">
          La boîte <strong>{statut.account_email}</strong> est liée. Choisissez maintenant les candidatures à reprendre.
        </p>
        <Link to="/boite-mail" className="text-sm font-semibold text-brand-700 hover:underline">Terminer la configuration</Link>
      </Carte>
    );
  }
  return (
    <Carte className="mb-6 flex flex-wrap items-center justify-between gap-x-8 gap-y-3 py-4">
      <div className="text-sm">
        <p className="font-semibold text-navy-900">{statut.account_email || FOURNISSEURS[statut.provider]}</p>
        <p className="text-muted">
          {statut.account_email && `${FOURNISSEURS[statut.provider]} · `}Dernière vérification : {formaterDateHeure(statut.last_sync_at)}
        </p>
      </div>
      <div className="flex flex-col items-end gap-1">
        <Interrupteur
          actif={statut.watching}
          onChange={onSurveillance}
          libelle={`Surveillance automatique${statut.watching ? ` (toutes les ${statut.poll_minutes} min)` : ''}`}
        />
        {etat?.surveillance_souhaitee && !statut.watching && (
          <p className="text-xs text-muted">Reprise en cours…</p>
        )}
      </div>
    </Carte>
  );
}

function Resultat({ resultat, onFermer }) {
  const { titre, resume, details = [], erreurs = [], tronque } = resultat;
  return (
    <Carte className="mb-6 py-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold tracking-wide text-muted uppercase">{titre}</p>
          <p className="mt-1 font-semibold text-navy-900">{resume}</p>
        </div>
        <button type="button" onClick={onFermer} className="text-muted hover:text-navy-900" aria-label="Fermer le résultat">
          <X className="size-4" />
        </button>
      </div>
      {tronque && (
        <p className="mt-2 text-sm text-amber-800">Il reste des emails à traiter. Cliquez de nouveau sur « Vérifier maintenant ».</p>
      )}
      {erreurs.length > 0 && (
        <div className="mt-3"><Alerte>{erreurs.map((e) => <p key={e}>{e}</p>)}</Alerte></div>
      )}
      {details.length > 0 && (
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer font-medium text-navy-700">Fichiers écartés ({details.length})</summary>
          <ul className="mt-2 flex flex-col gap-1">
            {details.map((d, i) => (
              <li key={i} className="text-muted"><span className="font-medium text-navy-800">{d.fichier}</span> : {d.raison}</li>
            ))}
          </ul>
        </details>
      )}
    </Carte>
  );
}

function ListeCV({ version, onImporter }) {
  const [page, setPage] = useState(0);
  const [cvs, setCvs] = useState(null);
  const [erreur, setErreur] = useState('');

  useEffect(() => {
    api.get(`/gmail/cvs?limit=${PAR_PAGE + 1}&offset=${page * PAR_PAGE}`).then(setCvs, (err) => setErreur(err.message));
  }, [page, version]);

  const ouvrir = async (cv) => {
    const message = await window.injara.fichiers.ouvrirCV(cv.saved_path);
    setErreur(message);
  };

  if (!cvs) return erreur ? <Alerte>{erreur}</Alerte> : <Chargement />;
  if (cvs.length === 0 && page === 0) {
    return (
      <div className="flex flex-col items-center rounded-2xl border border-dashed border-navy-100 bg-white px-8 py-14 text-center">
        <span className="mb-4 flex size-14 items-center justify-center rounded-2xl bg-navy-50 text-navy-700">
          <Inbox className="size-7" aria-hidden />
        </span>
        <h2 className="text-lg font-semibold text-navy-900">Aucun CV pour le moment</h2>
        <p className="mt-2 max-w-md text-sm text-muted">
          Les CV reçus en pièce jointe dans la boîte de recrutement apparaîtront ici. Vous pouvez aussi glisser des
          fichiers PDF, DOCX ou ZIP sur cette page.
        </p>
        <Bouton variante="secondaire" icone={Upload} onClick={onImporter} className="mt-6">Importer des CV</Bouton>
      </div>
    );
  }

  const visibles = cvs.slice(0, PAR_PAGE);
  return (
    <>
      {erreur && <div className="mb-3"><Alerte>{erreur}</Alerte></div>}
      <div className="overflow-hidden rounded-xl border border-line bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-mist text-xs font-semibold tracking-wide text-muted uppercase">
            <tr>
              <th className="px-4 py-3">Fichier</th>
              <th className="px-4 py-3">Candidat</th>
              <th className="px-4 py-3">Objet</th>
              <th className="px-4 py-3">Reçu le</th>
              <th className="px-4 py-3"><span className="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {visibles.map((cv) => (
              <tr key={`${cv.message_id}-${cv.attachment_id}`} className="hover:bg-mist/60">
                <td className="max-w-56 px-4 py-3">
                  <p className="flex items-center gap-2 truncate font-medium text-navy-900" title={cv.filename}>
                    <FileText className="size-4 shrink-0 text-muted" aria-hidden /> {cv.filename}
                  </p>
                  <p className="pl-6 text-xs text-muted">{formaterTaille(cv.size_bytes)}</p>
                </td>
                <td className="max-w-48 px-4 py-3">
                  {cv.source === 'upload' ? (
                    <span className="rounded-full bg-navy-50 px-2 py-0.5 text-xs font-medium text-navy-700">Import manuel</span>
                  ) : (
                    <>
                      <p className="truncate text-navy-900">{cv.sender_name || cv.sender_email}</p>
                      <p className="truncate text-xs text-muted">{cv.sender_email}</p>
                    </>
                  )}
                </td>
                <td className="max-w-56 truncate px-4 py-3 text-muted" title={cv.subject}>{cv.source === 'upload' ? '—' : cv.subject || '—'}</td>
                <td className="px-4 py-3 whitespace-nowrap text-muted">{formaterDateHeure(cv.received_at)}</td>
                <td className="px-4 py-3 text-right">
                  <Bouton variante="discret" icone={ExternalLink} onClick={() => ouvrir(cv)} aria-label={`Ouvrir ${cv.filename}`}>Ouvrir</Bouton>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {(page > 0 || cvs.length > PAR_PAGE) && (
        <div className="mt-4 flex items-center justify-between text-sm text-muted">
          <Bouton variante="secondaire" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Précédent</Bouton>
          Page {page + 1}
          <Bouton variante="secondaire" disabled={cvs.length <= PAR_PAGE} onClick={() => setPage((p) => p + 1)}>Suivant</Bouton>
        </div>
      )}
    </>
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
    return <p className="rounded-xl border border-dashed border-line bg-white px-6 py-12 text-center text-sm text-muted">Aucun email n'a été ignoré.</p>;
  }
  return (
    <>
      <p className="mb-3 text-sm text-muted">
        Ces pièces jointes ont été écartées par vos règles. Rien n'est ignoré en silence : vous pouvez les récupérer
        une par une. <Link to="/boite-mail" className="font-medium text-brand-700 hover:underline">Modifier les règles</Link>
      </p>
      <ul className="flex flex-col gap-2">
        {elements.map((x) => (
          <li key={x.id} className="flex flex-wrap items-center gap-4 rounded-xl border border-line bg-white p-4">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="truncate font-medium text-navy-900">{x.filename}</p>
                <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800 ring-1 ring-amber-200">
                  {REGLES_IGNORE[x.rule] || x.rule}
                </span>
              </div>
              <p className="mt-1 truncate text-sm text-muted">
                {x.sender_name ? `${x.sender_name} · ` : ''}{x.sender_email} · {x.subject || 'Sans objet'} · {formaterDateHeure(x.received_at)}
              </p>
              <p className="mt-1 text-sm text-navy-700">{x.reason}</p>
              {messages[x.id] && <p className="mt-1 text-sm font-medium text-navy-900">{messages[x.id]}</p>}
            </div>
            <Bouton
              variante="secondaire"
              icone={RotateCcw}
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
