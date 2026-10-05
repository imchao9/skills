const { app, BrowserWindow, shell } = require("electron");
const path = require("node:path");
const { startServer } = require("./local-server.cjs");

let mainWindow;
let localServer;

async function createWindow() {
  if (!localServer) localServer = await startServer();
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 960,
    minWidth: 960,
    minHeight: 700,
    title: "Skill Atlas",
    backgroundColor: "#fdfefe",
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  mainWindow.webContents.setWindowOpenHandler(({ url }) => { if (!url.startsWith("http://127.0.0.1:")) shell.openExternal(url); return { action: "deny" }; });
  await mainWindow.loadURL(`http://127.0.0.1:${localServer.port}/`);
  mainWindow.on("closed", () => { mainWindow = null; });
}

app.whenReady().then(createWindow).catch((error) => { console.error(error); app.quit(); });
app.on("activate", () => { if (!mainWindow) createWindow(); });
app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
app.on("before-quit", () => { localServer?.server.close(); localServer?.otlpServer?.close(); });
