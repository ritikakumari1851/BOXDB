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
