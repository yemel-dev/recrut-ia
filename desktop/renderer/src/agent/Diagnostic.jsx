// Aide « Pourquoi un email n'apparaît pas ? » : analyse les emails récents sans rien enregistrer.
import { Search } from 'lucide-react';
import { useState } from 'react';
import { api } from '../api.js';
import { Alerte, Bouton, Carte } from '../components/ui.jsx';
import { formaterDateHeure } from '../format.js';

export default function Diagnostic() {
  const [rapport, setRapport] = useState(null);
  const [jours, setJours] = useState(3);
  const [envoi, setEnvoi] = useState(false);
  const [erreur, setErreur] = useState('');

  const analyser = async () => {
    setEnvoi(true);
    setErreur('');
    try {
      setRapport(await api.get(`/gmail/diagnostics?days=${jours}`));
    } catch (err) {
      setErreur(err.message);
    } finally {
      setEnvoi(false);
    }
  };

  const s = rapport?.summary;
  return (
    <Carte className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="font-semibold text-navy-900">Un email n'apparaît pas ?</h2>
          <p className="mt-1 text-sm text-muted">Analysez les emails récents pour savoir s'ils seront récupérés, ou pourquoi ils sont écartés. Rien n'est enregistré.</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={jours}
            onChange={(e) => setJours(Number(e.target.value))}
            className="rounded-lg border border-line bg-white px-3 py-2 text-sm"
            aria-label="Période analysée"
          >
            {[1, 3, 7, 14, 30].map((n) => <option key={n} value={n}>{n} dernier{n > 1 ? 's' : ''} jour{n > 1 ? 's' : ''}</option>)}
          </select>
          <Bouton variante="secondaire" icone={Search} onClick={analyser} chargement={envoi}>Analyser</Bouton>
        </div>
      </div>
      <Alerte>{erreur}</Alerte>
      {rapport && (
        <>
          <p className="rounded-lg bg-mist px-4 py-3 text-sm text-navy-800">
            {s.emails_seen} email{s.emails_seen > 1 ? 's' : ''} analysé{s.emails_seen > 1 ? 's' : ''} · {s.emails_with_a_cv} avec un CV ·{' '}
            {s.to_be_collected} à récupérer · {s.already_collected} déjà récupéré{s.already_collected > 1 ? 's' : ''} · {s.duplicates} doublon{s.duplicates > 1 ? 's' : ''} · {s.rejected} rejeté{s.rejected > 1 ? 's' : ''}
          </p>
          <ul className="flex flex-col divide-y divide-line text-sm">
            {rapport.emails.map((e, i) => (
              <li key={i} className="py-3">
                <p className="font-medium text-navy-900">{e.subject || 'Sans objet'}</p>
                <p className="text-xs text-muted">{e.sender} · {formaterDateHeure(e.received_at)}</p>
                {e.seen_by_agent ? (
                  e.results.map((r, j) => (
                    <p key={j} className="mt-1 text-navy-800">
                      <span className="font-medium">{r.filename}</span> : {r.verdict === 'NOUVEAU' ? 'sera récupéré' : r.verdict} ({r.reason})
                    </p>
                  ))
                ) : (
                  <p className="mt-1 text-muted">Non retenu : {e.reason}</p>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </Carte>
  );
}
