"""
engine.py — BOXDB Execution Engine
Full SELECT pipeline: JOINs → WHERE → GROUP BY → HAVING → PROJECT → DISTINCT
                      → ORDER BY → LIMIT/OFFSET
Supports: aggregates, LIKE, IN, BETWEEN, IS NULL, AND/OR/NOT, multiple JOINs,
          AUTO_INCREMENT, NOT NULL, UNIQUE, DEFAULT, ALTER TABLE, DROP TABLE,
          SHOW TABLES, DESCRIBE, TRUNCATE.
"""

import re
from minidb.storage import StorageEngine


class ExecutionEngine:
    def __init__(self):
        self.storage = StorageEngine()

    def execute(self, ast: dict):
        handlers = {
            "SELECT":       self._exec_select,
            "INSERT":       self._exec_insert,
            "UPDATE":       self._exec_update,
            "DELETE":       self._exec_delete,
            "CREATE_TABLE": self._exec_create_table,
            "DROP_TABLE":   self._exec_drop_table,
            "ALTER_TABLE":  self._exec_alter_table,
            "CREATE_INDEX": self._exec_create_index,
            "SHOW_TABLES":  self._exec_show_tables,
            "DESCRIBE":     self._exec_describe,
            "TRUNCATE":     self._exec_truncate,
        }
        handler = handlers.get(ast["type"])
        if not handler:
            raise NotImplementedError(f"Action '{ast['type']}' not supported.")
        return handler(ast)

    # ══════════════════════════════════════════════════════════════════════════
    # Shared helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _row_val(self, row: dict, col_ref: str):
        """Resolve a column reference (table.col or col) from a combined row."""
        if col_ref in row:
            return row[col_ref]
        # fallback: match any key ending in ".col_ref"
        suffix = '.' + col_ref
        for k, v in row.items():
            if k.endswith(suffix):
                return v
        return None

    def _eval_cond(self, row: dict, cond: dict) -> bool:
        """Recursively evaluate a condition node against a row."""
        if cond is None:
            return True
        t = cond["type"]

        if t == "AND":
            return self._eval_cond(row, cond["left"]) and self._eval_cond(row, cond["right"])
        if t == "OR":
            return self._eval_cond(row, cond["left"]) or self._eval_cond(row, cond["right"])
        if t == "NOT":
            return not self._eval_cond(row, cond["operand"])
        if t == "IS_NULL":
            return self._row_val(row, cond["col"]) is None
        if t == "IS_NOT_NULL":
            return self._row_val(row, cond["col"]) is not None
        if t == "TRUTHY":
            return bool(self._row_val(row, cond["col"]))

        if t == "BETWEEN":
            v = self._row_val(row, cond["col"])
            return v is not None and cond["low"] <= v <= cond["high"]

        if t == "IN":
            v = self._row_val(row, cond["col"])
            return v in cond["values"]

        if t == "COMPARE":
            col_v = self._row_val(row, cond["col"])
            cmp_v = cond["value"]
            op = cond["op"]

            # Numeric coercion
            if col_v is not None and cmp_v is not None:
                if isinstance(col_v, (int, float)) and isinstance(cmp_v, str):
                    try:
                        cmp_v = type(col_v)(cmp_v)
                    except (ValueError, TypeError):
                        pass
                elif isinstance(cmp_v, (int, float)) and isinstance(col_v, str):
                    try:
                        col_v = type(cmp_v)(col_v)
                    except (ValueError, TypeError):
                        pass

            if op == "=":   return col_v == cmp_v
            if op == "!=":  return col_v != cmp_v
            if op == ">":   return col_v is not None and cmp_v is not None and col_v > cmp_v
            if op == "<":   return col_v is not None and cmp_v is not None and col_v < cmp_v
            if op == ">=":  return col_v is not None and cmp_v is not None and col_v >= cmp_v
            if op == "<=":  return col_v is not None and cmp_v is not None and col_v <= cmp_v
            if op == "LIKE":
                if col_v is None:
                    return False
                pat = re.escape(str(cmp_v)).replace(r'\%', '.*').replace(r'\_', '.').replace('%', '.*').replace('_', '.')
                return bool(re.match('^' + pat + '$', str(col_v), re.IGNORECASE))

        return True

    def _cast(self, val, expected_type: str):
        """Validate and cast a value to the expected column type."""
        if val is None:
            return None
        norm = expected_type.upper().strip()
        val_str = str(val)
        if norm == "INT":
            try:
                return int(float(val_str))
            except (ValueError, TypeError):
                raise TypeError(f"Value '{val}' is not a valid INT")
        if norm == "FLOAT":
            try:
                return float(val_str)
            except (ValueError, TypeError):
                raise TypeError(f"Value '{val}' is not a valid FLOAT")
        if norm == "BOOL":
            if val_str.lower() in ("true", "1", "yes"):
                return True
            if val_str.lower() in ("false", "0", "no"):
                return False
            raise TypeError(f"Value '{val}' is not a valid BOOL")
        if norm == "TEXT":
            return str(val)
        return val

    def _schema_of(self, table_name: str):
        """Return (column_dict, meta_dict) for table, handling old schema format."""
        schemas = self.storage.read_schemas()
        raw = schemas.get(table_name, {})
        meta = raw.get("_meta", {})
        cols = {k: v for k, v in raw.items() if not k.startswith("_")}
        return cols, meta

    # ══════════════════════════════════════════════════════════════════════════
    # SELECT
    # ══════════════════════════════════════════════════════════════════════════

    def _exec_select(self, ast: dict) -> list:
        primary = ast["table"]
        rows = self.storage.read_table(primary)
        fields = ast.get("fields", [{"type": "STAR"}])

        # 1. JOINs
        for join in ast.get("joins", []):
            rows = self._apply_join(rows, primary, join)
        # Backward compat: legacy 'join' key (single join)
        if ast.get("join") and not ast.get("joins"):
            rows = self._apply_join(rows, primary, ast["join"])

        # 2. WHERE
        if ast.get("where"):
            rows = [r for r in rows if self._eval_cond(r, ast["where"])]

        # 3. GROUP BY + aggregates
        has_agg = any(
            isinstance(f, dict) and f.get("type") == "AGGREGATE"
            for f in fields
        )
        group_by = ast.get("group_by", [])
        if has_agg or group_by:
            rows = self._apply_group(rows, fields, group_by)
            if ast.get("having"):
                rows = [r for r in rows if self._eval_cond(r, ast["having"])]
        else:
            # Normal field projection
            rows = self._project(rows, fields)

        # 4. DISTINCT
        if ast.get("distinct"):
            seen, unique = [], []
            for row in rows:
                key = tuple(sorted(row.items()))
                if key not in seen:
                    seen.append(key)
                    unique.append(row)
            rows = unique

        # 5. ORDER BY
        def _sort_key(r, col):
            v = self._row_val(r, col)
            if v is None:
                return (1, 0, "")
            if isinstance(v, (int, float)):
                return (0, 0, v)
            return (0, 1, str(v))

        for item in reversed(ast.get("order_by", [])):
            col = item["col"]
            rev = item["direction"] == "DESC"
            rows.sort(key=lambda r: _sort_key(r, col), reverse=rev)

        # 6. LIMIT / OFFSET
        offset = ast.get("offset") or 0
        limit = ast.get("limit")
        if offset:
            rows = rows[offset:]
        if limit is not None:
            rows = rows[:limit]

        return rows

    def _apply_join(self, left_rows, left_table, join_info) -> list:
        jtype = join_info.get("join_type", "INNER")
        jtable = join_info.get("joined_table")
        right_rows = self.storage.read_table(jtable)

        lk = (join_info.get("left_key") or "").split(".")[-1]
        rk = (join_info.get("right_key") or "").split(".")[-1]

        def merge(lrow, rrow):
            out = {}
            for k, v in lrow.items():
                out[k] = v
                if '.' not in k:
                    out[f"{left_table}.{k}"] = v
            for k, v in rrow.items():
                prefixed = f"{jtable}.{k}"
                out[prefixed] = v
                if k not in out:
                    out[k] = v
            return out

        result = []
        matched_right = set()

        for lrow in left_rows:
            matched = False
            for idx, rrow in enumerate(right_rows):
                lval = lrow.get(lk) if lk else None
                rval = rrow.get(rk) if rk else None
                if jtype == "CROSS" or lval == rval:
                    result.append(merge(lrow, rrow))
                    matched_right.add(idx)
                    matched = True
            # LEFT JOIN: emit unmatched left rows with NULLs for right cols
            if jtype == "LEFT" and not matched:
                null_right = {f"{jtable}.{k}": None for k in (right_rows[0].keys() if right_rows else [])}
                result.append({**lrow, **{k: v for k, v in lrow.items()
                                           if '.' not in k and f"{left_table}.{k}" not in lrow},
                                **null_right})

        # RIGHT JOIN: emit unmatched right rows with NULLs for left cols
        if jtype == "RIGHT":
            for idx, rrow in enumerate(right_rows):
                if idx not in matched_right:
                    null_left = {f"{left_table}.{k}": None for k in (left_rows[0].keys() if left_rows else [])}
                    out = dict(null_left)
                    for k, v in rrow.items():
                        out[f"{jtable}.{k}"] = v
                        out[k] = v
                    result.append(out)

        return result

    def _apply_group(self, rows, fields, group_cols) -> list:
        # Bucket rows into groups
        groups: dict = {}
        if group_cols:
            for row in rows:
                key = tuple(self._row_val(row, c) for c in group_cols)
                groups.setdefault(key, []).append(row)
        else:
            groups[None] = rows  # single global group

        agg_funcs = {
            "COUNT": lambda col, g: (len(g) if col == "*"
                                     else sum(1 for r in g if self._row_val(r, col) is not None)),
            "SUM":   lambda col, g: (sum(v for r in g if (v := self._row_val(r, col)) is not None) or None),
            "AVG":   lambda col, g: (
                (s := [v for r in g if (v := self._row_val(r, col)) is not None])
                and sum(s) / len(s) or None
            ),
            "MAX":   lambda col, g: (
                max((self._row_val(r, col) for r in g if self._row_val(r, col) is not None), default=None)
            ),
            "MIN":   lambda col, g: (
                min((self._row_val(r, col) for r in g if self._row_val(r, col) is not None), default=None)
            ),
        }

        result = []
        for key, grp in groups.items():
            new_row = {}
            # Include GROUP BY columns
            if group_cols and key is not None:
                for col, val in zip(group_cols, key):
                    new_row[col] = val
            # Compute each field
            for f in fields:
                if not isinstance(f, dict):
                    continue
                if f["type"] == "AGGREGATE":
                    func = f["func"]
                    col = f["col"]
                    alias = f.get("alias", f"{func}({col})")
                    fn = agg_funcs.get(func)
                    new_row[alias] = fn(col, grp) if fn else None
                elif f["type"] == "COLUMN":
                    name = f["name"]
                    alias = f.get("alias") or name
                    new_row[alias] = self._row_val(grp[0], name) if grp else None
            result.append(new_row)
        return result

    def _project(self, rows, fields) -> list:
        if not fields or (len(fields) == 1 and fields[0].get("type") == "STAR"):
            # Strip table-prefixed keys (keep only col-level keys)
            return [{k: v for k, v in r.items() if '.' not in k} or r
                    for r in rows]
        result = []
        for row in rows:
            new_row = {}
            for f in fields:
                if not isinstance(f, dict):
                    continue
                if f["type"] == "STAR":
                    new_row.update({k: v for k, v in row.items() if '.' not in k})
                elif f["type"] == "COLUMN":
                    name = f["name"]
                    alias = f.get("alias") or name.split(".")[-1]
                    new_row[alias] = self._row_val(row, name)
            result.append(new_row)
        return result

    # ══════════════════════════════════════════════════════════════════════════
    # INSERT
    # ══════════════════════════════════════════════════════════════════════════

    def _exec_insert(self, ast: dict) -> str:
        tname = ast["table"]
        rows = self.storage.read_table(tname)
        schemas = self.storage.read_schemas()
        raw = schemas.get(tname, {})
        schema = {k: v for k, v in raw.items() if not k.startswith("_")}
        meta = raw.get("_meta", {})

        columns = ast.get("columns")
        values = list(ast["values"])

        # ── AUTO_INCREMENT ─────────────────────────────────────────────────────
        ai_col = meta.get("auto_increment")
        if ai_col:
            next_id = meta.get("_next_id", 1)
            col_list = list(schema.keys())
            if columns is None:
                ai_idx = col_list.index(ai_col) if ai_col in col_list else -1
                if ai_idx >= 0 and (len(values) < len(col_list) or values[ai_idx] is None):
                    if len(values) < len(col_list):
                        values.insert(ai_idx, next_id)
                    else:
                        values[ai_idx] = next_id
            else:
                if ai_col not in columns:
                    columns = [ai_col] + list(columns)
                    values = [next_id] + values
            meta["_next_id"] = next_id + 1
            raw["_meta"] = meta
            schemas[tname] = raw
            self.storage.write_schemas(schemas)

        # ── Build new row ──────────────────────────────────────────────────────
        if columns:
            if len(columns) != len(values):
                raise ValueError(f"Column count ({len(columns)}) ≠ value count ({len(values)})")
            new_row = {}
            for col, val in zip(columns, values):
                new_row[col] = self._cast(val, schema.get(col, "TEXT"))
            # Fill defaults for omitted columns
            for col, ctype in schema.items():
                if col not in new_row:
                    dflt = meta.get("defaults", {}).get(col)
                    new_row[col] = self._cast(dflt, ctype) if dflt is not None else None
        else:
            if schema:
                col_list = list(schema.keys())
                if len(values) != len(col_list):
                    raise ValueError(
                        f"Expected {len(col_list)} values {col_list}, got {len(values)}"
                    )
                new_row = {col: self._cast(val, ctype)
                           for (col, ctype), val in zip(schema.items(), values)}
            else:
                keys = list(rows[0].keys()) if rows else list(range(len(values)))
                new_row = dict(zip(keys, values))

        # ── Constraint checks ──────────────────────────────────────────────────
        for col in meta.get("not_null", []):
            if new_row.get(col) is None:
                raise ValueError(f"Column '{col}' cannot be NULL")

        for col in meta.get("unique", []):
            v = new_row.get(col)
            if any(r.get(col) == v for r in rows):
                raise ValueError(f"Duplicate value '{v}' for UNIQUE column '{col}'")

        rows.append(new_row)
        self.storage.write_table(tname, rows)
        return f"1 row inserted into '{tname}'."

    # ══════════════════════════════════════════════════════════════════════════
    # UPDATE
    # ══════════════════════════════════════════════════════════════════════════

    def _exec_update(self, ast: dict) -> str:
        tname = ast["table"]
        rows = self.storage.read_table(tname)
        schema, meta = self._schema_of(tname)

        count = 0
        for row in rows:
            if self._eval_cond(row, ast.get("where")):
                for s in ast["sets"]:
                    col, val = s["column"], s["value"]
                    row[col] = self._cast(val, schema.get(col, "TEXT"))
                count += 1

        self.storage.write_table(tname, rows)
        return f"{count} row(s) updated."

    # ══════════════════════════════════════════════════════════════════════════
    # DELETE
    # ══════════════════════════════════════════════════════════════════════════

    def _exec_delete(self, ast: dict) -> str:
        tname = ast["table"]
        rows = self.storage.read_table(tname)
        kept = [r for r in rows if not self._eval_cond(r, ast.get("where"))]
        self.storage.write_table(tname, kept)
        return f"{len(rows) - len(kept)} row(s) deleted."

    # ══════════════════════════════════════════════════════════════════════════
    # CREATE TABLE
    # ══════════════════════════════════════════════════════════════════════════

    def _exec_create_table(self, ast: dict) -> str:
        tname = ast["table"]
        schema = ast["schema"]
        meta = ast.get("meta", {})
        schemas = self.storage.read_schemas()
        if tname in schemas:
            raise FileExistsError(f"Table '{tname}' already exists.")

        entry = dict(schema)
        clean_meta = {k: v for k, v in meta.items() if v}
        if clean_meta:
            if meta.get("auto_increment"):
                clean_meta["_next_id"] = 1
            entry["_meta"] = clean_meta

        schemas[tname] = entry
        self.storage.write_schemas(schemas)
        self.storage.write_table(tname, [])

        pk = meta.get("primary_key")
        ai = meta.get("auto_increment")
        cols_desc = ", ".join(
            f"{c} {t}" + (" PK" if c == pk else "") + (" AI" if c == ai else "")
            for c, t in schema.items()
        )
        return f"Table '{tname}' created ({cols_desc})."

    # ══════════════════════════════════════════════════════════════════════════
    # DROP TABLE
    # ══════════════════════════════════════════════════════════════════════════

    def _exec_drop_table(self, ast: dict) -> str:
        self.storage.drop_table(ast["table"])
        return f"Table '{ast['table']}' dropped."

    # ══════════════════════════════════════════════════════════════════════════
    # ALTER TABLE
    # ══════════════════════════════════════════════════════════════════════════

    def _exec_alter_table(self, ast: dict) -> str:
        tname = ast["table"]
        action = ast["action"]
        schemas = self.storage.read_schemas()
        entry = schemas.get(tname, {})

        if action == "ADD_COLUMN":
            col, ctype = ast["column"], ast["col_type"]
            entry[col] = ctype
            rows = self.storage.read_table(tname)
            dflt = ast.get("default")
            for r in rows:
                r[col] = dflt
            self.storage.write_table(tname, rows)
            schemas[tname] = entry
            self.storage.write_schemas(schemas)
            return f"Column '{col}' ({ctype}) added to '{tname}'."

        if action == "DROP_COLUMN":
            col = ast["column"]
            entry.pop(col, None)
            meta = entry.get("_meta", {})
            for key in ("primary_key", "auto_increment"):
                if meta.get(key) == col:
                    meta[key] = None
            for lst in ("not_null", "unique"):
                if col in meta.get(lst, []):
                    meta[lst].remove(col)
            meta.get("defaults", {}).pop(col, None)
            rows = self.storage.read_table(tname)
            for r in rows:
                r.pop(col, None)
            self.storage.write_table(tname, rows)
            schemas[tname] = entry
            self.storage.write_schemas(schemas)
            return f"Column '{col}' dropped from '{tname}'."

        if action == "RENAME_COLUMN":
            old, new = ast["old_name"], ast["new_name"]
            if old in entry:
                entry[new] = entry.pop(old)
            meta = entry.get("_meta", {})
            for key in ("primary_key", "auto_increment"):
                if meta.get(key) == old:
                    meta[key] = new
            for lst in ("not_null", "unique"):
                if old in meta.get(lst, []):
                    meta[lst] = [new if x == old else x for x in meta[lst]]
            if old in meta.get("defaults", {}):
                meta["defaults"][new] = meta["defaults"].pop(old)
            rows = self.storage.read_table(tname)
            for r in rows:
                if old in r:
                    r[new] = r.pop(old)
            self.storage.write_table(tname, rows)
            schemas[tname] = entry
            self.storage.write_schemas(schemas)
            return f"Column '{old}' renamed to '{new}' in '{tname}'."

        raise ValueError(f"Unknown ALTER action: {action}")

    # ══════════════════════════════════════════════════════════════════════════
    # CREATE INDEX
    # ══════════════════════════════════════════════════════════════════════════

    def _exec_create_index(self, ast: dict) -> str:
        self.storage.create_index(ast["table"], ast["column"])
        return f"Index created on {ast['table']}({ast['column']})."

    # ══════════════════════════════════════════════════════════════════════════
    # SHOW TABLES
    # ══════════════════════════════════════════════════════════════════════════

    def _exec_show_tables(self, _) -> list:
        tables = self.storage.list_tables()
        return [{"Tables": t} for t in tables]

    # ══════════════════════════════════════════════════════════════════════════
    # DESCRIBE table
    # ══════════════════════════════════════════════════════════════════════════

    def _exec_describe(self, ast: dict) -> list:
        schemas = self.storage.read_schemas()
        tname = ast["table"]
        raw = schemas.get(tname)

        # If not in schema, try to infer from data file
        if raw is None:
            try:
                rows = self.storage.read_table(tname)
                if rows:
                    raw = {k: "TEXT" for k in rows[0].keys()}
                else:
                    raw = {}
            except FileNotFoundError:
                raise FileNotFoundError(f"Table '{tname}' not found.")

        meta = raw.get("_meta", {})
        pk = meta.get("primary_key")
        ai = meta.get("auto_increment")
        not_null = meta.get("not_null", [])
        unique_cols = meta.get("unique", [])
        defaults = meta.get("defaults", {})
        result = []
        for col, ctype in raw.items():
            if col.startswith("_"):
                continue
            result.append({
                "Field":   col,
                "Type":    ctype,
                "Null":    "NO" if col in not_null else "YES",
                "Key":     "PRI" if col == pk else ("UNI" if col in unique_cols else ""),
                "Default": str(defaults[col]) if col in defaults else "NULL",
                "Extra":   "auto_increment" if col == ai else "",
            })
        return result


    # ══════════════════════════════════════════════════════════════════════════
    # TRUNCATE
    # ══════════════════════════════════════════════════════════════════════════

    def _exec_truncate(self, ast: dict) -> str:
        tname = ast["table"]
        # Reset AUTO_INCREMENT counter
        schemas = self.storage.read_schemas()
        entry = schemas.get(tname, {})
        if "_meta" in entry:
            entry["_meta"]["_next_id"] = 1
            schemas[tname] = entry
            self.storage.write_schemas(schemas)
        self.storage.write_table(tname, [])
        return f"Table '{tname}' truncated."