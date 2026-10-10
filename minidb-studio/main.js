const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

let mainWindow;
let pythonProcess;

// Resolve paths
function getPythonPath() {
  // In production: bundled python; in dev: system python
  const devPath = 'python';
  return devPath;
}

function getMiniDBPath() {
  // In production the miniDB folder is in extraResources
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'miniDB');
  }
  return path.join(__dirname, '..', 'miniDB');
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 650,
    frame: false,
    titleBarStyle: 'hidden',
    backgroundColor: '#050816',
    icon: path.join(__dirname, 'assets', 'icon.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  mainWindow.loadFile('renderer/index.html');

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// ─── IPC: Window Controls ────────────────────────────────────────────────────
ipcMain.on('window-minimize', () => mainWindow?.minimize());
ipcMain.on('window-maximize', () => {
  if (mainWindow?.isMaximized()) mainWindow.restore();
  else mainWindow?.maximize();
});
ipcMain.on('window-close', () => mainWindow?.close());

// ─── IPC: Execute Query ──────────────────────────────────────────────────────
ipcMain.handle('execute-query', async (event, query) => {
  return new Promise((resolve) => {
    const minidbPath = getMiniDBPath();
    const pythonPath = getPythonPath();

    // Write query to temp file and pass via stdin
    const scriptPath = path.join(__dirname, 'bridge.py');
    const child = spawn(pythonPath, [scriptPath, minidbPath], {
      cwd: minidbPath,
    });

    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (d) => (stdout += d.toString()));
    child.stderr.on('data', (d) => (stderr += d.toString()));

    child.on('close', (code) => {
      if (code !== 0 || stderr) {
        resolve({ success: false, error: stderr || 'Unknown error', rows: [], columns: [], message: null });
      } else {
        try {
          const result = JSON.parse(stdout);
          resolve(result);
        } catch (e) {
          resolve({ success: false, error: 'Failed to parse result: ' + stdout, rows: [], columns: [], message: null });
        }
      }
    });

    child.stdin.write(query);
    child.stdin.end();
  });
});

// ─── IPC: List Tables ────────────────────────────────────────────────────────
ipcMain.handle('list-tables', async () => {
  const minidbPath = getMiniDBPath();
  const dataDir = path.join(minidbPath, 'data');
  try {
    const files = fs.readdirSync(dataDir);
    const schemaPath = path.join(dataDir, '_schema.json');
    let schemas = {};
    if (fs.existsSync(schemaPath)) {
      schemas = JSON.parse(fs.readFileSync(schemaPath, 'utf8'));
    }

    const tables = files
      .filter((f) => f.endsWith('.json') && f !== '_schema.json')
      .map((f) => {
        const name = f.replace('.json', '');
        let rowCount = 0;
        try {
          const rows = JSON.parse(fs.readFileSync(path.join(dataDir, f), 'utf8'));
          rowCount = rows.length;
        } catch (e) {}
        return {
          name,
          rowCount,
          schema: schemas[name] || null,
        };
      });

    return { success: true, tables };
  } catch (e) {
    return { success: false, error: e.message, tables: [] };
  }
});

// ─── IPC: Export Results ─────────────────────────────────────────────────────
ipcMain.handle('export-results', async (event, { format, data, columns }) => {
  const { filePath } = await dialog.showSaveDialog(mainWindow, {
    title: 'Export Results',
    defaultPath: `minidb_export_${Date.now()}.${format}`,
    filters: [
      format === 'csv' ? { name: 'CSV', extensions: ['csv'] } : { name: 'JSON', extensions: ['json'] },
    ],
  });

  if (!filePath) return { success: false, error: 'Cancelled' };

  try {
    let content = '';
    if (format === 'csv') {
      const header = columns.join(',');
      const rows = data.map((row) => columns.map((c) => `"${(row[c] ?? '').toString().replace(/"/g, '""')}"`).join(','));
      content = [header, ...rows].join('\n');
    } else {
      content = JSON.stringify(data, null, 2);
    }
    fs.writeFileSync(filePath, content, 'utf8');
    return { success: true, filePath };
  } catch (e) {
    return { success: false, error: e.message };
  }
});

// ─── IPC: Open external link ─────────────────────────────────────────────────
ipcMain.on('open-external', (_, url) => shell.openExternal(url));

app.whenReady().then(createWindow);
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
