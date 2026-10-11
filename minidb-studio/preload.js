const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('minidb', {
  // Query execution
  executeQuery: (query) => ipcRenderer.invoke('execute-query', query),

  // Table explorer
  listTables: () => ipcRenderer.invoke('list-tables'),

  // Export
  exportResults: (options) => ipcRenderer.invoke('export-results', options),

  // Window controls
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),

  // External links
  openExternal: (url) => ipcRenderer.send('open-external', url),
});