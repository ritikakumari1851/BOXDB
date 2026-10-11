const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

let mainWindow;
let pythonProcess;

// Resolve paths
function getPythonPath() {
  if (process.env.PYTHON) return process.env.PYTHON;
  return 'python';
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
    backgroundColor: '#0e1017',
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

    child.on('error', (err) => {
      resolve({
        success: false,
        error: `Failed to start Python process: ${err.message}. Please ensure Python is installed and added to PATH.`,
        rows: [],
        columns: [],
        message: null,
      });
    });

    child.on('close', (code) => {
      if (code !== 0) {
        resolve({
          success: false,
          error: stderr.trim() || stdout.trim() || `Process exited with code ${code}`,
          rows: [],
          columns: [],
          message: null,
        });
      } else {
        try {
          const result = JSON.parse(stdout);
          resolve(result);
        } catch (e) {
          resolve({
            success: false,
            error: stderr.trim() || ('Failed to parse result: ' + stdout),
            rows: [],
            columns: [],
            message: null,
          });
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
    if (!fs.existsSync(dataDir)) {
      fs.mkdirSync(dataDir, { recursive: true });
    }
    const files = fs.readdirSync(dataDir);
    const schemaPath = path.join(dataDir, '_schema.json');
    let schemas = {};
    if (fs.existsSync(schemaPath)) {
      try {
        schemas = JSON.parse(fs.readFileSync(schemaPath, 'utf8'));
      } catch (e) {}
    }

    const tables = files
      .filter((f) => f.endsWith('.json') && !f.startsWith('_'))
      .map((f) => {
        const name = f.replace('.json', '');
        let rowCount = 0;
        try {
          const content = fs.readFileSync(path.join(dataDir, f), 'utf8').trim();
          if (content) {
            const rows = JSON.parse(content);
            if (Array.isArray(rows)) {
              rowCount = rows.length;
            }
          }
        } catch (e) {}
        const rawSchema = schemas[name] || null;
        let cleanSchema = null;
        if (rawSchema) {
          cleanSchema = Object.fromEntries(
            Object.entries(rawSchema).filter(([k]) => !k.startsWith('_'))
          );
        }
        return {
          name,
          rowCount,
          schema: cleanSchema,
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
