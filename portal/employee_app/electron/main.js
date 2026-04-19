const { app, BrowserWindow, ipcMain, Notification, shell } = require('electron')
const path = require('path')

const FORGE_BACKEND_URL = process.env.FORGE_BACKEND_URL || process.env.EMPLOYEE_APP_URL || ''
let mainWindow = null

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
    titleBarStyle: 'hiddenInset',
  })
  if (FORGE_BACKEND_URL) {
    mainWindow.loadURL(FORGE_BACKEND_URL)
    return
  }
  mainWindow.loadFile(path.join(__dirname, '..', 'out', 'index.html'))
}

app.whenReady().then(() => {
  ipcMain.handle('forge:set-badge-count', (_event, count) => {
    if (typeof app.setBadgeCount === 'function') {
      app.setBadgeCount(Number(count) || 0)
    }
    return { ok: true }
  })

  ipcMain.handle('forge:notify', (_event, payload) => {
    const title = payload?.title || 'Forge Employee'
    const body = payload?.body || ''
    const actionUrl = payload?.actionUrl || ''
    if (!Notification.isSupported()) {
      return { ok: false, reason: 'unsupported' }
    }
    const notification = new Notification({ title, body })
    notification.on('click', () => {
      if (actionUrl && /^https?:/i.test(actionUrl)) {
        void shell.openExternal(actionUrl)
      }
      if (mainWindow) {
        if (mainWindow.isMinimized()) {
          mainWindow.restore()
        }
        mainWindow.show()
        mainWindow.focus()
      }
    })
    notification.show()
    return { ok: true }
  })

  createWindow()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
