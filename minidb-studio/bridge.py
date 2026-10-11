#!/usr/bin/env python3
"""
bridge.py — MiniDB ↔ Electron bridge script.
Reads one query from stdin, executes it via MiniDB engine, returns JSON to stdout.
"""
import io
import json
import os
import sys

# Ensure UTF-8 I/O on Windows
if sys.platform == "win32":
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Resolve absolute path to miniDB root
if len(sys.argv) > 1 and sys.argv[1]:
    script_dir = os.path.abspath(sys.argv[1])
else:
    candidate = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'miniDB'))
    if os.path.exists(candidate):
        script_dir = candidate
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))

if script_dir not in sys.path:
    sys.path.insert(0, script_dir)
os.chdir(script_dir)  # Ensure StorageEngine finds data/ dir

try:
    from minidb.lexer import tokenize  # type: ignore # noqa: E402
    from minidb.parser import Parser  # type: ignore # noqa: E402
    from minidb.engine import ExecutionEngine  # type: ignore # noqa: E402
except ImportError:
    from miniDB.minidb.lexer import tokenize  # type: ignore # noqa: E402
    from miniDB.minidb.parser import Parser  # type: ignore # noqa: E402
    from miniDB.minidb.engine import ExecutionEngine  # type: ignore # noqa: E402


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