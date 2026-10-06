// Liste des candidatures traitées (une par mail), avec filtres par statut.
import { Inbox, Loader2, Upload } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api.js';
import { Alerte, Bouton, Chargement } from '../components/ui.jsx';
import { formaterDateHeure } from '../format.js';
import { BadgeStatutCandidature, MODES_ASSIGNATION, PastilleScore, formaterExperience } from './elements.jsx';

const PAR_PAGE = 50;
const RAFRAICHISSEMENT_MS = 5000;

const FILTRES = [
  { cle: 'toutes', libelle: 'Toutes', requete: '', compteur: 'total' },
  { cle: 'a_verifier', libelle: 'À vérifier', requete: 'statut=a_verifier', compteur: 'a_verifier' },
  { cle: 'non_classe', libelle: 'Non classées', requete: 'statut=non_classe&lecture=lue', compteur: 'non_classees' },
  { cle: 'illisible', libelle: 'Illisibles', requete: 'lecture=illisible', compteur: 'illisibles' },
];

export default function ListeCandidatures({ version, onImporter, onCompteurs }) {
  const navigate = useNavigate();
  const [filtre, setFiltre] = useState('toutes');
  const [page, setPage] = useState(0);
  const [donnees, setDonnees] = useState(null);
  const [erreur, setErreur] = useState('');

  const charger = useCallback(async () => {
    const f = FILTRES.find((x) => x.cle === filtre);
    try {
      const d = await api.get(`/candidatures?limite=${PAR_PAGE}&decalage=${page * PAR_PAGE}${f.requete ? `&${f.requete}` : ''}`);
      setDonnees(d);
      onCompteurs?.(d.compteurs);
      setErreur('');
    } catch (err) {
      setErreur(err.message);
    }
  }, [filtre, page, onCompteurs]);

  useEffect(() => {
    charger();
  }, [charger, version]);

  // Le traitement tourne en arrière-plan : la liste se met à jour seule (requête locale, peu coûteuse).
  useEffect(() => {
    const minuteur = setInterval(charger, RAFRAICHISSEMENT_MS);
    return () => clearInterval(minuteur);
  }, [charger]);
  const enCours = donnees?.compteurs?.en_attente > 0;

  if (!donnees) return erreur ? <Alerte>{erreur}</Alerte> : <Chargement />;
  const { elements, total, compteurs } = donnees;

  if (compteurs.total === 0) {
    return (
      <div className="flex flex-col items-center rounded-2xl border border-dashed border-navy-100 bg-white px-8 py-14 text-center">
        <span className="mb-4 flex size-14 items-center justify-center rounded-2xl bg-navy-50 text-navy-700">
          <Inbox className="size-7" aria-hidden />
        </span>
        <h2 className="text-lg font-semibold text-navy-900">Aucune candidature pour le moment</h2>
        <p className="mt-2 max-w-md text-sm text-muted">
          Les CV reçus dans la boîte de recrutement apparaîtront ici, lus, notés et classés par poste. Vous pouvez aussi
          glisser des fichiers PDF, DOCX ou ZIP sur cette page.
        </p>
        <Bouton variante="secondaire" icone={Upload} onClick={onImporter} className="mt-6">Importer des CV</Bouton>
      </div>
    );
  }

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {FILTRES.map((f) => (
          <button
            key={f.cle}
            type="button"
            aria-pressed={filtre === f.cle}
            onClick={() => {
              setFiltre(f.cle);
              setPage(0);
            }}
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors ${
              filtre === f.cle ? 'border-navy-900 bg-navy-900 text-white' : 'border-line bg-white text-navy-800 hover:border-navy-200'
            }`}
          >
            {f.libelle}
            <span className={filtre === f.cle ? 'text-navy-100' : 'text-muted'}>{compteurs[f.compteur]}</span>
          </button>
        ))}
        {enCours && (
          <span className="ml-auto inline-flex items-center gap-2 text-sm text-muted">
            <Loader2 className="size-4 animate-spin" aria-hidden /> {compteurs.en_attente} en cours de traitement
          </span>
        )}
      </div>
      {erreur && <div className="mb-3"><Alerte>{erreur}</Alerte></div>}

      {elements.length === 0 ? (
        <p className="rounded-xl border border-dashed border-line bg-white px-6 py-12 text-center text-sm text-muted">Aucune candidature dans cette catégorie.</p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-line bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-mist text-xs font-semibold tracking-wide text-muted uppercase">
              <tr>
                <th className="px-4 py-3">Candidat</th>
                <th className="px-4 py-3">Poste</th>
                <th className="px-4 py-3 text-center">Score</th>
                <th className="px-4 py-3">Profil</th>
                <th className="px-4 py-3">Reçue le</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {elements.map((c) => (
                <tr key={c.id} onClick={() => navigate(`/candidatures/${c.id}`)} className="cursor-pointer hover:bg-mist/60">
                  <td className="max-w-56 px-4 py-3">
                    <p className="truncate font-medium text-navy-900">{c.nom || c.email || c.nom_fichier_cv}</p>
                    <p className="truncate text-xs text-muted">{c.email || c.nom_fichier_cv}</p>
                  </td>
                  <td className="max-w-60 px-4 py-3">
                    <div className="flex flex-col items-start gap-1">
                      {c.poste_intitule && <span className="truncate font-medium text-navy-900">{c.poste_intitule}</span>}
                      <BadgeStatutCandidature candidature={c} />
                      {c.mode_assignation && c.statut_lecture === 'lue' && (
                        <span className="text-xs text-muted">{MODES_ASSIGNATION[c.mode_assignation]}</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-center"><PastilleScore score={c.score} /></td>
                  <td className="px-4 py-3 text-xs text-muted">
                    {c.statut_lecture === 'lue' ? (
                      <>
                        <p>{c.diplome_niveau || 'Diplôme non trouvé'}</p>
                        <p>{formaterExperience(c.experience_mois)} d'expérience</p>
                      </>
                    ) : (
                      c.motif_lecture || '—'
                    )}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-muted">{formaterDateHeure(c.recue_le)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {total > PAR_PAGE && (
        <div className="mt-4 flex items-center justify-between text-sm text-muted">
          <Bouton variante="secondaire" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Précédent</Bouton>
          Page {page + 1} sur {Math.ceil(total / PAR_PAGE)}
          <Bouton variante="secondaire" disabled={(page + 1) * PAR_PAGE >= total} onClick={() => setPage((p) => p + 1)}>Suivant</Bouton>
        </div>
      )}
    </>
  );
}
