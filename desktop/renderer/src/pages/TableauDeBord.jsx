import { ArrowRight, Briefcase, FileUp, Plus, Video } from 'lucide-react';
import { m } from 'motion/react';
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api.js';
import { useAgent } from '../agent/ContexteAgent.jsx';
import { PastilleScore } from '../candidatures/elements.jsx';
import { lancerCommande } from '../commandes.js';
import { cascade } from '../components/mouvement.js';
import { Alerte, BadgeStatut, Bouton, Carte, EnTetePage, cx } from '../components/ui.jsx';
import { STATUTS_ENTRETIEN } from '../constantes.js';
import { formaterDateHeure } from '../format.js';
import { FOURNISSEURS } from '../agent/libelles.js';

const ETAPES = [
  { cle: 'classees', libelle: 'Classées', texte: 'Rattachées à un poste', couleur: 'bg-accent', filtre: '' },
  { cle: 'a_verifier', libelle: 'À vérifier', texte: 'Correspondance faible ou postes proches', couleur: 'bg-alerte', filtre: 'a_verifier' },
  { cle: 'non_classees', libelle: 'Non classées', texte: 'Aucun poste actif ne correspond', couleur: 'bg-info', filtre: 'non_classe' },
  { cle: 'illisibles', libelle: 'CV illisibles', texte: 'À ouvrir et lire vous-même', couleur: 'bg-danger', filtre: 'illisible' },
];

export default function TableauDeBord() {
  const navigate = useNavigate();
  const [donnees, setDonnees] = useState(null);
  const [candidatures, setCandidatures] = useState(null);
  const [postes, setPostes] = useState([]);
  const [entretiens, setEntretiens] = useState([]);
  const [erreur, setErreur] = useState('');

  useEffect(() => {
    api.get('/tableau-de-bord').then(setDonnees, (err) => setErreur(err.message));
    api.get('/candidatures?limite=200').then(setCandidatures, () => setCandidatures({ elements: [], compteurs: null }));
    api.get('/postes?statut=actif').then(setPostes, () => {});
    Promise.all([api.get('/entretiens?statut=planifie'), api.get('/entretiens?statut=en_cours')]).then(([p, c]) => setEntretiens([...c, ...p]), () => {});
  }, []);

  if (erreur) return <Alerte>{erreur}</Alerte>;
  if (!donnees) return <SqueletteTableau />;

  const { entreprise_nom: nom, profil_renseigne: profilRenseigne, postes: compteursPostes } = donnees;
  const elements = candidatures?.elements || [];
  const meilleures = elements
    .filter((c) => c.score !== null && c.score !== undefined)
    .sort((a, b) => b.score - a.score)
    .slice(0, 6);
  const noms = Object.fromEntries(elements.map((c) => [c.id, c.nom || c.email || c.nom_fichier_cv]));

  return (
    <>
      <EnTetePage
        titre={nom || 'Tableau de bord'}
        description="Où en sont vos recrutements aujourd'hui."
        actions={
          <>
            <Bouton variante="secondaire" icone={FileUp} geste="soulever" onClick={() => { navigate('/candidatures'); lancerCommande('importer-cv'); }}>
              Importer des CV
            </Bouton>
            <Bouton icone={Plus} geste="pivoter" onClick={() => navigate('/postes/nouveau')}>Nouveau poste</Bouton>
          </>
        }
      />

      {!profilRenseigne && (
        <Alerte
          ton="info"
          className="mb-6"
          titre="Renseignez le profil de votre entreprise."
          action={
            <Link to="/entreprise" className="geste-hote inline-flex shrink-0 items-center gap-1 self-center text-sm font-semibold text-fort hover:underline">
              Compléter le profil <ArrowRight className="size-4" aria-hidden data-geste="avancer" />
            </Link>
          }
        >
          Son nom apparaît ici et sur les rapports des candidats.
        </Alerte>
      )}

      <Flux compteurs={candidatures?.compteurs} />

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <Carte sansMarge>
          <div className="flex items-center justify-between gap-4 px-5 pt-5 pb-3">
            <div>
              <h2 className="titre-section">Meilleures candidatures</h2>
              <p className="text-sm text-doux">Les scores les plus élevés, tous postes confondus.</p>
            </div>
            <Link to="/candidatures" className="geste-hote inline-flex items-center gap-1 text-sm font-medium text-accent-texte hover:underline">
              Toutes <ArrowRight className="size-3.5" aria-hidden data-geste="avancer" />
            </Link>
          </div>
          {candidatures === null ? (
            <ul className="flex flex-col gap-3 px-5 pb-5">
              {[0, 1, 2, 3].map((i) => <li key={i} className="squelette h-11" />)}
            </ul>
          ) : meilleures.length === 0 ? (
            <p className="px-5 pb-6 text-base text-doux">
              Aucun CV noté pour le moment. Les scores apparaissent dès qu'un CV lisible correspond à un poste actif.
            </p>
          ) : (
            <m.ol className="pb-2" initial="initial" animate="animate" variants={cascade.parent}>
              {meilleures.map((c, i) => (
                <m.li key={c.id} variants={cascade.enfant}>
                  <Link
                    to={`/candidatures/${c.id}`}
                    className="group flex items-center gap-4 border-t border-trait px-5 py-2.5 transition-colors hover:bg-survol"
                  >
                    <span className="w-4 text-sm text-tenu tabular-nums">{i + 1}</span>
                    <PastilleScore score={c.score} taille="petite" anime />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-base font-medium text-fort">{c.nom || c.email || c.nom_fichier_cv}</span>
                      <span className="block truncate text-sm text-doux">{c.poste_intitule || 'Aucun poste'}</span>
                    </span>
                    <ArrowRight className="size-4 text-tenu opacity-0 transition-opacity group-hover:opacity-100" aria-hidden />
                  </Link>
                </m.li>
              ))}
            </m.ol>
          )}
        </Carte>

        <div className="flex flex-col gap-6">
          <Carte sansMarge>
            <div className="flex items-center justify-between gap-3 px-5 pt-5 pb-3">
              <h2 className="titre-section">Postes</h2>
              <Link to="/postes" className="text-sm font-medium text-accent-texte hover:underline">Gérer</Link>
            </div>
            <dl className="grid grid-cols-3 border-y border-trait">
              {['actif', 'brouillon', 'cloture'].map((statut, i) => (
                <Link
                  key={statut}
                  to={`/postes?statut=${statut}`}
                  className={cx('flex flex-col gap-1 px-5 py-3 transition-colors hover:bg-survol', i > 0 && 'border-l border-trait')}
                >
                  <dt className="etiquette">{{ actif: 'Actifs', brouillon: 'Brouillons', cloture: 'Clôturés' }[statut]}</dt>
                  <dd className={cx('chiffre text-2xl', statut === 'actif' ? 'text-accent-texte' : 'text-fort')}>{compteursPostes[statut]}</dd>
                </Link>
              ))}
            </dl>
            {postes.length > 0 ? (
              <ul className="py-1">
                {postes.slice(0, 4).map((p) => (
                  <li key={p.id}>
                    <Link to={`/postes/${p.id}`} className="flex items-center gap-3 px-5 py-2 text-base transition-colors hover:bg-survol">
                      <Briefcase className="size-4 shrink-0 text-doux" aria-hidden />
                      <span className="min-w-0 flex-1 truncate text-texte">{p.intitule}</span>
                      <BadgeStatut statut={p.statut} />
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="flex flex-col items-start gap-3 px-5 py-4">
                <p className="text-base text-doux">Aucun poste actif : les CV ne peuvent pas encore être classés.</p>
                <Bouton variante="secondaire" taille="sm" icone={Plus} onClick={() => navigate('/postes/nouveau')}>Créer un poste</Bouton>
              </div>
            )}
          </Carte>

          <Carte sansMarge>
            <div className="flex items-center gap-2 px-5 pt-5 pb-3">
              <Video className="size-4 text-doux" aria-hidden />
              <h2 className="titre-section">Entretiens vidéo</h2>
            </div>
            {entretiens.length === 0 ? (
              <p className="px-5 pb-5 text-base text-doux">Aucun entretien prévu. Invitez un candidat depuis sa fiche.</p>
            ) : (
              <ul className="pb-2">
                {entretiens.slice(0, 5).map((e) => (
                  <li key={e.id}>
                    <Link to={`/entretiens/${e.id}`} className="flex items-center gap-3 border-t border-trait px-5 py-2.5 transition-colors hover:bg-survol">
                      <span className={cx('size-2 shrink-0 rounded-full', e.statut === 'en_cours' ? 'ia-pulsation bg-danger' : 'bg-info')} aria-hidden />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-base font-medium text-fort">{noms[e.candidature_id] || `Candidature ${e.candidature_id}`}</span>
                        <span className="block text-sm text-doux">
                          {STATUTS_ENTRETIEN[e.statut]}
                          {e.date_entretien && ` · ${formaterDateHeure(e.date_entretien)}`}
                        </span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Carte>

        </div>
      </div>
    </>
  );
}

/** Le flux des CV reçus : ce que l'IA en a fait. L'élément fort de l'écran. */
function Flux({ compteurs }) {
  const { statut } = useAgent();
  const total = compteurs?.total ?? statut?.total_cvs ?? 0;

  let boite;
  if (!statut) boite = null;
  else if (!statut.connected) boite = { texte: "Aucune boîte mail liée : l'agent ne récupère pas encore les candidatures.", lien: 'Lier la boîte mail', vers: '/boite-mail' };
  else if (statut.needs_setup) boite = { texte: `La boîte ${statut.account_email || FOURNISSEURS[statut.provider] || 'de démonstration'} est liée : choisissez les candidatures à reprendre.`, lien: 'Terminer la configuration', vers: '/boite-mail' };
  else {
    const qui = statut.account_email || FOURNISSEURS[statut.provider] || 'Boîte de démonstration';
    const surveillance = statut.watching ? `surveillée toutes les ${statut.poll_minutes} min` : 'surveillance en pause';
    boite = { texte: `${qui} · ${surveillance} · dernière vérification : ${formaterDateHeure(statut.last_sync_at)}`, lien: 'Réglages', vers: '/boite-mail' };
  }

  return (
    <Carte sansMarge className="relative overflow-hidden">
      <div className="pointer-events-none absolute -top-24 -right-16 size-72 rounded-full bg-[radial-gradient(closest-side,var(--accent-doux),transparent)]" aria-hidden />
      <div className="relative flex flex-wrap items-end gap-x-10 gap-y-6 px-6 pt-6 pb-5">
        <Link to="/candidatures" className="group flex flex-col gap-2">
          <span className="etiquette">CV reçus</span>
          <span className="chiffre text-4xl text-fort">{total}</span>
        </Link>
        <dl className="grid min-w-0 flex-1 grid-cols-2 gap-x-6 gap-y-4 lg:grid-cols-4">
          {ETAPES.map((e) => (
            <Link key={e.cle} to="/candidatures" state={{ filtre: e.filtre }} className="group flex min-w-0 flex-col gap-1 rounded-md">
              <dt className="flex items-center gap-1.5 text-sm font-medium text-texte">
                <span className={cx('size-2 rounded-full', e.couleur)} aria-hidden />
                {e.libelle}
              </dt>
              <dd className="chiffre text-2xl text-fort transition-colors group-hover:text-accent-texte">{compteurs ? compteurs[e.cle] : '–'}</dd>
              <dd className="text-xs text-doux">{e.texte}</dd>
            </Link>
          ))}
        </dl>
      </div>
      {/* Répartition proportionnelle des CV */}
      <div className="relative mx-6 flex h-1.5 gap-0.5 overflow-hidden rounded-full bg-survol-fort" aria-hidden>
        {compteurs && total > 0 &&
          ETAPES.map((e, i) =>
            compteurs[e.cle] > 0 ? (
              <m.span
                key={e.cle}
                className={cx('h-full origin-left', e.couleur)}
                style={{ flexGrow: compteurs[e.cle], flexBasis: 0 }}
                initial={{ transform: 'scaleX(0)' }}
                animate={{ transform: 'scaleX(1)' }}
                transition={{ duration: 0.5, delay: 0.1 + i * 0.06, ease: [0.23, 1, 0.32, 1] }}
              />
            ) : null,
          )}
      </div>
      {boite && (
        <div className="relative mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-trait px-6 py-3 text-sm">
          <p className="min-w-0 text-doux">{boite.texte}</p>
          <Link to={boite.vers} className="geste-hote inline-flex items-center gap-1 font-medium text-accent-texte hover:underline">
            {boite.lien} <ArrowRight className="size-3.5" aria-hidden data-geste="avancer" />
          </Link>
        </div>
      )}
      {compteurs?.en_attente > 0 && (
        <p className="relative flex items-center gap-2 border-t border-trait px-6 py-2.5 text-sm" role="status">
          <span className="ia-pulsation size-2 rounded-full bg-accent shadow-[0_0_8px_var(--halo)]" aria-hidden />
          <span className="ia-reflet font-medium">L'IA lit {compteurs.en_attente} CV…</span>
        </p>
      )}
    </Carte>
  );
}

function SqueletteTableau() {
  return (
    <div aria-busy="true" aria-label="Chargement du tableau de bord">
      <div className="squelette mb-3 h-8 w-64" />
      <div className="squelette mb-7 h-4 w-80" />
      <div className="squelette h-44 rounded-lg" />
      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="squelette h-72 rounded-lg" />
        <div className="squelette h-72 rounded-lg" />
      </div>
    </div>
  );
}
