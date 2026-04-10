const { app, BrowserWindow, Notification } = require('electron')
const path = require('path')

const EMPLOYEE_APP_URL = process.env.EMPLOYEE_APP_URL || 'http://localhost:3001'

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
  win.loadURL(EMPLOYEE_APP_URL)
}

app.whenReady().then(createWindow)

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
