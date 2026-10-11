/**
 * BOXDB — Renderer Application Logic
 * Deep Space Dark Theme · Multi-tab · Syntax Highlighting · History · Export
 */

'use strict';

// ─── MiniDB Keywords for Syntax Highlighting ─────────────────────────────────
const SYNTAX = {
  commands: new Set(['GET','ADD','CHANGE','REMOVE','BUILD','INDEX','SELECT','INSERT','UPDATE','DELETE','CREATE','DROP','ALTER','SHOW','DESCRIBE','TRUNCATE']),
  clauses: new Set(['FROM','INTO','VALUES','SET','FILTER','WHERE','JOIN','INNER','LEFT','RIGHT','OUTER','CROSS','ON','WITH','TABLE','TABLES','COLUMN','ORDER','BY','ASC','DESC','GROUP','HAVING','LIMIT','OFFSET','DISTINCT','AS','AND','OR','NOT','IS','NULL','LIKE','IN','BETWEEN','PRIMARY','KEY','UNIQUE','DEFAULT','AUTO_INCREMENT']),
  aggregates: new Set(['COUNT','SUM','AVG','MAX','MIN']),
  types: new Set(['INT','INTEGER','TEXT','VARCHAR','FLOAT','REAL','BOOL','BOOLEAN']),
  booleans: new Set(['TRUE','FALSE']),
  operators: new Set(['=','>','<','!=','>=','<=']),
};

const AUTOCOMPLETE_SUGGESTIONS = [
  // ── BOXDB Native
  { kw:'GET',            desc:'Select rows',             example:'GET * FROM users ORDER BY age DESC LIMIT 10' },
  { kw:'ADD',            desc:'Insert a row',            example:'ADD INTO users VALUES (3, "Charlie", 22, "bangalore")' },
  { kw:'CHANGE',         desc:'Update rows',             example:'CHANGE users SET city = "delhi", age = 26 FILTER id = 1' },
  { kw:'REMOVE',         desc:'Delete rows',             example:'REMOVE FROM users FILTER id = 3' },
  { kw:'BUILD',          desc:'Create a table',          example:'BUILD TABLE products WITH id INT AUTO_INCREMENT name TEXT NOT NULL price FLOAT' },
  { kw:'INDEX',          desc:'Create hash index',       example:'INDEX users ON id' },
  // ── SQL Aliases
  { kw:'SELECT',         desc:'Select rows (SQL)',       example:'SELECT * FROM users WHERE age > 18' },
  { kw:'INSERT',         desc:'Insert row (SQL)',        example:'INSERT INTO users (name, age) VALUES ("Bob", 30)' },
  { kw:'UPDATE',         desc:'Update rows (SQL)',       example:'UPDATE users SET city = "mumbai" WHERE id = 2' },
  { kw:'DELETE',         desc:'Delete rows (SQL)',       example:'DELETE FROM users WHERE id = 3' },
  { kw:'CREATE',         desc:'Create table (SQL)',      example:'CREATE TABLE products (id INT PRIMARY KEY AUTO_INCREMENT, name TEXT NOT NULL, price FLOAT DEFAULT 0)' },
  { kw:'DROP',           desc:'Drop a table',           example:'DROP TABLE products' },
  { kw:'ALTER',          desc:'Alter table structure',  example:'ALTER TABLE users ADD COLUMN email TEXT' },
  { kw:'SHOW',           desc:'List all tables',        example:'SHOW TABLES' },
  { kw:'DESCRIBE',       desc:'Show table schema',      example:'DESCRIBE users' },
  { kw:'TRUNCATE',       desc:'Delete all rows',        example:'TRUNCATE TABLE users' },
  // ── Filtering
  { kw:'FILTER',         desc:'Filter rows (BOXDB)',     example:'FILTER age > 25 AND city = "delhi"' },
  { kw:'WHERE',          desc:'Filter rows (SQL)',       example:'WHERE age > 25 AND city = "delhi"' },
  { kw:'AND',            desc:'Logical AND',            example:'FILTER age > 20 AND age < 30' },
  { kw:'OR',             desc:'Logical OR',             example:'FILTER city = "delhi" OR city = "mumbai"' },
  { kw:'LIKE',           desc:'Pattern match (%=any)',  example:'FILTER name LIKE "A%"' },
  { kw:'IN',             desc:'Match value in list',    example:'FILTER id IN (1, 2, 3)' },
  { kw:'BETWEEN',        desc:'Range check',            example:'FILTER age BETWEEN 20 AND 30' },
  { kw:'IS NULL',        desc:'Check for null',         example:'FILTER email IS NULL' },
  { kw:'IS NOT NULL',    desc:'Check not null',         example:'FILTER email IS NOT NULL' },
  // ── Sorting / Pagination
  { kw:'ORDER BY',       desc:'Sort results',           example:'ORDER BY age DESC' },
  { kw:'LIMIT',          desc:'Cap number of rows',     example:'LIMIT 10 OFFSET 0' },
  { kw:'DISTINCT',       desc:'Remove duplicates',      example:'GET DISTINCT city FROM users' },
  // ── JOINs
  { kw:'JOIN',           desc:'Inner join',             example:'JOIN orders ON users.id = orders.user_id' },
  { kw:'LEFT JOIN',      desc:'Left outer join',        example:'LEFT JOIN orders ON users.id = orders.user_id' },
  { kw:'RIGHT JOIN',     desc:'Right outer join',       example:'RIGHT JOIN orders ON users.id = orders.user_id' },
  // ── Grouping
  { kw:'GROUP BY',       desc:'Group rows',             example:'GROUP BY city' },
  { kw:'HAVING',         desc:'Filter groups',          example:'HAVING COUNT(*) > 1' },
  // ── Aggregates
  { kw:'COUNT',          desc:'Count rows',             example:'GET COUNT(*) AS total FROM users' },
  { kw:'SUM',            desc:'Sum values',             example:'GET SUM(price) AS revenue FROM orders' },
  { kw:'AVG',            desc:'Average values',         example:'GET AVG(age) AS avg_age FROM users' },
  { kw:'MAX',            desc:'Maximum value',          example:'GET MAX(price) AS max_price FROM orders' },
  { kw:'MIN',            desc:'Minimum value',          example:'GET MIN(price) AS min_price FROM orders' },
  // ── ALTER sub-commands
  { kw:'ADD COLUMN',     desc:'Add a column',           example:'ALTER TABLE users ADD COLUMN email TEXT' },
  { kw:'DROP COLUMN',    desc:'Remove a column',        example:'ALTER TABLE users DROP COLUMN email' },
  { kw:'RENAME COLUMN',  desc:'Rename a column',        example:'ALTER TABLE users RENAME COLUMN name TO full_name' },
];

// ─── State ────────────────────────────────────────────────────────────────────
let tabs = [];
let activeTabId = null;
let tabCounter = 0;
let queryHistory = [];
let currentResults = { rows: [], columns: [] };
let sortState = { column: null, direction: 'asc' };
let autocompleteEl = null;
let tables = [];

// ─── DOM References ───────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);
const queryEditor = $('query-editor');
const lineNumbers = $('line-numbers');
const highlightEl = $('editor-highlight');
const tabsList = $('tabs-list');
const resultsPlaceholder = $('results-placeholder');
const resultsTableWrap = $('results-table-wrap');
const resultsThead = $('results-thead');
const resultsTbody = $('results-tbody');
const errorPanel = $('error-panel');
const errorText = $('error-text');
const resultsMeta = $('results-meta');
const historyList = $('history-list');
const historyCount = $('history-count');
const messagesList = $('messages-list');
const tableList = $('table-list');
const tableCountBadge = $('table-count-badge');
const loadingOverlay = $('loading-overlay');
const toast = $('toast');
const cursorPos = $('cursor-pos');
const charCount = $('char-count');
const statusMsg = $('status-msg');
const execTime = $('exec-time');
const schemaPopup = $('schema-popup');
const schemaPopupTitle = $('schema-popup-title');
const schemaPopupBody = $('schema-popup-body');

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  initWindowControls();
  initTabs();
  initEditor();
  initToolbar();
  initResultsTabs();
  initSidebar();
  initResizer();
  initSchemaPopup();
  await refreshTables();
});

// ─── Window Controls ──────────────────────────────────────────────────────────
function initWindowControls() {
  if (window.minidb?.minimize) {
    $('btn-minimize').onclick = () => window.minidb.minimize();
    $('btn-maximize').onclick = () => window.minidb.maximize();
    $('btn-close').onclick = () => window.minidb.close();
  }
}

// ─── Tabs ─────────────────────────────────────────────────────────────────────
function initTabs() {
  createTab('Query 1');
  $('btn-add-tab').onclick = () => createTab(`Query ${tabs.length + 1}`);
}

function createTab(name = 'New Query') {
  const id = ++tabCounter;
  const tab = {
    id,
    name,
    query: '',
    results: { rows: [], columns: [] },
    error: null,
    message: null,
  };
  tabs.push(tab);
  renderTabStrip();
  activateTab(id);
}

function renderTabStrip() {
  tabsList.innerHTML = '';
  tabs.forEach((tab) => {
    const el = document.createElement('button');
    el.className = 'tab' + (tab.id === activeTabId ? ' active' : '');
    el.dataset.tabId = tab.id;
    el.innerHTML = `
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
      ${escHtml(tab.name)}
      <button class="tab-close" data-close-tab="${tab.id}" title="Close tab">✕</button>
    `;
    el.onclick = (e) => {
      if (e.target.dataset.closeTab) return closeTab(parseInt(e.target.dataset.closeTab));
      activateTab(tab.id);
    };
    tabsList.appendChild(el);
  });
}

function activateTab(id) {
  // Save current editor content to old tab
  if (activeTabId !== null) {
    const old = tabs.find((t) => t.id === activeTabId);
    if (old) old.query = queryEditor.value;
  }

  activeTabId = id;
  const tab = tabs.find((t) => t.id === id);
  if (!tab) return;

  // Restore editor
  queryEditor.value = tab.query;
  updateLineNumbers();
  doSyntaxHighlight();
  updateEditorStats();

  // Restore results
  currentResults = tab.results;
  if (tab.error) {
    showError(tab.error);
  } else if (tab.results.rows.length > 0 || tab.message) {
    renderResults(tab.results.rows, tab.results.columns, tab.message);
  } else {
    showPlaceholder();
  }

  renderTabStrip();
}

function closeTab(id) {
  if (tabs.length === 1) {
    showToast('Cannot close last tab', 'warn');
    return;
  }
  const idx = tabs.findIndex((t) => t.id === id);
  tabs.splice(idx, 1);
  if (activeTabId === id) {
    activateTab(tabs[Math.max(0, idx - 1)].id);
  } else {
    renderTabStrip();
  }
}

// ─── Editor ───────────────────────────────────────────────────────────────────
function initEditor() {
  queryEditor.addEventListener('input', () => {
    updateLineNumbers();
    doSyntaxHighlight();
    updateEditorStats();
    showAutocomplete();
  });

  queryEditor.addEventListener('keydown', (e) => {
    // Run on Ctrl+Enter
    if (e.key === 'Enter' && e.ctrlKey) {
      e.preventDefault();
      runQuery();
      return;
    }
    // Tab inserts spaces
    if (e.key === 'Tab') {
      e.preventDefault();
      const start = queryEditor.selectionStart;
      const end = queryEditor.selectionEnd;
      queryEditor.value = queryEditor.value.substring(0, start) + '  ' + queryEditor.value.substring(end);
      queryEditor.selectionStart = queryEditor.selectionEnd = start + 2;
      doSyntaxHighlight();
      return;
    }
    // Hide autocomplete on Escape
    if (e.key === 'Escape') hideAutocomplete();
  });

  queryEditor.addEventListener('scroll', () => {
    lineNumbers.scrollTop = queryEditor.scrollTop;
  });

  queryEditor.addEventListener('click', updateEditorStats);
  queryEditor.addEventListener('keyup', updateEditorStats);
}

function updateLineNumbers() {
  const lines = queryEditor.value.split('\n').length;
  lineNumbers.textContent = Array.from({ length: lines }, (_, i) => i + 1).join('\n');
}

function updateEditorStats() {
  const val = queryEditor.value;
  const pos = queryEditor.selectionStart;
  const before = val.substring(0, pos);
  const lines = before.split('\n');
  const ln = lines.length;
  const col = lines[lines.length - 1].length + 1;
  cursorPos.textContent = `Ln ${ln}, Col ${col}`;
  charCount.textContent = `${val.length} chars`;
}

// ─── Syntax Highlighting ──────────────────────────────────────────────────────
function doSyntaxHighlight() {
  // We style the textarea text by rendering a mirrored overlay div
  // (simple approach: tokenise and color the editor directly via caret tricks)
  // For textarea-based syntax highlighting we use a lightweight approach.
  const text = queryEditor.value;
  const highlighted = tokenizeAndHighlight(text);
  highlightEl.innerHTML = highlighted;
}

function tokenizeAndHighlight(text) {
  const lines = text.split('\n');
  return lines
    .map((line) => {
      if (line.trimStart().startsWith('--')) {
        return `<span class="hl-comment">${escHtml(line)}</span>`;
      }
      const words = line.split(/(\s+|(?=[=!<>])|(?<=[=!<>]))/);
      return words
        .map((w) => {
          const upper = w.trim().toUpperCase();
          if (!upper) return escHtml(w);
          if (SYNTAX.commands.has(upper)) return `<span class="hl-keyword-cmd">${escHtml(w)}</span>`;
          if (SYNTAX.clauses.has(upper)) return `<span class="hl-keyword-clause">${escHtml(w)}</span>`;
          if (SYNTAX.types.has(upper)) return `<span class="hl-keyword-type">${escHtml(w)}</span>`;
          if (SYNTAX.operators.has(w.trim())) return `<span class="hl-operator">${escHtml(w)}</span>`;
          if (/^-?\d+(\.\d+)?$/.test(w.trim())) return `<span class="hl-number">${escHtml(w)}</span>`;
          return `<span class="hl-identifier">${escHtml(w)}</span>`;
        })
        .join('');
    })
    .join('\n');
}

// ─── Autocomplete ─────────────────────────────────────────────────────────────
function showAutocomplete() {
  const val = queryEditor.value;
  const pos = queryEditor.selectionStart;
  const wordStart = val.lastIndexOf(' ', pos - 1) + 1;
  const word = val.substring(wordStart, pos).toUpperCase();

  if (word.length < 1) { hideAutocomplete(); return; }

  const matches = AUTOCOMPLETE_SUGGESTIONS.filter((s) => s.kw.startsWith(word) && s.kw !== word);
  if (!matches.length) { hideAutocomplete(); return; }

  if (!autocompleteEl) {
    autocompleteEl = document.createElement('div');
    autocompleteEl.className = 'autocomplete-hint';
    document.body.appendChild(autocompleteEl);
  }

  // Position near cursor
  const rect = queryEditor.getBoundingClientRect();
  autocompleteEl.style.left = `${rect.left + 60}px`;
  autocompleteEl.style.top = `${rect.top + 40}px`;

  autocompleteEl.innerHTML = matches
    .slice(0, 6)
    .map(
      (m) =>
        `<div class="autocomplete-item" data-kw="${m.kw}">
          <span class="autocomplete-kw">${m.kw}</span>
          <span class="autocomplete-desc">${m.desc}</span>
        </div>`
    )
    .join('');

  autocompleteEl.querySelectorAll('.autocomplete-item').forEach((item) => {
    item.onclick = () => {
      const kw = item.dataset.kw;
      const currentVal = queryEditor.value;
      const before = currentVal.substring(0, wordStart);
      const after = currentVal.substring(pos);
      queryEditor.value = before + kw + ' ' + after;
      queryEditor.selectionStart = queryEditor.selectionEnd = wordStart + kw.length + 1;
      hideAutocomplete();
      doSyntaxHighlight();
    };
  });
}

function hideAutocomplete() {
  if (autocompleteEl) {
    autocompleteEl.remove();
    autocompleteEl = null;
  }
}

document.addEventListener('click', (e) => {
  if (autocompleteEl && !autocompleteEl.contains(e.target) && e.target !== queryEditor) {
    hideAutocomplete();
  }
});

// ─── Toolbar Buttons ──────────────────────────────────────────────────────────
function initToolbar() {
  $('btn-run').onclick = runQuery;
  $('btn-clear').onclick = clearEditor;
  $('btn-format').onclick = formatQuery;
  $('btn-export-csv').onclick = () => exportResults('csv');
  $('btn-export-json').onclick = () => exportResults('json');
}

function clearEditor() {
  queryEditor.value = '';
  updateLineNumbers();
  doSyntaxHighlight();
  updateEditorStats();
  queryEditor.focus();
}

function formatQuery() {
  const val = queryEditor.value.trim();
  if (!val) return;
  // Simple formatting: uppercase keywords, one clause per visual chunk
  const keywords = [...SYNTAX.commands, ...SYNTAX.clauses, ...SYNTAX.types];
  let formatted = val;
  keywords.forEach((kw) => {
    const re = new RegExp(`\\b${kw}\\b`, 'gi');
    formatted = formatted.replace(re, kw);
  });
  queryEditor.value = formatted;
  doSyntaxHighlight();
  showToast('Query formatted', 'success');
}

// ─── Run Query ────────────────────────────────────────────────────────────────
async function runQuery() {
  const query = queryEditor.value.trim();
  if (!query) { showToast('Please enter a query', 'warn'); return; }

  // Save tab state
  const tab = tabs.find((t) => t.id === activeTabId);
  if (tab) tab.query = query;

  // Update tab name from first keyword
  const firstWord = query.split(/\s+/)[0].toUpperCase();
  if (tab && SYNTAX.commands.has(firstWord)) {
    tab.name = `${firstWord} · ${tabCounter}`;
    renderTabStrip();
  }

  setStatus('running', '● Executing…');
  showLoading(true);
  const startTime = Date.now();

  try {
    const result = await window.minidb.executeQuery(query);
    const duration = Date.now() - startTime;

    addHistoryItem(query, result.success, duration);
    addMessage(
      result.success
        ? `Query OK · ${result.message || `${result.rows.length} rows`} · ${duration}ms`
        : `Error: ${result.error}`,
      result.success ? 'success' : 'error'
    );

    if (result.success) {
      setStatus('success', `✓ ${result.message || result.rows.length + ' rows'}`);
      execTime.textContent = `${duration}ms`;

      if (tab) {
        tab.results = { rows: result.rows, columns: result.columns };
        tab.error = null;
        tab.message = result.message;
      }
      currentResults = { rows: result.rows, columns: result.columns };
      renderResults(result.rows, result.columns, result.message);
      await refreshTables();
    } else {
      setStatus('error', '✕ Error');
      if (tab) { tab.results = { rows: [], columns: [] }; tab.error = result.error; }
      showError(result.error);
    }
  } catch (err) {
    setStatus('error', '✕ Failed');
    showError(err.message);
    addMessage(`Fatal: ${err.message}`, 'error');
  } finally {
    showLoading(false);
  }
}

// ─── Results Rendering ────────────────────────────────────────────────────────
function renderResults(rows, columns, message) {
  resultsPlaceholder.style.display = 'none';
  errorPanel.style.display = 'none';

  if (rows.length === 0) {
    // Show message (INSERT/UPDATE/DELETE etc.)
    resultsTableWrap.style.display = 'none';
    resultsPlaceholder.style.display = 'flex';
    resultsPlaceholder.innerHTML = `
      <div class="placeholder-icon" style="color: var(--accent-green); opacity: 0.7;">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <polyline points="20 6 9 17 4 12"/>
        </svg>
      </div>
      <p style="color: var(--accent-green); font-size: 13px;">${escHtml(message || 'Query executed successfully')}</p>
    `;
    resultsMeta.textContent = '';
    disableExport(true);
    return;
  }

  // Render table
  resultsTableWrap.style.display = 'block';
  resultsMeta.textContent = `${rows.length} row${rows.length !== 1 ? 's' : ''} · ${columns.length} col${columns.length !== 1 ? 's' : ''}`;

  // Header
  resultsThead.innerHTML = `<tr>${columns
    .map(
      (col, i) =>
        `<th data-col="${i}" title="Click to sort">${escHtml(col)}</th>`
    )
    .join('')}</tr>`;

  // Body
  renderTableBody(rows, columns);
  disableExport(false);

  // Sort on header click
  resultsThead.querySelectorAll('th').forEach((th) => {
    th.onclick = () => {
      const col = columns[parseInt(th.dataset.col)];
      if (sortState.column === col) {
        sortState.direction = sortState.direction === 'asc' ? 'desc' : 'asc';
      } else {
        sortState.column = col;
        sortState.direction = 'asc';
      }
      resultsThead.querySelectorAll('th').forEach((t) => t.classList.remove('sort-asc', 'sort-desc'));
      th.classList.add(sortState.direction === 'asc' ? 'sort-asc' : 'sort-desc');

      const sorted = [...rows].sort((a, b) => {
        const va = a[col] ?? '';
        const vb = b[col] ?? '';
        if (typeof va === 'number' && typeof vb === 'number') {
          return sortState.direction === 'asc' ? va - vb : vb - va;
        }
        return sortState.direction === 'asc'
          ? String(va).localeCompare(String(vb))
          : String(vb).localeCompare(String(va));
      });
      renderTableBody(sorted, columns);
    };
  });
}

function renderTableBody(rows, columns) {
  resultsTbody.innerHTML = rows
    .map(
      (row) =>
        `<tr>${columns
          .map((col) => {
            const val = row[col];
            const cls = getCellClass(val);
            const display = val === null || val === undefined ? 'NULL' : String(val);
            return `<td class="${cls}" title="${escHtml(display)}">${escHtml(display)}</td>`;
          })
          .join('')}</tr>`
    )
    .join('');
}

function getCellClass(val) {
  if (val === null || val === undefined) return 'type-null';
  if (typeof val === 'boolean') return val ? 'type-bool-true' : 'type-bool-false';
  if (Number.isInteger(val)) return 'type-int';
  if (typeof val === 'number') return 'type-float';
  return '';
}

function showError(msg) {
  resultsTableWrap.style.display = 'none';
  resultsPlaceholder.style.display = 'none';
  errorPanel.style.display = 'flex';
  errorText.textContent = msg;
  resultsMeta.textContent = '';
  disableExport(true);
}

function showPlaceholder() {
  resultsTableWrap.style.display = 'none';
  errorPanel.style.display = 'none';
  resultsPlaceholder.style.display = 'flex';
  resultsPlaceholder.innerHTML = `
    <div class="placeholder-icon">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
        <ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v4.5c0 1.657 4.03 3 9 3s9-1.343 9-3V5"/>
        <path d="M3 9.5v4.5c0 1.657 4.03 3 9 3s9-1.343 9-3V9.5"/>
        <path d="M3 14v4.5c0 1.657 4.03 3 9 3s9-1.343 9-3V14"/>
      </svg>
    </div>
    <p>Run a query to see results here</p>
  `;
  disableExport(true);
}

function disableExport(disabled) {
  $('btn-export-csv').disabled = disabled;
  $('btn-export-json').disabled = disabled;
}

// ─── Results Tabs ─────────────────────────────────────────────────────────────
function initResultsTabs() {
  document.querySelectorAll('.res-tab').forEach((tab) => {
    tab.onclick = () => {
      document.querySelectorAll('.res-tab').forEach((t) => t.classList.remove('active'));
      document.querySelectorAll('.res-panel').forEach((p) => p.classList.remove('active'));
      tab.classList.add('active');
      $(`${tab.dataset.panel}`).classList.add('active');
    };
  });
}

// ─── History ──────────────────────────────────────────────────────────────────
function addHistoryItem(query, success, duration) {
  const item = {
    query,
    success,
    duration,
    time: new Date(),
  };
  queryHistory.unshift(item);
  if (queryHistory.length > 100) queryHistory.pop();
  renderHistory();
}

function renderHistory() {
  historyCount.textContent = `${queryHistory.length} queries`;
  if (!queryHistory.length) {
    historyList.innerHTML = '<div class="table-empty">No query history yet</div>';
    return;
  }
  historyList.innerHTML = queryHistory
    .map(
      (item, idx) => `
      <div class="history-item" data-idx="${idx}">
        <div class="history-status ${item.success ? 'ok' : 'err'}"></div>
        <div class="history-query">${escHtml(item.query)}</div>
        <div class="history-item-meta">
          <span class="history-time">${formatTime(item.time)}</span>
          <span class="history-duration">${item.duration}ms</span>
        </div>
      </div>
    `
    )
    .join('');

  historyList.querySelectorAll('.history-item').forEach((el) => {
    el.onclick = () => {
      const item = queryHistory[parseInt(el.dataset.idx)];
      queryEditor.value = item.query;
      updateLineNumbers();
      doSyntaxHighlight();
      updateEditorStats();
      // Switch to results tab
      $('tab-results').click();
      queryEditor.focus();
    };
  });
}

$('btn-clear-history').onclick = () => {
  queryHistory = [];
  renderHistory();
};

// ─── Messages ─────────────────────────────────────────────────────────────────
function addMessage(text, type = 'info') {
  const item = document.createElement('div');
  item.className = `message-item ${type}`;
  item.innerHTML = `<span class="msg-time">${formatTime(new Date())}</span><span class="msg-text">${escHtml(text)}</span>`;
  messagesList.appendChild(item);
  messagesList.scrollTop = messagesList.scrollHeight;
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────
function initSidebar() {
  $('btn-refresh-tables').onclick = refreshTables;

  document.querySelectorAll('.quick-cmd').forEach((btn) => {
    btn.onclick = () => {
      const q = btn.dataset.query;
      queryEditor.value = q;
      updateLineNumbers();
      doSyntaxHighlight();
      updateEditorStats();
      queryEditor.focus();
      const doubleSpaceIdx = q.indexOf('  ');
      if (doubleSpaceIdx !== -1) {
        queryEditor.selectionStart = queryEditor.selectionEnd = doubleSpaceIdx + 1;
      } else {
        queryEditor.selectionStart = queryEditor.selectionEnd = q.length;
      }
    };
  });
}

async function refreshTables() {
  try {
    const result = await window.minidb.listTables();
    if (!result.success) return;
    tables = result.tables;
    renderTableList(tables);
  } catch (e) {
    console.error('Failed to list tables:', e);
  }
}

function renderTableList(tables) {
  tableCountBadge.textContent = tables.length;
  if (!tables.length) {
    tableList.innerHTML = '<div class="table-empty">No tables found</div>';
    return;
  }
  tableList.innerHTML = tables
    .map(
      (t) => `
      <div class="table-item" data-table="${t.name}">
        <svg class="table-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/>
          <line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="3" x2="9" y2="21"/>
        </svg>
        <div class="table-info">
          <div class="table-name">${escHtml(t.name)}</div>
          <div class="table-rows">${t.rowCount} rows</div>
        </div>
        ${t.schema ? `<button class="table-schema-btn" data-table="${t.name}">schema</button>` : ''}
      </div>
    `
    )
    .join('');

  tableList.querySelectorAll('.table-item').forEach((el) => {
    el.onclick = (e) => {
      if (e.target.classList.contains('table-schema-btn')) return;
      const tableName = el.dataset.table;
      queryEditor.value = `GET * FROM ${tableName}`;
      updateLineNumbers();
      doSyntaxHighlight();
      updateEditorStats();
      queryEditor.focus();
    };
  });

  tableList.querySelectorAll('.table-schema-btn').forEach((btn) => {
    btn.onclick = (e) => {
      e.stopPropagation();
      showSchemaPopup(btn.dataset.table);
    };
  });
}

// ─── Schema Popup ─────────────────────────────────────────────────────────────
function initSchemaPopup() {
  $('schema-popup-close').onclick = () => {
    schemaPopup.style.display = 'none';
  };
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') schemaPopup.style.display = 'none';
  });
}

function showSchemaPopup(tableName) {
  const table = tables.find((t) => t.name === tableName);
  if (!table || !table.schema) return;

  schemaPopupTitle.textContent = `${tableName} · Schema`;
  schemaPopupBody.innerHTML = Object.entries(table.schema)
    .map(
      ([col, type]) => `
      <div class="schema-row">
        <span class="schema-col-name">${escHtml(col)}</span>
        <span class="schema-type-badge type-${type}">${type}</span>
      </div>
    `
    )
    .join('');

  schemaPopup.style.display = 'block';
}

// ─── Export ───────────────────────────────────────────────────────────────────
async function exportResults(format) {
  if (!currentResults.rows.length) return;
  try {
    const result = await window.minidb.exportResults({
      format,
      data: currentResults.rows,
      columns: currentResults.columns,
    });
    if (result.success) {
      showToast(`Exported to ${result.filePath.split('\\').pop()}`, 'success');
      addMessage(`Exported ${currentResults.rows.length} rows as ${format.toUpperCase()} to ${result.filePath}`, 'success');
    } else {
      showToast(result.error, 'error');
    }
  } catch (e) {
    showToast(e.message, 'error');
  }
}

// ─── Pane Resizer ─────────────────────────────────────────────────────────────
function initResizer() {
  const editorPane = document.querySelector('.editor-pane');
  const mainArea = document.querySelector('.main-area');

  // Insert resizer element between editor and results
  const resizer = document.createElement('div');
  resizer.className = 'pane-resizer';
  editorPane.after(resizer);

  let startY, startH;

  resizer.addEventListener('mousedown', (e) => {
    startY = e.clientY;
    startH = editorPane.getBoundingClientRect().height;
    document.body.style.cursor = 'ns-resize';
    document.body.style.userSelect = 'none';

    const onMove = (e) => {
      const delta = e.clientY - startY;
      const newH = Math.max(120, Math.min(startH + delta, mainArea.clientHeight - 200));
      editorPane.style.height = newH + 'px';
    };
    const onUp = () => {
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });
}

// ─── Status & Utilities ───────────────────────────────────────────────────────
function setStatus(type, msg) {
  statusMsg.textContent = msg;
  statusMsg.className = `status-${type}`;
}

function showLoading(visible) {
  loadingOverlay.style.display = visible ? 'flex' : 'none';
}

let toastTimer = null;
function showToast(msg, type = 'info') {
  toast.textContent = msg;
  toast.className = `toast ${type} show`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.className = 'toast'; }, 3000);
}

function formatTime(date) {
  return date.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function escHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
