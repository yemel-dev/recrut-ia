// Mails aux candidats : état de l'envoi, fonctionnement (invitation par le recruteur, réponse négative à la clôture
// du poste) et modèles, avec un éditeur et un aperçu en direct présenté comme un vrai mail.
import { CalendarCheck, Check, ChevronRight, Lock, MailX, Plus, RotateCcw, Save, Undo2, UserCheck } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';
import { useAgent } from '../agent/ContexteAgent.jsx';
import { Alerte, Badge, Bouton, Carte, Champ, Chargement, Confirmation, EnTetePage, Onglets, Saisie, ZoneTexte, cx } from '../components/ui.jsx';
import { AutorisationEnvoi } from '../mails/AutorisationEnvoi.jsx';
import { MailRendu } from '../mails/elements.jsx';

const MODELES = {
  invitation: {
    titre: 'Invitation à un entretien',
    court: 'Invitation',
    icone: CalendarCheck,
    variables: ['civilite_nom', 'poste', 'entreprise', 'date', 'heure', 'duree', 'lieu', 'message'],
    destinataire: 'Awa Ndong',
  },
  refus: {
    titre: 'Réponse négative',
    court: 'Réponse négative',
    icone: MailX,
    variables: ['civilite_nom', 'poste', 'entreprise'],
    destinataire: 'Awa Ndong',
  },
};

// Noms clairs des variables : l'utilisateur clique, la variable s'insère à l'endroit du curseur
const VARIABLES = {
  civilite_nom: 'Nom du candidat',
  poste: 'Poste',
  entreprise: 'Entreprise',
  date: 'Date',
  heure: 'Heure',
  duree: 'Durée',
  lieu: 'Lieu ou lien de la visio',
  message: 'Votre message',
};

/** Prévient la mise en page (état de l'envoi) qu'un réglage a changé. */
export const signalerReglagesMails = () => window.dispatchEvent(new Event('injara:reglages-mails'));

export default function ParametresMails() {
  const [reglages, setReglages] = useState(null);
  const [entreprise, setEntreprise] = useState('');
  const [onglet, setOnglet] = useState('invitation');
  const [modifies, setModifies] = useState({}); // type -> modifications non enregistrées
  const [erreur, setErreur] = useState('');

  useEffect(() => {
    api.get('/parametres/mails').then(setReglages, (err) => setErreur(err.message));
    api.get('/entreprise').then((e) => setEntreprise(e.nom || ''), () => {});
  }, []);

  if (!reglages) return erreur ? <Alerte>{erreur}</Alerte> : <Chargement />;

  return (
    <>
      <EnTetePage
        titre="Mails aux candidats"
        description="Les réponses aux candidats partent de votre boîte de recrutement, signées du nom de votre entreprise."
      />

      <div className="mb-10 flex flex-col gap-5">
        <AutorisationEnvoi onChange={signalerReglagesMails} />
        <Fonctionnement />
      </div>

      <section aria-labelledby="titre-modeles">
        <div className="mb-1 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 id="titre-modeles" className="titre-section text-xl!">Modèles de mail</h2>
            <p className="mt-1 text-sm text-doux">Le texte envoyé à chaque candidat. Les variables sont remplacées par ses informations.</p>
          </div>
        </div>
        <Onglets
          className="mt-4"
          valeur={onglet}
          onChange={setOnglet}
          onglets={Object.entries(MODELES).map(([type, d]) => ({
            valeur: type,
            libelle: (
              <span className="flex items-center gap-2">
                <d.icone className="size-4" aria-hidden />
                {d.court}
                {modifies[type] && <span className="size-1.5 rounded-full bg-alerte" title="Modifications non enregistrées" />}
              </span>
            ),
          }))}
        />
        {/* Les deux éditeurs restent montés : changer d'onglet ne perd pas une saisie en cours */}
        {Object.keys(MODELES).map((type) => (
          <div key={type} hidden={onglet !== type}>
            <EditeurModele
              type={type}
              modele={reglages.modeles[type]}
              entreprise={entreprise}
              onModifie={(oui) => setModifies((m) => ({ ...m, [type]: oui }))}
              onEnregistre={(nouveaux) => {
                setReglages(nouveaux);
                signalerReglagesMails();
              }}
            />
          </div>
        ))}
      </section>
    </>
  );
}

/** Quand part chaque mail : le recruteur invite, la clôture du poste prévient les autres. */
function Fonctionnement() {
  const etapes = [
    {
      icone: UserCheck,
      titre: 'Vous retenez des candidats',
      texte: "Sur leur fiche, puis vous planifiez l'entretien.",
    },
    {
      icone: CalendarCheck,
      titre: "Vous envoyez l'invitation",
      texte: "Depuis la page du poste, après l'aperçu de chaque mail.",
      mail: 'Invitation',
    },
    {
      icone: Lock,
      titre: 'Vous clôturez le poste',
      texte: 'Les candidats non retenus reçoivent la réponse négative, automatiquement.',
      mail: 'Réponse négative',
    },
  ];
  return (
    <Carte className="flex flex-col gap-4">
      <h2 className="titre-section">Comment ça marche</h2>
      <ol className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_auto_1fr_auto_1fr] md:items-stretch">
        {etapes.flatMap((e, i) => [
          i > 0 && (
            <li key={`fleche-${i}`} aria-hidden className="hidden items-center text-tenu md:flex">
              <ChevronRight className="size-5" />
            </li>
          ),
          <li key={e.titre} className="relative flex flex-col gap-2 rounded-lg border border-trait bg-enfonce/60 p-4">
            <div className="flex items-center gap-2.5">
              <span className="grid size-8 shrink-0 place-items-center rounded-md border border-accent-trait bg-accent-doux text-accent-texte">
                <e.icone className="size-4" aria-hidden />
              </span>
              <span className="font-affichage text-sm font-medium text-tenu tabular-nums">{String(i + 1).padStart(2, '0')}</span>
            </div>
            <p className="font-semibold leading-snug text-fort">{e.titre}</p>
            <p className="text-sm leading-snug text-doux">{e.texte}</p>
            {e.mail && (
              <Badge ton="accent" className="mt-auto self-start">
                {e.mail}
              </Badge>
            )}
          </li>,
        ])}
      </ol>
    </Carte>
  );
}

function EditeurModele({ type, modele, entreprise, onModifie, onEnregistre }) {
  const { notifier } = useAgent();
  const def = MODELES[type];
  const [objet, setObjet] = useState(modele.objet);
  const [corps, setCorps] = useState(modele.corps);
  const [apercu, setApercu] = useState(null);
  const [erreurs, setErreurs] = useState({});
  const [envoi, setEnvoi] = useState(false);
  const [retablir, setRetablir] = useState(false);
  const zone = useRef(null);
  const champObjet = useRef(null);
  const dernierChamp = useRef('corps'); // où insérer une variable : dernier champ utilisé
  const modifie = objet !== modele.objet || corps !== modele.corps;

  useEffect(() => {
    setObjet(modele.objet);
    setCorps(modele.corps);
  }, [modele]);

  useEffect(() => onModifie(modifie), [modifie]); // eslint-disable-line react-hooks/exhaustive-deps

  // Aperçu en direct (valeurs d'exemple), recalculé peu après la frappe
  useEffect(() => {
    const minuteur = setTimeout(() => {
      api.post(`/parametres/mails/modeles/${type}/apercu`, { objet, corps }).then(
        (a) => {
          setApercu(a);
          setErreurs({});
        },
        (err) => setErreurs(err.champs || {}),
      );
    }, 250);
    return () => clearTimeout(minuteur);
  }, [type, objet, corps]);

  const inserer = (variable) => {
    const jeton = `{${variable}}`;
    const champ = dernierChamp.current === 'objet' ? champObjet.current : zone.current;
    const [valeur, changer] = dernierChamp.current === 'objet' ? [objet, setObjet] : [corps, setCorps];
    const debut = champ?.selectionStart ?? valeur.length;
    const fin = champ?.selectionEnd ?? valeur.length;
    changer(valeur.slice(0, debut) + jeton + valeur.slice(fin));
    requestAnimationFrame(() => {
      champ?.focus();
      champ?.setSelectionRange(debut + jeton.length, debut + jeton.length);
    });
  };

  const enregistrer = async () => {
    setEnvoi(true);
    setErreurs({});
    try {
      onEnregistre(await api.put(`/parametres/mails/modeles/${type}`, { objet, corps }));
      notifier(`Modèle « ${def.titre} » enregistré.`, 'succes');
    } catch (err) {
      setErreurs(err.champs || {});
    } finally {
      setEnvoi(false);
    }
  };

  const remettre = async () => {
    setEnvoi(true);
    try {
      onEnregistre(await api.delete(`/parametres/mails/modeles/${type}`));
      notifier(`Modèle « ${def.titre} » rétabli.`, 'succes');
    } finally {
      setEnvoi(false);
      setRetablir(false);
    }
  };

  return (
    <Carte sansMarge className="overflow-hidden">
      <div className="grid grid-cols-1 lg:grid-cols-2">
        {/* Éditeur */}
        <div className="flex flex-col gap-4 p-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="titre-section">{def.titre}</h3>
            <Badge ton={modele.par_defaut ? 'neutre' : 'info'}>{modele.par_defaut ? 'Modèle INJARA' : 'Votre modèle'}</Badge>
          </div>
          <Champ label="Objet" erreur={erreurs.objet}>
            {(a) => (
              <Saisie
                {...a}
                ref={champObjet}
                value={objet}
                maxLength={200}
                onFocus={() => (dernierChamp.current = 'objet')}
                onChange={(e) => setObjet(e.target.value)}
              />
            )}
          </Champ>
          <Champ label="Texte du mail" erreur={erreurs.corps}>
            {(a) => (
              <ZoneTexte
                {...a}
                ref={zone}
                rows={12}
                value={corps}
                maxLength={5000}
                onFocus={() => (dernierChamp.current = 'corps')}
                onChange={(e) => setCorps(e.target.value)}
                className="min-h-72 text-base leading-relaxed [field-sizing:content]"
              />
            )}
          </Champ>
          <div>
            <p className="etiquette mb-2">Insérer une information du candidat</p>
            <div className="flex flex-wrap gap-1.5">
              {def.variables.map((v) => (
                <button
                  key={v}
                  type="button"
                  onMouseDown={(e) => e.preventDefault()} // garde le curseur dans le champ
                  onClick={() => inserer(v)}
                  title={`Insère {${v}}`}
                  className="appui inline-flex h-7 items-center gap-1 rounded-full border border-trait-fort px-2.5 text-sm text-texte transition-colors hover:border-accent-trait hover:bg-accent-doux hover:text-accent-texte"
                >
                  <Plus className="size-3" aria-hidden />
                  {VARIABLES[v]}
                </button>
              ))}
            </div>
            <p className="mt-2.5 text-xs leading-relaxed text-tenu">
              Sans nom fiable dans le CV, le nom devient « Madame, Monsieur ».
              {type === 'invitation' && ' Une ligne qui ne contient que « Votre message » disparaît quand le message est vide.'}
            </p>
          </div>
          <div className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t border-trait pt-4">
            <div className="flex items-center gap-1">
              {!modele.par_defaut && !modifie && (
                <Bouton variante="discret" taille="sm" icone={RotateCcw} onClick={() => setRetablir(true)}>
                  Rétablir le modèle INJARA
                </Bouton>
              )}
              {modifie && (
                <Bouton
                  variante="discret"
                  taille="sm"
                  icone={Undo2}
                  onClick={() => {
                    setObjet(modele.objet);
                    setCorps(modele.corps);
                  }}
                >
                  Annuler les modifications
                </Bouton>
              )}
            </div>
            <div className="flex items-center gap-3">
              <span className={cx('flex items-center gap-1.5 text-sm', modifie ? 'text-alerte' : 'text-tenu')}>
                {modifie ? 'Non enregistré' : <><Check className="size-3.5" aria-hidden /> Enregistré</>}
              </span>
              <Bouton icone={Save} chargement={envoi} disabled={!modifie} onClick={enregistrer}>Enregistrer</Bouton>
            </div>
          </div>
        </div>

        {/* Aperçu en direct */}
        <div className="border-t border-trait bg-enfonce/50 p-6 lg:border-t-0 lg:border-l">
          <div>
            <p className="etiquette mb-3">Aperçu, avec un exemple de candidat</p>
            <MailApercu apercu={apercu} entreprise={entreprise} destinataire={def.destinataire} />
          </div>
        </div>
      </div>

      <Confirmation
        ouverte={retablir}
        titre="Rétablir le modèle INJARA ?"
        libelleConfirmer="Rétablir"
        chargement={envoi}
        onConfirmer={remettre}
        onAnnuler={() => setRetablir(false)}
      >
        Votre texte sera remplacé par le modèle d'origine d'INJARA.
      </Confirmation>
    </Carte>
  );
}

/** Le mail tel que le candidat le recevra : objet et expéditeur, puis le mail mis en forme. */
function MailApercu({ apercu, entreprise, destinataire }) {
  if (!apercu) return <div className="squelette h-96 rounded-lg" />;
  const nom = entreprise || 'Votre entreprise';
  return (
    <article className="overflow-hidden rounded-lg border border-trait bg-surface shadow-flottante">
      <header className="border-b border-trait px-5 py-4">
        <p className="text-lg leading-snug font-semibold text-fort">{apercu.objet || <span className="text-tenu">(sans objet)</span>}</p>
        <p className="mt-1 truncate text-sm text-doux">
          De : <span className="font-medium text-texte">{nom}</span> · À : {destinataire}
        </p>
      </header>
      <MailRendu html={apercu.html} />
    </article>
  );
}
