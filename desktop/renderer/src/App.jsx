import { HashRouter, Navigate, Outlet, Route, Routes } from 'react-router-dom';
import Disposition from './components/Disposition.jsx';
import BoiteMail from './pages/BoiteMail.jsx';
import Candidatures from './pages/Candidatures.jsx';
import Entretien from './pages/Entretien.jsx';
import FicheCandidature from './pages/FicheCandidature.jsx';
import { Alerte, Chargement } from './components/ui.jsx';
import Connexion from './pages/Connexion.jsx';
import CreationCompte from './pages/CreationCompte.jsx';
import MotDePasseOublie from './pages/MotDePasseOublie.jsx';
import PosteDetail from './pages/PosteDetail.jsx';
import PosteFormulaire from './pages/PosteFormulaire.jsx';
import Postes from './pages/Postes.jsx';
import ProfilEntreprise from './pages/ProfilEntreprise.jsx';
import TableauDeBord from './pages/TableauDeBord.jsx';
import Fenetre from './components/shell/Fenetre.jsx';
import { FournisseurSession, useSession } from './session.jsx';

/** Écrans sans connexion : création du compte (si aucun compte) ou connexion / récupération (si un compte existe). */
function AccesPublic({ creation = false }) {
  const { compteExiste, connecte } = useSession();
  if (connecte) return <Navigate to="/" replace />;
  if (creation && compteExiste) return <Navigate to="/connexion" replace />;
  if (!creation && !compteExiste) return <Navigate to="/creation" replace />;
  return <Outlet />;
}

/** Tout le reste exige une session. */
function AccesProtege() {
  const { compteExiste, connecte } = useSession();
  if (!compteExiste) return <Navigate to="/creation" replace />;
  if (!connecte) return <Navigate to="/connexion" replace />;
  return <Outlet />;
}

function Routeur() {
  const { charge, erreur } = useSession();
  if (!charge) return <Chargement texte="Démarrage d'INJARA…" plein />;
  if (erreur) {
    return (
      <div className="grid h-full place-items-center p-12">
        <div className="w-full max-w-md">
          <Alerte titre="INJARA ne répond pas">{erreur}</Alerte>
        </div>
      </div>
    );
  }
  return (
    <Routes>
      <Route element={<AccesPublic creation />}>
        <Route path="/creation" element={<CreationCompte />} />
      </Route>
      <Route element={<AccesPublic />}>
        <Route path="/connexion" element={<Connexion />} />
        <Route path="/mot-de-passe-oublie" element={<MotDePasseOublie />} />
      </Route>
      <Route element={<AccesProtege />}>
        <Route element={<Disposition />}>
          <Route index element={<TableauDeBord />} />
          <Route path="/entreprise" element={<ProfilEntreprise />} />
          <Route path="/candidatures" element={<Candidatures />} />
          <Route path="/candidatures/:id" element={<FicheCandidature />} />
          <Route path="/entretiens/:id" element={<Entretien />} />
          <Route path="/boite-mail" element={<BoiteMail />} />
          <Route path="/postes" element={<Postes />} />
          <Route path="/postes/nouveau" element={<PosteFormulaire />} />
          <Route path="/postes/:id" element={<PosteDetail />} />
          <Route path="/postes/:id/modifier" element={<PosteFormulaire />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <HashRouter>
      <FournisseurSession>
        <Fenetre>
          <Routeur />
        </Fenetre>
      </FournisseurSession>
    </HashRouter>
  );
}
