"""
storage.py — BOXDB Storage Engine
Handles JSON-based table I/O, schema management, indexes, and drop/alter support.
"""

import json
import os
from minidb.index import HashIndex


class StorageEngine:
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            # Default to data folder inside miniDB directory regardless of current working directory
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(base_dir, "data")
        self.data_dir = data_dir
        self.indexes: dict[str, dict[str, HashIndex]] = {}
        os.makedirs(data_dir, exist_ok=True)

    # ── Path helpers ─────────────────────────────────────────────────────────

    def _table_path(self, table_name: str) -> str:
        return os.path.join(self.data_dir, f"{table_name}.json")

    def _schema_path(self) -> str:
        return os.path.join(self.data_dir, "_schema.json")

    # ── Table I/O ─────────────────────────────────────────────────────────────

    def read_table(self, table_name: str) -> list[dict]:
        path = self._table_path(table_name)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Table '{table_name}' does not exist.")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            return json.loads(content)

    def write_table(self, table_name: str, data: list[dict]):
        with open(self._table_path(table_name), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def list_tables(self) -> list[str]:
        """Return list of all existing table names from schema and data files."""
        tables = set()
        schemas = self.read_schemas()
        for k in schemas:
            if not k.startswith("_"):
                tables.add(k)
        if os.path.exists(self.data_dir):
            for f in os.listdir(self.data_dir):
                if f.endswith(".json") and not f.startswith("_"):
                    tables.add(f[:-5])
        return sorted(tables)

    def drop_table(self, table_name: str):
        """Delete table file, remove from schema, clear indexes."""
        path = self._table_path(table_name)
        if os.path.exists(path):
            os.remove(path)
        schemas = self.read_schemas()
        if table_name in schemas:
            schemas.pop(table_name, None)
            self.write_schemas(schemas)
        self.indexes.pop(table_name, None)

    # ── Schema I/O ───────────────────────────────────────────────────────────

    def read_schemas(self) -> dict:
        path = self._schema_path()
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def write_schemas(self, schemas: dict):
        with open(self._schema_path(), "w", encoding="utf-8") as f:
            json.dump(schemas, f, indent=2)

    def write_schema(self, table_name: str, schema: dict):
        schemas = self.read_schemas()
        schemas[table_name] = schema
        self.write_schemas(schemas)

    def create_table_file(self, table_name: str, schema: dict):
        """Legacy helper used by old CREATE TABLE path."""
        path = self._table_path(table_name)
        if os.path.exists(path):
            raise FileExistsError(f"Table '{table_name}' already exists.")
        self.write_table(table_name, [])
        self.write_schema(table_name, schema)

    # ── Index Management ─────────────────────────────────────────────────────

    def create_index(self, table_name: str, column_name: str):
        rows = self.read_table(table_name)
        idx = HashIndex(column_name)
        idx.build(rows)
        self.indexes.setdefault(table_name, {})[column_name] = idx

    def get_index(self, table_name: str, column_name: str) -> "HashIndex | None":
        return self.indexes.get(table_name, {}).get(column_name)
