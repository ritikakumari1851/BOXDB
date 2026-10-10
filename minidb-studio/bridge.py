#!/usr/bin/env python3
"""
bridge.py — MiniDB ↔ Electron bridge script.
Reads one query from stdin, executes it via MiniDB engine, returns JSON to stdout.
"""
import sys
import json
import os

# Add miniDB parent to path so imports work
script_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)
os.chdir(script_dir)  # Ensure StorageEngine finds data/ dir

from minidb.lexer import tokenize
from minidb.parser import Parser
from minidb.engine import ExecutionEngine
from minidb.formatter import TableFormatter

def main():
    engine = ExecutionEngine()
    query = sys.stdin.read().strip()

    if not query:
        print(json.dumps({"success": False, "error": "Empty query", "rows": [], "columns": [], "message": None}))
        return

    try:
        tokens = tokenize(query)
        parser = Parser(tokens)
        ast = parser.parse()
        results = engine.execute(ast)

        if isinstance(results, list):
            columns = list(dict.fromkeys(k for row in results for k in row.keys())) if results else []
            print(json.dumps({
                "success": True,
                "rows": results,
                "columns": columns,
                "message": f"{len(results)} row(s) returned",
                "error": None
            }))
        else:
            # Status message from INSERT/UPDATE/DELETE/CREATE
            print(json.dumps({
                "success": True,
                "rows": [],
                "columns": [],
                "message": str(results),
                "error": None
            }))
    except Exception as e:
        print(json.dumps({
            "success": False,
            "error": str(e),
            "rows": [],
            "columns": [],
            "message": None
        }))

if __name__ == "__main__":
    main()