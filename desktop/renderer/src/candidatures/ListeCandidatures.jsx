// Liste des candidatures traitées (une par mail), avec filtres par statut.
// Lignes : clic ou Entrée pour ouvrir la fiche ; clic droit ou Maj+F10 pour le menu (fiche, CV, copier l'email).
import { ChevronLeft, ChevronRight, Copy, ExternalLink, FileText, FileUp, Inbox, SearchX } from 'lucide-react';
import { m } from 'motion/react';
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api.js';
import { useAgent } from '../agent/ContexteAgent.jsx';
import EtatVide from '../components/EtatVide.jsx';
import { useMenuContextuel } from '../components/Menu.jsx';
import { delaiCascade, COURBE_SORTIE } from '../components/mouvement.js';
import { Alerte, Bouton, Segments, cx } from '../components/ui.jsx';
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

/** Initiales sur une pastille de teinte stable (repère visuel pour parcourir la liste). */
const TEINTES = ['#2ed384', '#7fb0ff', '#f5b94a', '#c49bff', '#ff9b8a', '#5fd4d4'];
function Initiales({ nom }) {
  const mots = (nom || '?').replace(/[^\p{L}\s-]/gu, ' ').trim().split(/\s+/);
  const initiales = ((mots[0]?.[0] || '?') + (mots.length > 1 ? mots[mots.length - 1][0] : '')).toUpperCase();
  const teinte = TEINTES[[...(nom || '')].reduce((s, c) => s + c.charCodeAt(0), 0) % TEINTES.length];
  return (
    <span
      className="grid size-8 shrink-0 place-items-center rounded-full font-affichage text-[11px] font-semibold"
      style={{ color: `color-mix(in oklab, ${teinte} 62%, var(--texte-fort))`, backgroundColor: `color-mix(in oklab, ${teinte} 14%, transparent)`, boxShadow: `inset 0 0 0 1px color-mix(in oklab, ${teinte} 30%, transparent)` }}
      aria-hidden
    >
      {initiales}
    </span>
  );
}

export default function ListeCandidatures({ version, onImporter, onCompteurs, filtreInitial }) {
  const navigate = useNavigate();
  const { notifier } = useAgent();
  const { ouvrir: ouvrirMenu, menu } = useMenuContextuel('Actions sur la candidature');
  const [filtre, setFiltre] = useState(() => (FILTRES.some((f) => f.cle === filtreInitial) ? filtreInitial : 'toutes'));
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

  const ouvrirCV = async (c) => {
    const message = await window.injara.fichiers.ouvrirCV(c.id);
    if (message) notifier(message, 'erreur');
  };

  const actions = (c) => {
    const liste = [
      { libelle: 'Ouvrir la fiche', icone: FileText, action: () => navigate(`/candidatures/${c.id}`), raccourci: 'Entrée' },
      { libelle: 'Ouvrir le CV', icone: ExternalLink, action: () => ouvrirCV(c), geste: 'decoller' },
    ];
    if (c.email) {
      liste.push(null, {
        libelle: "Copier l'email",
        icone: Copy,
        action: () => navigator.clipboard.writeText(c.email).then(() => notifier('Email copié.', 'succes'), () => notifier("La copie de l'email a échoué.", 'erreur')),
      });
    }
    return liste;
  };

  if (!donnees) return erreur ? <Alerte>{erreur}</Alerte> : <SqueletteListe />;
  const { elements, total, compteurs } = donnees;

  if (compteurs.total === 0) {
    return (
      <EtatVide
        icone={Inbox}
        titre="Aucune candidature pour le moment"
        action={<Bouton variante="secondaire" icone={FileUp} geste="soulever" onClick={onImporter}>Importer des CV</Bouton>}
      >
        Les CV reçus dans la boîte de recrutement apparaîtront ici, lus, notés et classés par poste. Vous pouvez aussi
        glisser des fichiers PDF, DOCX ou ZIP sur cette page.
      </EtatVide>
    );
  }

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Segments
          libelle="Filtrer les candidatures"
          valeur={filtre}
          onChange={(v) => {
            setFiltre(v);
            setPage(0);
          }}
          options={FILTRES.map((f) => ({ valeur: f.cle, libelle: f.libelle, compteur: compteurs[f.compteur] }))}
        />
        {enCours && (
          <span className="ml-auto inline-flex items-center gap-2 text-sm" role="status">
            <span className="ia-pulsation size-2 rounded-full bg-accent shadow-[0_0_8px_var(--halo)]" aria-hidden />
            <span className="ia-reflet font-medium">L'IA lit {compteurs.en_attente} CV…</span>
          </span>
        )}
      </div>
      {erreur && <Alerte className="mb-3">{erreur}</Alerte>}

      {elements.length === 0 ? (
        <EtatVide icone={SearchX} titre="Aucune candidature dans cette catégorie" compact>
          Choisissez un autre filtre pour voir les autres candidatures.
        </EtatVide>
      ) : (
        <div className="overflow-hidden rounded-lg border border-trait bg-surface shadow-carte">
          <table className="w-full text-left text-base">
            <thead className="border-b border-trait bg-survol text-sm text-doux">
              <tr>
                <th scope="col" className="py-2.5 pr-4 pl-5 font-medium">Candidat</th>
                <th scope="col" className="px-4 py-2.5 font-medium">Poste</th>
                <th scope="col" className="px-4 py-2.5 text-center font-medium">Score</th>
                <th scope="col" className="px-4 py-2.5 font-medium">Profil</th>
                <th scope="col" className="py-2.5 pr-5 pl-4 font-medium">Reçue le</th>
              </tr>
            </thead>
            <tbody>
              {elements.map((c, i) => {
                const nom = c.nom || c.email || c.nom_fichier_cv;
                return (
                  <m.tr
                    key={c.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.2, delay: delaiCascade(i), ease: COURBE_SORTIE }}
                    tabIndex={0}
                    aria-label={`${nom}, ouvrir la fiche`}
                    onClick={() => navigate(`/candidatures/${c.id}`)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') navigate(`/candidatures/${c.id}`);
                      else if (e.key === 'F10' && e.shiftKey) {
                        e.preventDefault();
                        ouvrirMenu({ preventDefault() {}, clientX: 0, clientY: 0, currentTarget: e.currentTarget }, actions(c));
                      }
                    }}
                    onContextMenu={(e) => ouvrirMenu(e, actions(c))}
                    className={cx(
                      'group border-b border-trait last:border-b-0 transition-colors hover:bg-survol focus-visible:bg-survol-fort focus-visible:outline-none',
                      'focus-visible:shadow-[inset_3px_0_0_var(--accent)]',
                    )}
                  >
                    <td className="max-w-64 py-2.5 pr-4 pl-5">
                      <div className="flex items-center gap-3">
                        <Initiales nom={nom} />
                        <div className="min-w-0">
                          <p className="truncate font-medium text-fort">{nom}</p>
                          <p className="truncate text-sm text-doux">{c.email || c.nom_fichier_cv}</p>
                        </div>
                      </div>
                    </td>
                    <td className="max-w-64 px-4 py-2.5">
                      <div className="flex flex-col items-start gap-1">
                        {c.poste_intitule && <span className="max-w-full truncate font-medium text-texte">{c.poste_intitule}</span>}
                        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                          <BadgeStatutCandidature candidature={c} />
                          {c.mode_assignation && c.statut_lecture === 'lue' && (
                            <span className="text-xs text-doux">{MODES_ASSIGNATION[c.mode_assignation]}</span>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-2.5 text-center">
                      <span className="inline-flex"><PastilleScore score={c.score} taille="petite" /></span>
                    </td>
                    <td className="px-4 py-2.5 text-sm text-doux">
                      {c.statut_lecture === 'lue' ? (
                        <>
                          <p className="text-texte">{c.diplome_niveau || 'Diplôme non trouvé'}</p>
                          <p className="tabular-nums">{formaterExperience(c.experience_mois)} d'expérience</p>
                        </>
                      ) : (
                        <p className="line-clamp-2 max-w-56">{c.motif_lecture || '—'}</p>
                      )}
                    </td>
                    <td className="py-2.5 pr-5 pl-4 text-sm whitespace-nowrap text-doux tabular-nums">{formaterDateHeure(c.recue_le)}</td>
                  </m.tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {total > PAR_PAGE && (
        <nav className="mt-4 flex items-center justify-between text-sm text-doux" aria-label="Pages">
          <Bouton variante="secondaire" taille="sm" icone={ChevronLeft} geste="reculer" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Précédent</Bouton>
          <span className="tabular-nums">Page {page + 1} sur {Math.ceil(total / PAR_PAGE)}</span>
          <Bouton variante="secondaire" taille="sm" disabled={(page + 1) * PAR_PAGE >= total} onClick={() => setPage((p) => p + 1)} className="flex-row-reverse">
            <ChevronRight className="size-4" aria-hidden data-geste="avancer" /> Suivant
          </Bouton>
        </nav>
      )}
      <p className="mt-3 text-xs text-tenu">Astuce : clic droit sur une ligne pour ouvrir le CV ou copier l'email.</p>
      {menu}
    </>
  );
}

function SqueletteListe() {
  return (
    <div aria-busy="true" aria-label="Chargement des candidatures">
      <div className="squelette mb-4 h-8 w-96 rounded-md" />
      <div className="overflow-hidden rounded-lg border border-trait">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="flex items-center gap-4 border-b border-trait px-5 py-3 last:border-b-0">
            <div className="squelette size-8 rounded-full" />
            <div className="flex-1"><div className="squelette mb-1.5 h-3.5 w-48" /><div className="squelette h-3 w-32" /></div>
            <div className="squelette h-3.5 w-40" />
            <div className="squelette size-9 rounded-full" />
            <div className="squelette h-3.5 w-28" />
          </div>
        ))}
      </div>
    </div>
  );
}
