// Exposes safe IPC bridges to the renderer via contextBridge
const { contextBridge, ipcRenderer } = require('electron')

const fileDropListeners = new Set()

window.addEventListener('DOMContentLoaded', () => {
  window.addEventListener('drop', (event) => {
    const files = Array.from(event.dataTransfer?.files || [])
    for (const file of files) {
      if (!file.path) continue
      for (const listener of fileDropListeners) {
        listener(file.path)
      }
    }
  })
})

contextBridge.exposeInMainWorld('forge', {
  backendUrl: process.env.FORGE_BACKEND_URL || '',
  setBadgeCount: (count) => ipcRenderer.invoke('forge:set-badge-count', count),
  notify: (title, body, actionUrl = '') => ipcRenderer.invoke('forge:notify', { title, body, actionUrl }),
  onFileDropped: (listener) => {
    fileDropListeners.add(listener)
    return () => fileDropListeners.delete(listener)
  },
})
