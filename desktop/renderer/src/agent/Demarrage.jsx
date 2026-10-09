// Premier réglage après la liaison : « Reprendre les candidatures déjà reçues ? » → aperçu → import.
import { ArrowLeft, Check, Download } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api.js';
import { Alerte, Badge, Bouton, Carte, Chargement, Saisie } from '../components/ui.jsx';
import { formaterDateHeure } from '../format.js';
import { useAgent } from './ContexteAgent.jsx';
import { FOURNISSEURS, ISSUES_APERCU, resumeSynchro } from './libelles.js';

const aujourdhui = () => new Date().toISOString().slice(0, 10);

/** onTermine() : appelé après l'import (assistant de démarrage) ; sinon, on ouvre la liste des candidatures. */
export default function Demarrage({ onTermine }) {
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
      if (onTermine) onTermine();
      else navigate('/candidatures');
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
        <p className="text-sm text-doux">Boîte liée : <strong className="text-fort">{statut.account_email || FOURNISSEURS[statut.provider]}</strong></p>
        <h2 className="titre-section mt-1 text-xl!">Voulez-vous reprendre les candidatures déjà reçues ?</h2>
      </div>
      <Alerte>{erreur}</Alerte>

      {etape === 'choix' ? (
        <>
          <div className="flex flex-col gap-3" role="radiogroup">
            {options.map((o) => (
              <label
                key={o.valeur}
                className={`flex cursor-pointer gap-3 rounded-lg border p-4 transition-colors ${
                  choix === o.valeur ? 'border-accent-trait bg-accent-doux shadow-halo' : 'border-trait hover:border-trait-fort hover:bg-survol'
                }`}
              >
                <input type="radio" name="reprise" checked={choix === o.valeur} onChange={() => setChoix(o.valeur)} className="mt-1 accent-[var(--accent)]" />
                <span className="flex-1">
                  <span className="flex items-center gap-2 font-semibold text-fort">
                    {o.titre}
                    {o.recommande && <Badge ton="accent">Recommandé</Badge>}
                  </span>
                  <span className="mt-0.5 block text-sm text-doux">{o.texte}</span>
                  {o.valeur === 'date' && choix === 'date' && (
                    <Saisie type="date" max={aujourdhui()} value={date} onChange={(e) => setDate(e.target.value)} className="mt-3 w-48" aria-label="Date de départ" />
                  )}
                </span>
              </label>
            ))}
            <button
              type="button"
              onClick={() => setChoix('everything')}
              className={`self-start text-sm ${choix === 'everything' ? 'font-semibold text-accent-texte' : 'text-doux hover:text-fort'}`}
            >
              {choix === 'everything' && <Check className="mr-1 inline size-4" aria-hidden />}
              Tout l'historique de la boîte
            </button>
            {choix === 'everything' && (
              <p className="rounded-md border border-alerte-trait bg-alerte-doux px-4 py-3 text-base text-texte">
                {profil('everything').description}
                {(profil('everything').config.warnings || []).map((w) => <span key={w} className="mt-1 block">{w}</span>)}
              </p>
            )}
          </div>
          <Bouton onClick={voirApercu} chargement={chargement} className="self-end">Voir l'aperçu</Bouton>
        </>
      ) : (
        <Apercu apercu={apercu} nouveauxSeulement={choix === 'new_only'}>
          <label className="flex items-center gap-3 text-sm text-texte">
            <input type="checkbox" checked={surveiller} onChange={(e) => setSurveiller(e.target.checked)} className="size-4 accent-[var(--accent)]" />
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
      <div className="rounded-lg bg-survol p-4">
        <p className="text-lg font-semibold text-fort tabular-nums">
          {apercu.to_import} CV {apercu.to_import > 1 ? 'seront importés' : 'sera importé'}
          <span className="text-base font-normal text-doux">
            {' '}· {apercu.ignored} ignoré{apercu.ignored > 1 ? 's' : ''} · {apercu.already_imported} déjà importé{apercu.already_imported > 1 ? 's' : ''}
          </span>
        </p>
        <p className="mt-1 text-sm text-doux">{apercu.description}</p>
        {nouveauxSeulement && (
          <p className="mt-1 text-sm text-texte">Seuls les emails reçus à partir de maintenant seront importés : l'aperçu est donc vide, c'est normal.</p>
        )}
        <p className="mt-1 text-xs text-doux">Rien n'a encore été téléchargé.</p>
      </div>
      {apercu.samples.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-trait">
          <table className="w-full text-left text-base">
            <thead className="border-b border-trait bg-survol text-sm font-medium text-doux">
              <tr>
                <th className="px-4 py-2">Fichier</th>
                <th className="px-4 py-2">Expéditeur</th>
                <th className="px-4 py-2">Reçu le</th>
                <th className="px-4 py-2">Résultat</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-trait">
              {apercu.samples.map((s, i) => (
                <tr key={i}>
                  <td className="max-w-48 truncate px-4 py-2 font-medium text-fort" title={s.filename}>{s.filename}</td>
                  <td className="max-w-48 truncate px-4 py-2 text-doux">{s.sender_name || s.sender_email}</td>
                  <td className="px-4 py-2 whitespace-nowrap text-doux">{formaterDateHeure(s.received_at)}</td>
                  <td className="px-4 py-2">
                    <span className={s.outcome === 'to_import' ? 'font-medium text-accent-texte' : 'text-doux'}>{ISSUES_APERCU[s.outcome]}</span>
                    {s.reason && <span className="block text-xs text-doux">{s.reason}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {apercu.truncated && <p className="border-t border-trait px-4 py-2 text-sm text-doux">… et d'autres.</p>}
        </div>
      )}
      {children}
    </div>
  );
}
