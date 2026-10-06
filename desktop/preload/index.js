// Pont sécurisé : l'interface ne reçoit que cette petite API, sans accès à Node ni à ipcRenderer.

const { contextBridge, ipcRenderer } = require('electron');

const requete = (methode, chemin, corps) => ipcRenderer.invoke('injara:requete', { methode, chemin, corps });

contextBridge.exposeInMainWorld('injara', {
  api: {
    get: (chemin) => requete('GET', chemin),
    post: (chemin, corps) => requete('POST', chemin, corps),
    put: (chemin, corps) => requete('PUT', chemin, corps),
    delete: (chemin) => requete('DELETE', chemin),
  },
});
