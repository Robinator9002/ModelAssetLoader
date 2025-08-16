import { app, BrowserWindow } from 'electron';
import path from 'path';
import { fileURLToPath } from 'url'; // Added for __dirname
// Check if we are in development mode (Vite Dev Server) or production mode (build files)
import isDev from 'electron-is-dev';

// --- GTK Version Fix for Electron 36+ under GNOME ---
// Forces GTK version 3 to avoid conflicts, since Electron 36+
// defaults to GTK 4 under GNOME, which can cause issues if other
// parts of the app or native modules expect GTK 2/3.
// See discussion and Electron 36 release notes.
if (process.platform === 'linux') {
    // Only relevant for Linux
    app.commandLine.appendSwitch('gtk-version', '3');
}
// --- End GTK Version Fix ---

const __filename = fileURLToPath(import.meta.url); // Current file path
const __dirname = path.dirname(__filename); // Directory of the current file

function createWindow() {
    const mainWindow = new BrowserWindow({
        width: 1024,
        height: 768,
        icon: path.join(__dirname, 'public', 'narrow-icon.png'),
        webPreferences: {
            nodeIntegration: false, // Important for security, default is false since Electron 5
            contextIsolation: true, // Important for security, default is true since Electron 12
            // preload: path.join(__dirname, 'preload.js') // Load your preload script here if needed
        },
    });

    if (isDev) {
        // In development mode: load the URL from the Vite Dev Server
        mainWindow.loadURL('http://localhost:5173');
        // Automatically open the devtools
        mainWindow.webContents.openDevTools('detached-panel');
    } else {
        // In production mode: load the built index.html file
        mainWindow.loadFile(path.join(__dirname, 'dist', 'index.html'));
    }
}

// This method is called when Electron has finished initialization
// and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.whenReady().then(() => {
    createWindow();

    app.on('activate', function () {
        // On macOS it’s common to re-create a window in the app when the
        // dock icon is clicked and there are no other windows open.
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

// Quit the application when all windows are closed, except on macOS.
// There it is common for applications and their menu bar to stay active
// until the user explicitly quits with Cmd + Q.
app.on('window-all-closed', function () {
    if (process.platform !== 'darwin') {
        // 'darwin' is macOS
        app.quit();
    }
});

// Here you can add more application-specific main process logic.
// For example, IPC handlers for communication with the renderer process.
