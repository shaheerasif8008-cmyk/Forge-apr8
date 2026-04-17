// Exposes safe IPC bridges to the renderer via contextBridge
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electron', {
  notify: (title, body) => ipcRenderer.invoke('notify', { title, body }),
  backendUrl: process.env.FORGE_BACKEND_URL || '',
})
