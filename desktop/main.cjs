const { app, BrowserWindow, shell, dialog, ipcMain } = require("electron");
const URL_BASE = "http://127.0.0.1:8080";
app.setName("Perch");
app.setPath(
  "userData",
  require("node:path").join(app.getPath("appData"), "Local Agents WebUI"),
);
let win;
let choosingWorkspace = false;
ipcMain.handle("perch:choose-workspace", async (event) => {
  if (!win || event.sender !== win.webContents || event.senderFrame !== win.webContents.mainFrame ||
      new URL(event.senderFrame.url).origin !== URL_BASE) throw new Error("Untrusted folder request");
  if (choosingWorkspace) return null;
  choosingWorkspace = true;
  try {
    const result = await dialog.showOpenDialog(win, {
      title: "选择工作空间", buttonLabel: "使用此文件夹",
      properties: ["openDirectory", "createDirectory"],
    });
    return result.canceled ? null : result.filePaths[0] || null;
  } finally { choosingWorkspace = false; }
});
function createWindow() {
  win = new BrowserWindow({
    width: 1200,
    height: 860,
    minWidth: 390,
    minHeight: 600,
    title: "Perch · 栖",
    backgroundColor: "#171717",
    webPreferences: {
      preload: require("node:path").join(__dirname, "preload.cjs"),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true,
    },
  });
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//.test(url)) shell.openExternal(url);
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (event, url) => {
    if (new URL(url).origin !== URL_BASE) {
      event.preventDefault();
      if (/^https?:\/\//.test(url)) shell.openExternal(url);
    }
  });
  win.webContents.session.setPermissionRequestHandler(
    (_wc, _permission, callback) => callback(false),
  );
  win.loadURL(URL_BASE + "/");
  win.webContents.on("did-fail-load", (_e, code) => {
    if (code !== -3)
      dialog.showErrorBox(
        "本机服务暂不可用",
        "请确认 Open WebUI 服务正在运行于 127.0.0.1:8080，再重新打开客户端。",
      );
  });
}
if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on("second-instance", () => {
    if (win) {
      win.show();
      win.focus();
    }
  });
  app.whenReady().then(createWindow);
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
  app.on("window-all-closed", () => app.quit());
}
