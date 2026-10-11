"""
parser.py — BOXDB Parser
Supports BOXDB-native syntax (GET/ADD/CHANGE/REMOVE/BUILD) + SQL aliases.
New features: ORDER BY, LIMIT, OFFSET, GROUP BY, HAVING, aggregates,
              AND/OR/NOT conditions, LIKE, IN, BETWEEN, IS NULL,
              LEFT/RIGHT/INNER JOIN, multi-SET UPDATE, column-list INSERT,
              DROP TABLE, ALTER TABLE, SHOW TABLES, DESCRIBE, TRUNCATE,
              AUTO_INCREMENT, PRIMARY KEY, NOT NULL, DEFAULT, UNIQUE.
"""


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    # ══════════════════════════════════════════════════════════════════════════
    # Low-level helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _peek(self, offset=0):
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else None

    def _current(self):
        return self._peek(0)

    def _advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _is_kw(self, *kws, offset=0):
        tok = self._peek(offset)
        return tok is not None and tok.type == "KEYWORD" and tok.value in kws

    def _expect_kw(self, *kws):
        if not self._is_kw(*kws):
            got = self._current()
            raise SyntaxError(
                f"Expected {' or '.join(kws)}, got "
                f"'{got.value if got else 'EOF'}'"
            )
        return self._advance()

    def _try_kw(self, *kws):
        if self._is_kw(*kws):
            return self._advance()
        return None

    def _is_tok(self, type_, offset=0):
        tok = self._peek(offset)
        return tok is not None and tok.type == type_

    def _try_tok(self, type_):
        if self._is_tok(type_):
            return self._advance()
        return None

    # Stop-keywords that end a field list / expression scan
    _STOP = {"FROM", "WHERE", "FILTER", "ORDER", "GROUP", "HAVING",
             "LIMIT", "OFFSET", "JOIN", "INNER", "LEFT", "RIGHT",
             "CROSS", "OUTER", "SEMICOLON"}

    def _at_stop(self):
        tok = self._current()
        if tok is None:
            return True
        if tok.type == "SEMICOLON":
            return True
        if tok.type == "KEYWORD" and tok.value in self._STOP:
            return True
        return False

    RESERVED_CLAUSE_KEYWORDS = {
        "GET", "ADD", "CHANGE", "REMOVE", "BUILD", "INDEX", "WITH", "FILTER",
        "SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER",
        "FROM", "INTO", "VALUES", "SET", "WHERE",
        "JOIN", "INNER", "LEFT", "RIGHT", "OUTER", "CROSS", "ON",
        "ORDER", "BY", "GROUP", "HAVING", "LIMIT", "OFFSET",
        "TABLE", "TABLES", "SHOW", "DESCRIBE", "TRUNCATE"
    }

    def _parse_name(self):
        """Parse a plain identifier or non-clause keyword-used-as-name."""
        tok = self._current()
        if tok is None:
            raise SyntaxError("Expected identifier, got EOF")
        if tok.type == "KEYWORD":
            if tok.value in self.RESERVED_CLAUSE_KEYWORDS:
                raise SyntaxError(f"Expected identifier, got reserved keyword '{tok.value}'")
            self.pos += 1
            return tok.value
        if tok.type == "IDENTIFIER":
            self.pos += 1
            return tok.value
        raise SyntaxError(f"Expected identifier, got {tok.type}:{tok.value}")

    def _parse_col_ref(self):
        tok = self._current()
        if tok is None:
            raise SyntaxError("Expected column reference")
        if tok.type in ("IDENTIFIER", "KEYWORD"):
            self.pos += 1
            return tok.value
        if tok.type == "STAR":
            self.pos += 1
            return "*"
        raise SyntaxError(f"Expected column ref, got {tok.type}:{tok.value}")

    def _parse_literal(self):
        """Parse a literal value (number, string, bool, NULL, or bare word)."""
        tok = self._current()
        if tok is None:
            raise SyntaxError("Expected value, got EOF")
        if tok.type in ("INT_LIT", "FLOAT_LIT", "STRING", "BOOL_LIT"):
            self.pos += 1
            return tok.value
        if tok.type == "KEYWORD" and tok.value == "NULL":
            self.pos += 1
            return None
        if tok.type == "KEYWORD" and tok.value == "TRUE":
            self.pos += 1
            return True
        if tok.type == "KEYWORD" and tok.value == "FALSE":
            self.pos += 1
            return False
        # Bare identifier used as unquoted string value (BOXDB native compat)
        if tok.type == "IDENTIFIER":
            self.pos += 1
            return tok.value
        raise SyntaxError(f"Expected literal, got {tok.type}:{tok.value}")

    def _parse_col_type(self) -> str:
        type_map = {
            "INT": "INT", "INTEGER": "INT",
            "TEXT": "TEXT", "VARCHAR": "TEXT",
            "FLOAT": "FLOAT", "REAL": "FLOAT",
            "BOOL": "BOOL", "BOOLEAN": "BOOL",
        }
        tok = self._current()
        if tok is None:
            raise SyntaxError("Expected column type")
        if tok.type == "KEYWORD" and tok.value in type_map:
            self.pos += 1
            # Skip VARCHAR(n) size spec
            if tok.value == "VARCHAR" and self._is_tok("LPAREN"):
                self._advance()
                while not self._is_tok("RPAREN"):
                    self._advance()
                self._advance()
            return type_map[tok.value]
        if tok.type == "IDENTIFIER":
            self.pos += 1
            return tok.value.upper()
        raise SyntaxError(f"Expected data type, got {tok.value}")

    # ══════════════════════════════════════════════════════════════════════════
    # Top-level dispatch
    # ══════════════════════════════════════════════════════════════════════════

    def parse(self) -> dict:
        if not self.tokens or self.pos >= len(self.tokens):
            raise ValueError("Empty query")

        tok = self._current()
        kw = tok.value if tok.type == "KEYWORD" else None

        if kw in ("GET", "SELECT"):
            return self._parse_select()
        elif kw in ("ADD", "INSERT"):
            return self._parse_insert()
        elif kw in ("CHANGE", "UPDATE"):
            return self._parse_update()
        elif kw in ("REMOVE", "DELETE"):
            return self._parse_delete()
        elif kw in ("BUILD", "CREATE"):
            return self._parse_create()
        elif kw == "DROP":
            return self._parse_drop()
        elif kw == "ALTER":
            return self._parse_alter()
        elif kw == "INDEX":
            return self._parse_index_stmt()
        elif kw == "SHOW":
            return self._parse_show()
        elif kw == "DESCRIBE":
            return self._parse_describe()
        elif kw == "TRUNCATE":
            return self._parse_truncate()
        else:
            raise NotImplementedError(f"Command '{tok.value}' not recognized.")

    # ══════════════════════════════════════════════════════════════════════════
    # SELECT  (GET / SELECT)
    # ══════════════════════════════════════════════════════════════════════════

    def _parse_select(self) -> dict:
        self._advance()  # GET | SELECT
        distinct = bool(self._try_kw("DISTINCT"))
        fields = self._parse_field_list()

        self._expect_kw("FROM")
        table = self._parse_name()
        # Optional table alias
        table_alias = None
        if self._try_kw("AS"):
            table_alias = self._parse_name()

        # JOINs
        joins = []
        while self._is_kw("JOIN", "INNER", "LEFT", "RIGHT", "CROSS", "OUTER"):
            joins.append(self._parse_join())

        # WHERE / FILTER
        where = None
        if self._is_kw("WHERE", "FILTER"):
            self._advance()
            where = self._parse_condition()

        # GROUP BY
        group_by = []
        if self._is_kw("GROUP"):
            self._advance()
            self._expect_kw("BY")
            group_by.append(self._parse_col_ref())
            while self._is_tok("COMMA"):
                self._advance()
                group_by.append(self._parse_col_ref())

        # HAVING
        having = None
        if self._is_kw("HAVING"):
            self._advance()
            having = self._parse_condition()

        # ORDER BY
        order_by = []
        if self._is_kw("ORDER"):
            self._advance()
            self._expect_kw("BY")
            order_by.append(self._parse_order_item())
            while self._is_tok("COMMA"):
                self._advance()
                order_by.append(self._parse_order_item())

        # LIMIT [OFFSET]
        limit = None
        offset = 0
        if self._is_kw("LIMIT"):
            self._advance()
            tok = self._current()
            if tok and tok.type == "INT_LIT":
                limit = tok.value
                self._advance()
            # OFFSET keyword
            if self._is_kw("OFFSET"):
                self._advance()
                tok = self._current()
                if tok and tok.type == "INT_LIT":
                    offset = tok.value
                    self._advance()
            # MySQL-style: LIMIT offset, count
            elif self._is_tok("COMMA"):
                self._advance()
                tok = self._current()
                if tok and tok.type == "INT_LIT":
                    offset = limit
                    limit = tok.value
                    self._advance()

        return {
            "type": "SELECT",
            "distinct": distinct,
            "fields": fields,
            "table": table,
            "table_alias": table_alias,
            "joins": joins,
            "where": where,
            "group_by": group_by,
            "having": having,
            "order_by": order_by,
            "limit": limit,
            "offset": offset,
        }

    def _parse_field_list(self) -> list:
        tok = self._current()
        if tok and tok.type == "STAR":
            self._advance()
            return [{"type": "STAR"}]

        stop = {"FROM", "WHERE", "FILTER", "ORDER", "GROUP",
                "HAVING", "LIMIT", "OFFSET"}
        fields = []
        while self._current() and not self._is_kw(*stop) and not self._is_tok("SEMICOLON"):
            fields.append(self._parse_field_expr())
            self._try_tok("COMMA")  # comma optional (BOXDB compat)

        return fields if fields else [{"type": "STAR"}]

    def _parse_field_expr(self) -> dict:
        tok = self._current()
        if tok is None:
            raise SyntaxError("Expected field expression")

        # STAR
        if tok.type == "STAR":
            self._advance()
            return {"type": "STAR"}

        # Aggregate: COUNT(*), SUM(col), AVG(col), MAX(col), MIN(col)
        if tok.type == "KEYWORD" and tok.value in ("COUNT", "SUM", "AVG", "MAX", "MIN"):
            func = tok.value
            self._advance()
            self._try_tok("LPAREN")  # (
            inner = self._current()
            if inner and inner.type == "STAR":
                col = "*"
                self._advance()
            else:
                col = self._parse_col_ref()
            self._try_tok("RPAREN")  # )
            alias = None
            if self._try_kw("AS"):
                alias = self._parse_name()
            label = alias or f"{func}({col})"
            return {"type": "AGGREGATE", "func": func, "col": col, "alias": label}

        # Regular column [AS alias]
        col = self._parse_col_ref()
        alias = None
        if self._try_kw("AS"):
            alias = self._parse_name()
        return {"type": "COLUMN", "name": col, "alias": alias}

    def _parse_join(self) -> dict:
        join_type = "INNER"
        if self._is_kw("LEFT"):
            join_type = "LEFT"; self._advance(); self._try_kw("OUTER")
        elif self._is_kw("RIGHT"):
            join_type = "RIGHT"; self._advance(); self._try_kw("OUTER")
        elif self._is_kw("INNER"):
            join_type = "INNER"; self._advance()
        elif self._is_kw("CROSS"):
            join_type = "CROSS"; self._advance()
        elif self._is_kw("OUTER"):
            self._advance()

        self._expect_kw("JOIN")
        joined_table = self._parse_name()
        joined_alias = None
        if self._try_kw("AS"):
            joined_alias = self._parse_name()

        left_key = right_key = None
        if self._try_kw("ON"):
            left_key = self._parse_col_ref()
            self._try_tok("OPERATOR")   # skip '='
            right_key = self._parse_col_ref()

        return {
            "join_type": join_type,
            "joined_table": joined_table,
            "joined_alias": joined_alias,
            "left_key": left_key,
            "right_key": right_key,
        }

    def _parse_order_item(self) -> dict:
        col = self._parse_col_ref()
        direction = "ASC"
        if self._is_kw("DESC"):
            direction = "DESC"; self._advance()
        elif self._is_kw("ASC"):
            self._advance()
        return {"col": col, "direction": direction}

    # ══════════════════════════════════════════════════════════════════════════
    # Condition parser  (WHERE / FILTER / HAVING)
    # Precedence: OR < AND < NOT < comparison
    # ══════════════════════════════════════════════════════════════════════════

    def _parse_condition(self) -> dict:
        return self._parse_or()

    def _parse_or(self) -> dict:
        left = self._parse_and()
        while self._is_kw("OR"):
            self._advance()
            right = self._parse_and()
            left = {"type": "OR", "left": left, "right": right}
        return left

    def _parse_and(self) -> dict:
        left = self._parse_not()
        while self._is_kw("AND"):
            self._advance()
            right = self._parse_not()
            left = {"type": "AND", "left": left, "right": right}
        return left

    def _parse_not(self) -> dict:
        if self._is_kw("NOT"):
            self._advance()
            return {"type": "NOT", "operand": self._parse_not()}
        return self._parse_comparison()

    def _parse_comparison(self) -> dict:
        # Parenthesised sub-condition
        if self._is_tok("LPAREN"):
            self._advance()
            cond = self._parse_condition()
            self._try_tok("RPAREN")
            return cond

        col = self._parse_col_ref()
        tok = self._current()
        if tok is None:
            return {"type": "TRUTHY", "col": col}

        # IS [NOT] NULL
        if self._is_kw("IS"):
            self._advance()
            negate = bool(self._try_kw("NOT"))
            if self._is_kw("NULL"):
                self._advance()
                return {"type": "IS_NOT_NULL" if negate else "IS_NULL", "col": col}
            raise SyntaxError("Expected NULL after IS [NOT]")

        # BETWEEN val AND val
        if self._is_kw("BETWEEN"):
            self._advance()
            low = self._parse_literal()
            self._expect_kw("AND")
            high = self._parse_literal()
            return {"type": "BETWEEN", "col": col, "low": low, "high": high}

        # [NOT] IN (val, ...)
        negate = False
        if self._is_kw("NOT"):
            negate = True
            self._advance()

        if self._is_kw("IN"):
            self._advance()
            self._try_tok("LPAREN")
            vals = [self._parse_literal()]
            while self._is_tok("COMMA"):
                self._advance()
                vals.append(self._parse_literal())
            self._try_tok("RPAREN")
            cond = {"type": "IN", "col": col, "values": vals}
            return {"type": "NOT", "operand": cond} if negate else cond

        # [NOT] LIKE pattern
        if self._is_kw("LIKE"):
            self._advance()
            pattern = self._parse_literal()
            cond = {"type": "COMPARE", "col": col, "op": "LIKE", "value": pattern}
            return {"type": "NOT", "operand": cond} if negate else cond

        if negate:
            raise SyntaxError("NOT without valid predicate")

        # Standard operators: = > < >= <= !=
        if tok.type == "OPERATOR":
            op = tok.value
            self._advance()
            val = self._parse_literal()
            return {"type": "COMPARE", "col": col, "op": op, "value": val}

        raise SyntaxError(f"Expected operator in condition, got {tok.type}:{tok.value}")

    # ══════════════════════════════════════════════════════════════════════════
    # INSERT  (ADD INTO / INSERT INTO)
    # ══════════════════════════════════════════════════════════════════════════

    def _parse_insert(self) -> dict:
        self._advance()           # ADD | INSERT
        self._expect_kw("INTO")
        table = self._parse_name()

        # Optional column list: (col1, col2, ...)
        columns = None
        if self._is_tok("LPAREN"):
            self._advance()
            columns = [self._parse_name()]
            while self._is_tok("COMMA"):
                self._advance()
                columns.append(self._parse_name())
            self._try_tok("RPAREN")

        self._expect_kw("VALUES")

        # SQL style: VALUES (v1, v2, ...)
        if self._is_tok("LPAREN"):
            self._advance()
            values = [self._parse_literal()]
            while self._is_tok("COMMA"):
                self._advance()
                values.append(self._parse_literal())
            self._try_tok("RPAREN")
        else:
            # BOXDB native: VALUES v1 v2 v3 (space-separated)
            values = []
            stop_types = {"SEMICOLON", "KEYWORD"}
            stop_kws = {"WHERE", "FILTER", "ORDER", "LIMIT"}
            while self._current():
                t = self._current()
                if t.type == "SEMICOLON":
                    break
                if t.type == "KEYWORD" and t.value in stop_kws:
                    break
                values.append(self._parse_literal())

        return {"type": "INSERT", "table": table, "columns": columns, "values": values}

    # ══════════════════════════════════════════════════════════════════════════
    # UPDATE  (CHANGE / UPDATE)
    # ══════════════════════════════════════════════════════════════════════════

    def _parse_update(self) -> dict:
        self._advance()  # CHANGE | UPDATE
        table = self._parse_name()
        self._expect_kw("SET")

        # Parse one or more SET col = val [, col = val ...]
        sets = [self._parse_set_clause()]
        while self._is_tok("COMMA"):
            self._advance()
            sets.append(self._parse_set_clause())

        where = None
        if self._is_kw("WHERE", "FILTER"):
            self._advance()
            where = self._parse_condition()

        return {"type": "UPDATE", "table": table, "sets": sets, "where": where}

    def _parse_set_clause(self) -> dict:
        col = self._parse_name()
        tok = self._current()
        if tok and tok.type == "OPERATOR" and tok.value == "=":
            self._advance()
        val = self._parse_literal()
        return {"column": col, "value": val}

    # ══════════════════════════════════════════════════════════════════════════
    # DELETE  (REMOVE FROM / DELETE FROM)
    # ══════════════════════════════════════════════════════════════════════════

    def _parse_delete(self) -> dict:
        self._advance()  # REMOVE | DELETE
        self._expect_kw("FROM")
        table = self._parse_name()

        where = None
        if self._is_kw("WHERE", "FILTER"):
            self._advance()
            where = self._parse_condition()

        return {"type": "DELETE", "table": table, "where": where}

    # ══════════════════════════════════════════════════════════════════════════
    # CREATE TABLE  (BUILD TABLE / CREATE TABLE)
    # ══════════════════════════════════════════════════════════════════════════

    def _parse_create(self) -> dict:
        self._advance()  # BUILD | CREATE

        # CREATE INDEX ...
        if self._is_kw("INDEX"):
            return self._parse_index_stmt()

        self._expect_kw("TABLE")

        # IF NOT EXISTS
        if self._is_kw("IF"):
            self._advance()
            self._try_kw("NOT")
            self._try_kw("EXISTS")

        table = self._parse_name()
        schema = {}
        meta = {
            "primary_key": None,
            "auto_increment": None,
            "not_null": [],
            "unique": [],
            "defaults": {},
        }

        # ── SQL style: CREATE TABLE name (col TYPE constraints, ...) ──────────
        if self._is_tok("LPAREN"):
            self._advance()
            while not self._is_tok("RPAREN") and self._current():
                tok = self._current()

                # Table-level PRIMARY KEY (col)
                if self._is_kw("PRIMARY"):
                    self._advance()
                    self._expect_kw("KEY")
                    self._try_tok("LPAREN")
                    meta["primary_key"] = self._parse_name()
                    self._try_tok("RPAREN")
                else:
                    col_name = self._parse_name()
                    col_type = self._parse_col_type()
                    schema[col_name] = col_type
                    # Column-level constraints
                    self._parse_col_constraints(col_name, meta)

                self._try_tok("COMMA")
            self._try_tok("RPAREN")

        # ── BOXDB native: BUILD TABLE name WITH col TYPE [constraint] ... ──────
        elif self._is_kw("WITH"):
            self._advance()
            stop_kws = {"WHERE", "FILTER", "ORDER", "LIMIT", "SEMICOLON"}
            while self._current() and not self._is_kw(*stop_kws) and not self._is_tok("SEMICOLON"):
                col_name = self._parse_name()
                col_type = self._parse_col_type()
                schema[col_name] = col_type
                self._parse_col_constraints(col_name, meta)
                self._try_tok("COMMA")

        return {"type": "CREATE_TABLE", "table": table, "schema": schema, "meta": meta}

    def _parse_col_constraints(self, col_name: str, meta: dict):
        """Parse optional column constraints inline (PRIMARY KEY, AUTO_INCREMENT, NOT NULL, etc.)."""
        constraint_kws = {"PRIMARY", "AUTO_INCREMENT", "NOT", "UNIQUE", "DEFAULT"}
        while self._is_kw(*constraint_kws):
            kw = self._current().value
            if kw == "PRIMARY":
                self._advance()
                self._try_kw("KEY")
                meta["primary_key"] = col_name
            elif kw == "AUTO_INCREMENT":
                self._advance()
                meta["auto_increment"] = col_name
                if col_name not in meta["not_null"]:
                    meta["not_null"].append(col_name)
            elif kw == "NOT":
                self._advance()
                self._try_kw("NULL")
                if col_name not in meta["not_null"]:
                    meta["not_null"].append(col_name)
            elif kw == "UNIQUE":
                self._advance()
                if col_name not in meta["unique"]:
                    meta["unique"].append(col_name)
            elif kw == "DEFAULT":
                self._advance()
                meta["defaults"][col_name] = self._parse_literal()
            else:
                break

    # ══════════════════════════════════════════════════════════════════════════
    # DROP TABLE
    # ══════════════════════════════════════════════════════════════════════════

    def _parse_drop(self) -> dict:
        self._advance()  # DROP
        self._expect_kw("TABLE")
        if self._is_kw("IF"):
            self._advance()
            self._try_kw("EXISTS")
        table = self._parse_name()
        return {"type": "DROP_TABLE", "table": table}

    # ══════════════════════════════════════════════════════════════════════════
    # ALTER TABLE
    # ══════════════════════════════════════════════════════════════════════════

    def _parse_alter(self) -> dict:
        self._advance()  # ALTER
        self._expect_kw("TABLE")
        table = self._parse_name()

        if self._is_kw("ADD"):
            self._advance()
            self._try_kw("COLUMN")
            col_name = self._parse_name()
            col_type = self._parse_col_type()
            default = None
            if self._is_kw("DEFAULT"):
                self._advance()
                default = self._parse_literal()
            return {"type": "ALTER_TABLE", "action": "ADD_COLUMN",
                    "table": table, "column": col_name, "col_type": col_type, "default": default}

        if self._is_kw("DROP"):
            self._advance()
            self._try_kw("COLUMN")
            col_name = self._parse_name()
            return {"type": "ALTER_TABLE", "action": "DROP_COLUMN",
                    "table": table, "column": col_name}

        if self._is_kw("RENAME"):
            self._advance()
            self._try_kw("COLUMN")
            old_name = self._parse_name()
            self._expect_kw("TO")
            new_name = self._parse_name()
            return {"type": "ALTER_TABLE", "action": "RENAME_COLUMN",
                    "table": table, "old_name": old_name, "new_name": new_name}

        raise SyntaxError("ALTER TABLE: expected ADD, DROP, or RENAME")

    # ══════════════════════════════════════════════════════════════════════════
    # INDEX  (INDEX table ON col  |  CREATE INDEX name ON table (col))
    # ══════════════════════════════════════════════════════════════════════════

    def _parse_index_stmt(self) -> dict:
        if self._is_kw("INDEX"):
            self._advance()

        if self._is_kw("ON"):
            self._advance()
            table = self._parse_name()
            self._try_tok("LPAREN")
            col = self._parse_name()
            self._try_tok("RPAREN")
            return {"type": "CREATE_INDEX", "table": table, "column": col}

        first_name = self._parse_name()
        self._expect_kw("ON")

        next_tok = self._peek(1)
        # Check if what follows ON is `table (col)` or `table col`
        if next_tok and (next_tok.type == "LPAREN" or (next_tok.type in ("IDENTIFIER", "KEYWORD") and next_tok.value not in ("SEMICOLON",))):
            # first_name was the index name, next token is table name
            table = self._parse_name()
            self._try_tok("LPAREN")
            col = self._parse_name()
            self._try_tok("RPAREN")
        else:
            # BOXDB native: INDEX table ON col
            table = first_name
            self._try_tok("LPAREN")
            col = self._parse_name()
            self._try_tok("RPAREN")

        return {"type": "CREATE_INDEX", "table": table, "column": col}

    # ══════════════════════════════════════════════════════════════════════════
    # SHOW TABLES
    # ══════════════════════════════════════════════════════════════════════════

    def _parse_show(self) -> dict:
        self._advance()  # SHOW
        self._expect_kw("TABLES")
        return {"type": "SHOW_TABLES"}

    # ══════════════════════════════════════════════════════════════════════════
    # DESCRIBE table
    # ══════════════════════════════════════════════════════════════════════════

    def _parse_describe(self) -> dict:
        self._advance()  # DESCRIBE
        table = self._parse_name()
        return {"type": "DESCRIBE", "table": table}

    # ══════════════════════════════════════════════════════════════════════════
    # TRUNCATE [TABLE] table
    # ══════════════════════════════════════════════════════════════════════════

    def _parse_truncate(self) -> dict:
        self._advance()  # TRUNCATE
        self._try_kw("TABLE")
        table = self._parse_name()
        return {"type": "TRUNCATE", "table": table}