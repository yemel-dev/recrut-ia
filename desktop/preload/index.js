// Pont sécurisé : l'interface ne reçoit que cette petite API, sans accès à Node ni à ipcRenderer.

const { contextBridge, ipcRenderer, webUtils } = require('electron');

const requete = (methode, chemin, corps) => ipcRenderer.invoke('injara:requete', { methode, chemin, corps });

const abonner = (canal, ecouteur) => {
  ipcRenderer.on(canal, ecouteur);
  return () => ipcRenderer.removeListener(canal, ecouteur);
};

contextBridge.exposeInMainWorld('injara', {
  api: {
    get: (chemin) => requete('GET', chemin),
    post: (chemin, corps) => requete('POST', chemin, corps),
    put: (chemin, corps) => requete('PUT', chemin, corps),
    delete: (chemin) => requete('DELETE', chemin),
  },
  /** Entretien vidéo : signalisation WebRTC relayée par le processus principal, et enregistrement local chiffré. */
  entretien: {
    /** Ouvre la salle ; renvoie { ok, donnees: { ice } } ou { ok: false, donnees: { detail } }. */
    ouvrirSalle: (entretienId) => ipcRenderer.invoke('injara:salle-ouvrir', entretienId),
    envoyer: (texte) => ipcRenderer.invoke('injara:salle-envoyer', texte),
    fermerSalle: () => ipcRenderer.invoke('injara:salle-fermer'),
    /** Messages de signalisation reçus ; renvoie la fonction qui se désabonne. */
    surMessage: (rappel) => abonner('injara:salle-message', (_e, texte) => rappel(texte)),
    surFermeture: (rappel) => abonner('injara:salle-fermee', (_e, infos) => rappel(infos.code)),
    envoyerMorceau: (entretienId, morceau) => ipcRenderer.invoke('injara:enregistrement-morceau', entretienId, morceau),
    /** Boîte « Enregistrer sous » puis écriture du fichier déchiffré. Renvoie { ok, chemin }, { annule } ou { ok: false, message }. */
    exporterEnregistrement: (entretienId) => ipcRenderer.invoke('injara:exporter-enregistrement', entretienId),
  },
  fichiers: {
    /** Ouvre la boîte de dialogue « Importer des CV » ; renvoie les chemins choisis. */
    choisirCV: () => ipcRenderer.invoke('injara:choisir-cv'),
    /** Chemin local d'un fichier glissé-déposé dans la fenêtre. */
    cheminDe: (fichier) => webUtils.getPathForFile(fichier),
    importerCV: (chemins) => ipcRenderer.invoke('injara:importer-cv', chemins),
    /** Ouvre le CV d'une candidature (déchiffré dans un dossier temporaire) ; renvoie un message d'erreur, ou une chaîne vide. */
    ouvrirCV: (candidatureId) => ipcRenderer.invoke('injara:ouvrir-cv', candidatureId),
    importerIdentifiantsGoogle: () => ipcRenderer.invoke('injara:importer-identifiants-google'),
    /** Rapport PDF du candidat : l'utilisateur choisit où l'enregistrer. Renvoie { ok, chemin }, { annule } ou { ok: false, message }. */
    exporterRapport: (candidatureId) => ipcRenderer.invoke('injara:exporter-rapport', candidatureId),
  },
});
