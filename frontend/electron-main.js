import { app, BrowserWindow } from "electron";
import path from "path";
import { fileURLToPath } from 'url'; // Hinzufügen für __dirname
// Prüfen, ob wir im Entwicklungsmodus sind (Vite Dev Server) oder im Produktionsmodus (Build-Dateien)
import isDev from "electron-is-dev";

// --- GTK Version Fix für Electron 36+ unter GNOME ---
// Setzt die GTK-Version auf 3, um Konflikte zu vermeiden, da Electron 36+
// standardmäßig GTK 4 unter GNOME verwenden möchte, was zu Problemen führen kann,
// wenn andere Teile der Anwendung oder native Module GTK 2/3 erwarten.
// Siehe Diskussion und Electron 36 Release Notes.
if (process.platform === 'linux') { // Nur für Linux relevant
	app.commandLine.appendSwitch('gtk-version', '3');
}
// --- Ende GTK Version Fix ---

const __filename = fileURLToPath(import.meta.url); // Aktueller Dateipfad
const __dirname = path.dirname(__filename);       // Verzeichnis der aktuellen Datei

function createWindow() {
	const mainWindow = new BrowserWindow({
		width: 1024,
		height: 768,
		icon: path.join(__dirname, 'public', 'narrow-icon.png'),
		webPreferences: {
			nodeIntegration: false, // Wichtig für Sicherheit, Standard ist false ab Electron 5
			contextIsolation: true, // Wichtig für Sicherheit, Standard ist true ab Electron 12
			// preload: path.join(__dirname, 'preload.js') // Hier dein Preload-Skript einbinden, falls benötigt
		},
	});

	if (isDev) {
		// Im Entwicklungsmodus: Lade die URL vom Vite Dev Server
		mainWindow.loadURL("http://localhost:5173");
		// Öffne die Entwicklertools automatisch
		mainWindow.webContents.openDevTools('detached-panel');
	} else {
		// Im Produktionsmodus: Lade die gebaute index.html Datei
		mainWindow.loadFile(path.join(__dirname, "dist", "index.html"));
	}
}

// Diese Methode wird aufgerufen, wenn Electron mit der Initialisierung fertig ist
// und bereit ist, Browser-Fenster zu erstellen.
// Einige APIs können nur nach dem Eintreten dieses Events verwendet werden.
app.whenReady().then(() => {
	createWindow();

	app.on("activate", function () {
		// Auf macOS ist es üblich, ein neues Fenster in der App zu erstellen, wenn
		// das Dock-Icon angeklickt wird und keine anderen Fenster geöffnet sind.
		if (BrowserWindow.getAllWindows().length === 0) createWindow();
	});
});

// Beende die Anwendung, wenn alle Fenster geschlossen sind, außer auf macOS.
// Dort ist es üblich, dass Anwendungen und ihre Menüleisten aktiv bleiben,
// bis der Benutzer sie explizit mit Cmd + Q beendet.
app.on("window-all-closed", function () {
	if (process.platform !== "darwin") { // 'darwin' ist macOS
		app.quit();
	}
});

// Hier könntest du noch weitere anwendungsspezifische Hauptprozess-Logik hinzufügen.
// Zum Beispiel IPC-Handler für die Kommunikation mit dem Renderer-Prozess.
