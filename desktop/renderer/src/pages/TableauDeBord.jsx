import { ArrowRight, Briefcase, Building2, FileText, Mail, Plus } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api.js';
import { useAgent } from '../agent/ContexteAgent.jsx';
import { formaterDateHeure } from '../format.js';
import { Alerte, Carte, Chargement, EnTetePage } from '../components/ui.jsx';

const LIBELLES = { actif: 'Postes actifs', brouillon: 'Brouillons', cloture: 'Postes clôturés' };

const DESCRIPTIONS = {
  actif: 'Utilisés pour classer les candidatures',
  brouillon: 'En préparation, pas encore utilisés',
  cloture: 'Recrutement terminé',
};

export default function TableauDeBord() {
  const [donnees, setDonnees] = useState(null);
  const [erreur, setErreur] = useState('');

  useEffect(() => {
    api.get('/tableau-de-bord').then(setDonnees, (err) => setErreur(err.message));
  }, []);

  if (erreur) return <Alerte>{erreur}</Alerte>;
  if (!donnees) return <Chargement />;

  const { entreprise_nom: nom, profil_renseigne: profilRenseigne, postes } = donnees;

  return (
    <>
      <EnTetePage titre={nom || 'Tableau de bord'} description="Vue d'ensemble de vos recrutements." />

      {!profilRenseigne && (
        <Carte className="mb-6 flex items-center justify-between gap-4 border-brand-100 bg-brand-50">
          <div className="flex items-center gap-3">
            <Building2 className="size-5 text-brand-700" aria-hidden />
            <p className="text-sm text-navy-800">Commencez par renseigner le profil de votre entreprise.</p>
          </div>
          <Link to="/entreprise" className="inline-flex items-center gap-1 text-sm font-semibold text-brand-700 hover:underline">
            Compléter le profil <ArrowRight className="size-4" aria-hidden />
          </Link>
        </Carte>
      )}

      <CarteCandidatures />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {['actif', 'brouillon', 'cloture'].map((statut) => (
          <Link
            key={statut}
            to={`/postes?statut=${statut}`}
            className="rounded-xl border border-line bg-white p-5 transition-colors hover:border-navy-200"
          >
            <p className="text-sm font-medium text-muted">{LIBELLES[statut]}</p>
            <p className={`mt-2 text-3xl font-bold ${statut === 'actif' ? 'text-brand-700' : 'text-navy-900'}`}>{postes[statut]}</p>
            <p className="mt-1 text-xs text-muted">{DESCRIPTIONS[statut]}</p>
          </Link>
        ))}
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <AccesRapide vers="/postes" icone={Briefcase} titre="Postes" texte={`${postes.total} poste${postes.total > 1 ? 's' : ''} au total`} />
        {postes.total === 0 ? (
          <AccesRapide vers="/postes/nouveau" icone={Plus} titre="Créer un premier poste" texte="Décrivez le profil que vous recherchez" />
        ) : (
          <AccesRapide vers="/entreprise" icone={Building2} titre="Profil entreprise" texte="Coordonnées et présentation" />
        )}
      </div>
    </>
  );
}

function AccesRapide({ vers, icone: Icone, titre, texte }) {
  return (
    <Link to={vers} className="group flex items-center gap-4 rounded-xl border border-line bg-white p-5 transition-colors hover:border-navy-200">
      <span className="flex size-10 items-center justify-center rounded-lg bg-navy-50 text-navy-700">
        <Icone className="size-5" aria-hidden />
      </span>
      <span className="flex-1">
        <span className="block font-semibold text-navy-900">{titre}</span>
        <span className="block text-sm text-muted">{texte}</span>
      </span>
      <ArrowRight className="size-4 text-muted transition-transform group-hover:translate-x-0.5" aria-hidden />
    </Link>
  );
}

/** Résumé de l'agent mail : CV reçus, boîte liée, surveillance. */
function CarteCandidatures() {
  const { statut } = useAgent();
  if (!statut) return null;

  let texte;
  let action;
  if (!statut.connected) {
    texte = "Aucune boîte mail liée : l'agent ne récupère pas encore les candidatures.";
    action = { vers: '/boite-mail', libelle: 'Lier la boîte mail', icone: Mail };
  } else if (statut.needs_setup) {
    texte = `La boîte ${statut.account_email} est liée : choisissez les candidatures à reprendre.`;
    action = { vers: '/boite-mail', libelle: 'Terminer la configuration', icone: Mail };
  } else {
    const surveillance = statut.watching ? `surveillée toutes les ${statut.poll_minutes} min` : 'surveillance en pause';
    texte = `${statut.account_email || 'Boîte de démonstration'} · ${surveillance} · dernière vérification : ${formaterDateHeure(statut.last_sync_at)}`;
    action = { vers: '/candidatures', libelle: 'Voir les candidatures', icone: FileText };
  }
  const Icone = action.icone;

  return (
    <Link
      to={action.vers}
      className="group mb-6 flex flex-wrap items-center gap-5 rounded-xl border border-line bg-white p-5 transition-colors hover:border-navy-200"
    >
      <div className="min-w-32">
        <p className="text-sm font-medium text-muted">CV reçus</p>
        <p className="mt-1 text-3xl font-bold text-navy-900">{statut.total_cvs}</p>
      </div>
      <p className="min-w-0 flex-1 text-sm text-muted">{texte}</p>
      <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-brand-700">
        <Icone className="size-4" aria-hidden /> {action.libelle}
        <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" aria-hidden />
      </span>
    </Link>
  );
}
