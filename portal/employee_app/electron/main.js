const { app, BrowserWindow } = require('electron')
const path = require('path')

const FORGE_BACKEND_URL = process.env.FORGE_BACKEND_URL || process.env.EMPLOYEE_APP_URL || ''

function createWindow() {
  const win = new BrowserWindow({
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
    win.loadURL(FORGE_BACKEND_URL)
    return
  }
  win.loadFile(path.join(__dirname, '..', 'out', 'index.html'))
}

app.whenReady().then(createWindow)

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
