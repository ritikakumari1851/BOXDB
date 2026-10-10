# BOXDB (MiniDB & MiniDB Studio)

A lightweight, high-performance relational database engine built from scratch in Python, paired with a modern desktop GUI ("MiniDB Studio") built using Electron. 

BOXDB delivers a MySQL-like experience powered by its own custom query language: **BOX-QQL** (**B**inary **O**ptimized e**X**ecution **Q**uery and **Q**ualification **L**anguage).

---

## 🚀 Key Features

* **Custom Query Language (BOX-QQL):** Supports an intuitive, minimalist command syntax alongside standard SQL aliases (`GET`/`SELECT`, `ADD`/`INSERT`, `CHANGE`/`UPDATE`, `REMOVE`/`DELETE`, `BUILD`/`CREATE`).
* **High-Performance In-Memory Indexing:** $O(1)$ Hash Indexing implementation for lightning-fast lookups on indexed columns.
* **Relational Joins & Aggregations:** Supports complex multi-table joins (`INNER`, `LEFT`, `RIGHT`, `OUTER`, `CROSS`) and aggregate computations (`COUNT`, `SUM`, `AVG`, `MAX`, `MIN`).
* **Persistent JSON Storage:** Stores table schemas and row records cleanly within a local `/data` directory structure.
* **Electron Desktop Studio:** A sleek, dark-themed GUI featuring an interactive query editor, live table navigator, schema explorer, and quick results exporter (CSV/JSON).

---

## 🏗️ Project Architecture

BOXDB/
├── miniDB/                 # Core Python Database Engine
│   ├── data/               # Local JSON storage & schema files
│   ├── minidb/             # Engine modules (lexer, parser, engine, storage, index, formatter)
│   └── main.py             # CLI entry point
└── minidb-studio/          # Electron Desktop GUI
    ├── renderer/           # HTML, CSS, and Frontend JavaScript app
    ├── main.js             # Electron main process & IPC handlers
    ├── preload.js          # Secure context bridge implementation
    └── bridge.py           # Python-to-Electron standard I/O communication script
🛠️ Getting Setup & Running Prerequisites Python 3.10+
installed on your system.Node.js & npm installed for running the Electron GUI.
Installation & Execution 
Clone the repository:git clone https://github.com/ritikakumari1851/BOXDB.git
cd BOXDB

Launch the Electron Desktop Studio:cd minidb-studio
npm install
npm start

📖 BOX-QQL Quick ReferenceOperation
Native CommandSQL Alias EquivalentExampleRetrieve Data
GETSELECTGET name, salary FROM employees FILTER salary > 50000;
Insert Data ADDINSERT
ADD INTO employees VALUES 1, "Alice", 75000;
Update DataCHANGEUPDATECHANGE employees SET salary = 80000 FILTER id = 1;
Delete DataREMOVEDELETEREMOVE FROM employees FILTER id = 1;
Create SchemaBUILDCREATEBUILD TABLE employees WITH id INT, name TEXT, salary FLOAT;
Create IndexINDEXCREATE INDEXINDEX employees ON id;
📄 Documentation For the complete language specification, syntax guides, advanced filtering predicates (LIKE, IN, BETWEEN), 
and aggregate functions, refer to the included BOX-QQL Reference Manual.
