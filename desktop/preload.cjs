const { contextBridge, ipcRenderer } = require('electron');
// Only a folder picker is exposed; the renderer cannot invoke arbitrary IPC.
contextBridge.exposeInMainWorld('perchDesktop', Object.freeze({
  chooseWorkspace: () => ipcRenderer.invoke('perch:choose-workspace'),
}));
