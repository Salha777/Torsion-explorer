// Torsion Explorer: desktop wrapper around the offline page (site/index.html).
// The page needs no network and no Node access, so it runs fully sandboxed.
const { app, BrowserWindow, shell, Menu } = require("electron");
const path = require("path");

const SELFTEST = process.env.PTE_SELFTEST === "1"; // load, report, quit (used to test the build)

function createWindow() {
  const win = new BrowserWindow({
    width: 1440,
    height: 960,
    minWidth: 720,
    minHeight: 600,
    show: !SELFTEST,
    backgroundColor: "#0F151B",
    title: "Torsion Explorer",
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true, spellcheck: false },
  });
  win.loadFile(path.join(__dirname, "app", "index.html"));

  // the page never navigates; anything that tries to (a pasted link, a stray click) opens in the browser
  const external = (url) => { if (/^https?:\/\//i.test(url)) shell.openExternal(url); };
  win.webContents.setWindowOpenHandler(({ url }) => { external(url); return { action: "deny" }; });
  win.webContents.on("will-navigate", (e, url) => {
    if (!url.startsWith("file:")) { e.preventDefault(); external(url); }
  });

  if (SELFTEST) {
    win.webContents.on("did-finish-load", async () => {
      const r = await win.webContents.executeJavaScript(
        "new Promise(res=>setTimeout(()=>res({title:document.title,mols:document.querySelectorAll('#mols button').length," +
        "caption:document.getElementById('molcap').textContent.slice(0,60),fonts:document.fonts.check(\"400 14px 'IBM Plex Sans'\")}),1500))");
      console.log("SELFTEST " + JSON.stringify(r));
      app.quit();
    });
    win.webContents.on("did-fail-load", (_e, code, desc) => { console.log("SELFTEST FAIL " + code + " " + desc); app.exit(1); });
  }
}

Menu.setApplicationMenu(Menu.buildFromTemplate([
  { label: "File", submenu: [{ role: "quit" }] },
  { label: "View", submenu: [{ role: "reload" }, { role: "togglefullscreen" }, { type: "separator" },
    { role: "resetZoom" }, { role: "zoomIn" }, { role: "zoomOut" }] },
]));

app.whenReady().then(createWindow);
app.on("window-all-closed", () => app.quit());
