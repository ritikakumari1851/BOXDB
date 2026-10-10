# BOXDB 🗄️

A beautiful, unique desktop database GUI for your custom MiniDB engine.  
Built with **Electron** + **HTML/CSS/JS** frontend + **Python** backend.

---

## ✨ Features

| Feature | Details |
|---|---|
| 🎨 **Deep Space Dark Theme** | Navy/black + neon cyan & purple |
| 📝 **Query Editor** | Syntax highlighting for all MiniDB keywords |
| 🔮 **Autocomplete** | Keyword suggestions as you type |
| 📊 **Results Table** | Sortable columns, type-colored values |
| 🗂️ **Multiple Tabs** | Work on several queries at once |
| 📁 **DB Explorer Sidebar** | Browse tables, row counts, schemas |
| 📜 **Query History** | Click any past query to reload it |
| 💬 **Messages Panel** | Execution log with timestamps |
| 📤 **Export** | Download results as CSV or JSON |
| ↕️ **Resizable Panes** | Drag the divider between editor & results |

---

## 🚀 Quick Start (Dev Mode)

```bash
cd minidb-studio
npm start
```

**Keyboard shortcuts:**
- `Ctrl+Enter` — Run query
- `Tab` — Insert 2 spaces
- `Escape` — Close autocomplete / schema popup

---

## 📖 MiniDB Query Language

| Command | Syntax | Description |
|---|---|---|
| `GET` | `GET * FROM table` | Select all rows |
| `GET` | `GET col1 col2 FROM table FILTER col = val` | Select with filter |
| `GET` | `GET * FROM t1 JOIN t2 ON t1.id = t2.fk` | Join two tables |
| `ADD` | `ADD INTO table VALUES val1 val2 ...` | Insert a row |
| `CHANGE` | `CHANGE table SET col = val FILTER id = 1` | Update row(s) |
| `REMOVE` | `REMOVE FROM table FILTER col = val` | Delete row(s) |
| `BUILD` | `BUILD TABLE name WITH col1 INT col2 TEXT` | Create table |
| `INDEX` | `INDEX table ON column` | Create hash index |

**Column types:** `INT`, `TEXT`, `FLOAT`, `BOOL`

---

## 📦 Build Installer (.exe)

```bash
npm run build
```

This creates a Windows NSIS installer in the `dist/` folder.  
The installer includes MiniDB engine files and creates desktop + start menu shortcuts.

---

## 🏗️ Project Structure

```
minidb-studio/
├── main.js          # Electron main process
├── preload.js       # Secure IPC bridge
├── bridge.py        # Python↔Electron query bridge
├── renderer/
│   ├── index.html   # App UI
│   ├── styles.css   # Deep space dark theme
│   └── app.js       # Full app logic
└── assets/
    └── icon.png     # App icon
```
