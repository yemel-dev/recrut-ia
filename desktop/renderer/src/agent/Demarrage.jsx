// Premier réglage après la liaison : « Reprendre les candidatures déjà reçues ? » → aperçu → import.
import { ArrowLeft, Check, Download } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api.js';
import { Alerte, Bouton, Carte, Chargement, Saisie } from '../components/ui.jsx';
import { formaterDateHeure } from '../format.js';
import { useAgent } from './ContexteAgent.jsx';
import { FOURNISSEURS, ISSUES_APERCU, resumeSynchro } from './libelles.js';

const aujourdhui = () => new Date().toISOString().slice(0, 10);

export default function Demarrage() {
  const navigate = useNavigate();
  const { statut, rafraichir, notifier, signalerNouveauxCV } = useAgent();
  const [profils, setProfils] = useState(null);
  const [choix, setChoix] = useState('prudent'); // nom de profil, ou « date »
  const [date, setDate] = useState('');
  const [apercu, setApercu] = useState(null);
  const [etape, setEtape] = useState('choix'); // choix → apercu → import
  const [surveiller, setSurveiller] = useState(true);
  const [chargement, setChargement] = useState(false);
  const [erreur, setErreur] = useState('');

  useEffect(() => {
    api.get('/gmail/profiles').then(setProfils, (err) => setErreur(err.message));
  }, []);

  const profil = (nom) => profils?.find((p) => p.name === nom);
  const reglage = () =>
    choix === 'date' ? { ...profil('prudent').config, mode: 'since_date', since_date: date } : profil(choix).config;

  const voirApercu = async () => {
    if (choix === 'date' && !date) {
      setErreur('Choisissez une date de départ.');
      return;
    }
    setErreur('');
    setChargement(true);
    try {
      setApercu(await api.post('/gmail/preview', reglage()));
      setEtape('apercu');
    } catch (err) {
      setErreur(err.champs?.requete || err.message);
    } finally {
      setChargement(false);
    }
  };

  const importer = async () => {
    setErreur('');
    setEtape('import');
    try {
      if (choix === 'date') await api.put('/gmail/config', reglage());
      else await api.put(`/gmail/config/profile/${choix}`);
      const resultat = await api.post('/gmail/sync');
      if (surveiller) await api.put('/agent/surveillance', { active: true });
      notifier(`Import terminé : ${resumeSynchro(resultat)}.`, 'succes');
      signalerNouveauxCV();
      await rafraichir();
      navigate('/candidatures');
    } catch (err) {
      setErreur(err.message);
      setEtape('apercu');
      rafraichir();
    }
  };

  if (!profils) return erreur ? <Alerte>{erreur}</Alerte> : <Chargement />;

  if (etape === 'import') {
    return (
      <Carte>
        <Chargement texte="Import des candidatures en cours… Cela peut prendre quelques minutes selon le nombre d'emails." />
      </Carte>
    );
  }

  const options = [
    { valeur: 'prudent', titre: 'Les 30 derniers jours', texte: profil('prudent').description, recommande: true },
    { valeur: 'date', titre: "À partir d'une date…", texte: 'Reprend les candidatures reçues depuis la date de votre choix.' },
    { valeur: 'new_only', titre: 'Seulement les nouveaux emails', texte: profil('new_only').description },
  ];

  return (
    <Carte className="flex flex-col gap-6">
      <div>
        <p className="text-sm text-muted">Boîte liée : <strong className="text-navy-900">{statut.account_email || FOURNISSEURS[statut.provider]}</strong></p>
        <h2 className="mt-1 text-xl font-bold text-navy-900">Voulez-vous reprendre les candidatures déjà reçues ?</h2>
      </div>
      <Alerte>{erreur}</Alerte>

      {etape === 'choix' ? (
        <>
          <div className="flex flex-col gap-3" role="radiogroup">
            {options.map((o) => (
              <label
                key={o.valeur}
                className={`flex cursor-pointer gap-3 rounded-xl border p-4 transition-colors ${
                  choix === o.valeur ? 'border-brand-500 bg-brand-50' : 'border-line hover:border-navy-200'
                }`}
              >
                <input type="radio" name="reprise" checked={choix === o.valeur} onChange={() => setChoix(o.valeur)} className="mt-1 accent-brand-600" />
                <span className="flex-1">
                  <span className="flex items-center gap-2 font-semibold text-navy-900">
                    {o.titre}
                    {o.recommande && <span className="rounded-full bg-brand-100 px-2 py-0.5 text-xs text-brand-700">Recommandé</span>}
                  </span>
                  <span className="mt-0.5 block text-sm text-muted">{o.texte}</span>
                  {o.valeur === 'date' && choix === 'date' && (
                    <Saisie type="date" max={aujourdhui()} value={date} onChange={(e) => setDate(e.target.value)} className="mt-3 w-48" aria-label="Date de départ" />
                  )}
                </span>
              </label>
            ))}
            <button
              type="button"
              onClick={() => setChoix('everything')}
              className={`self-start text-sm ${choix === 'everything' ? 'font-semibold text-brand-700' : 'text-muted hover:text-navy-900'}`}
            >
              {choix === 'everything' && <Check className="mr-1 inline size-4" aria-hidden />}
              Tout l'historique de la boîte
            </button>
            {choix === 'everything' && (
              <p className="rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-900">
                {profil('everything').description}
                {(profil('everything').config.warnings || []).map((w) => <span key={w} className="mt-1 block">{w}</span>)}
              </p>
            )}
          </div>
          <Bouton onClick={voirApercu} chargement={chargement} className="self-end">Voir l'aperçu</Bouton>
        </>
      ) : (
        <Apercu apercu={apercu} nouveauxSeulement={choix === 'new_only'}>
          <label className="flex items-center gap-3 text-sm text-navy-800">
            <input type="checkbox" checked={surveiller} onChange={(e) => setSurveiller(e.target.checked)} className="size-4 accent-brand-600" />
            Surveiller ensuite la boîte automatiquement (vérification toutes les {statut.poll_minutes} minutes)
          </label>
          <div className="flex justify-between gap-2">
            <Bouton variante="secondaire" icone={ArrowLeft} onClick={() => setEtape('choix')}>Modifier le choix</Bouton>
            <Bouton icone={Download} onClick={importer}>Importer</Bouton>
          </div>
        </Apercu>
      )}
    </Carte>
  );
}

function Apercu({ apercu, nouveauxSeulement, children }) {
  return (
    <div className="flex flex-col gap-5">
      <div className="rounded-xl bg-mist p-4">
        <p className="text-lg font-semibold text-navy-900">
          {apercu.to_import} CV {apercu.to_import > 1 ? 'seront importés' : 'sera importé'}
          <span className="text-base font-normal text-muted">
            {' '}· {apercu.ignored} ignoré{apercu.ignored > 1 ? 's' : ''} · {apercu.already_imported} déjà importé{apercu.already_imported > 1 ? 's' : ''}
          </span>
        </p>
        <p className="mt-1 text-sm text-muted">{apercu.description}</p>
        {nouveauxSeulement && (
          <p className="mt-1 text-sm text-navy-800">Seuls les emails reçus à partir de maintenant seront importés : l'aperçu est donc vide, c'est normal.</p>
        )}
        <p className="mt-1 text-xs text-muted">Rien n'a encore été téléchargé.</p>
      </div>
      {apercu.samples.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-line">
          <table className="w-full text-left text-sm">
            <thead className="bg-mist text-xs font-semibold tracking-wide text-muted uppercase">
              <tr>
                <th className="px-4 py-2">Fichier</th>
                <th className="px-4 py-2">Expéditeur</th>
                <th className="px-4 py-2">Reçu le</th>
                <th className="px-4 py-2">Résultat</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {apercu.samples.map((s, i) => (
                <tr key={i}>
                  <td className="max-w-48 truncate px-4 py-2 font-medium text-navy-900" title={s.filename}>{s.filename}</td>
                  <td className="max-w-48 truncate px-4 py-2 text-muted">{s.sender_name || s.sender_email}</td>
                  <td className="px-4 py-2 whitespace-nowrap text-muted">{formaterDateHeure(s.received_at)}</td>
                  <td className="px-4 py-2">
                    <span className={s.outcome === 'to_import' ? 'font-medium text-brand-700' : 'text-muted'}>{ISSUES_APERCU[s.outcome]}</span>
                    {s.reason && <span className="block text-xs text-muted">{s.reason}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {apercu.truncated && <p className="border-t border-line px-4 py-2 text-sm text-muted">… et d'autres.</p>}
        </div>
      )}
      {children}
    </div>
  );
}
