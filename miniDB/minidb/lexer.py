"""
lexer.py — BOXDB Lexer
Tokenizes BOXDB-QL queries (custom syntax + SQL aliases).
"""


class Token:
    def __init__(self, type_: str, value):
        self.type = type_
        self.value = value

    def __repr__(self):
        return f"Token({self.type}, {repr(self.value)})"


# All recognized keywords (BOXDB native + SQL aliases)
KEYWORDS = {
    # ── BOXDB Native Commands ──────────────────────────────────
    "GET", "ADD", "CHANGE", "REMOVE", "BUILD", "INDEX", "WITH", "FILTER",
    # ── SQL Aliases ────────────────────────────────────────────
    "SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER",
    # ── Clauses ────────────────────────────────────────────────
    "FROM", "INTO", "VALUES", "SET", "WHERE",
    "JOIN", "INNER", "LEFT", "RIGHT", "OUTER", "CROSS", "ON",
    "ORDER", "BY", "ASC", "DESC",
    "GROUP", "HAVING",
    "LIMIT", "OFFSET",
    "DISTINCT", "AS",
    # ── Table / Schema ops ─────────────────────────────────────
    "TABLE", "SHOW", "TABLES", "DESCRIBE", "TRUNCATE",
    "COLUMN", "RENAME", "TO", "IF", "EXISTS",
    "PRIMARY", "KEY", "UNIQUE", "NOT", "NULL",
    "DEFAULT", "AUTO_INCREMENT",
    # ── Data types ─────────────────────────────────────────────
    "INT", "INTEGER", "TEXT", "VARCHAR", "FLOAT", "REAL", "BOOL", "BOOLEAN",
    # ── Aggregate functions ────────────────────────────────────
    "COUNT", "SUM", "AVG", "MAX", "MIN",
    # ── Logical ────────────────────────────────────────────────
    "AND", "OR",
    # ── Special predicates ─────────────────────────────────────
    "IS", "LIKE", "IN", "BETWEEN",
}


def tokenize(query: str) -> list:
    tokens = []
    i = 0
    n = len(query)

    while i < n:
        # ── Whitespace ─────────────────────────────────────────
        if query[i].isspace():
            i += 1
            continue

        # ── Line comment: -- ... ───────────────────────────────
        if query[i:i + 2] == '--':
            while i < n and query[i] != '\n':
                i += 1
            continue

        # ── Block comment: /* ... */ ───────────────────────────
        if query[i:i + 2] == '/*':
            i += 2
            while i < n - 1 and query[i:i + 2] != '*/':
                i += 1
            i += 2
            continue

        # ── String literal (single or double quoted) ───────────
        if query[i] in ('"', "'"):
            quote = query[i]
            i += 1
            s = []
            while i < n and query[i] != quote:
                if query[i] == '\\' and i + 1 < n:
                    esc = query[i + 1]
                    s.append({'n': '\n', 't': '\t', 'r': '\r'}.get(esc, esc))
                    i += 2
                else:
                    s.append(query[i])
                    i += 1
            i += 1  # skip closing quote
            tokens.append(Token("STRING", ''.join(s)))
            continue

        # ── Backtick-quoted identifier ─────────────────────────
        if query[i] == '`':
            i += 1
            start = i
            while i < n and query[i] != '`':
                i += 1
            tokens.append(Token("IDENTIFIER", query[start:i]))
            i += 1
            continue

        # ── Two-char operators ─────────────────────────────────
        two = query[i:i + 2]
        if two in ("!=", ">=", "<=", "<>"):
            tokens.append(Token("OPERATOR", "!=" if two == "<>" else two))
            i += 2
            continue

        # ── Single-char tokens ─────────────────────────────────
        ch = query[i]
        if ch == '*':
            tokens.append(Token("STAR", "*")); i += 1; continue
        if ch in "=><":
            tokens.append(Token("OPERATOR", ch)); i += 1; continue
        if ch == ',':
            tokens.append(Token("COMMA", ",")); i += 1; continue
        if ch == '(':
            tokens.append(Token("LPAREN", "(")); i += 1; continue
        if ch == ')':
            tokens.append(Token("RPAREN", ")")); i += 1; continue
        if ch == ';':
            tokens.append(Token("SEMICOLON", ";")); i += 1; continue

        # ── Numbers ────────────────────────────────────────────
        if query[i].isdigit():
            start = i
            while i < n and query[i].isdigit():
                i += 1
            if i < n and query[i] == '.':
                i += 1
                while i < n and query[i].isdigit():
                    i += 1
                tokens.append(Token("FLOAT_LIT", float(query[start:i])))
            else:
                tokens.append(Token("INT_LIT", int(query[start:i])))
            continue

        # ── Identifiers and keywords ───────────────────────────
        if query[i].isalpha() or query[i] == '_':
            start = i
            while i < n and (query[i].isalnum() or query[i] == '_'):
                i += 1
            # Greedily consume table.column form
            if (i < n and query[i] == '.' and i + 1 < n
                    and (query[i + 1].isalpha() or query[i + 1] == '_')):
                i += 1  # dot
                while i < n and (query[i].isalnum() or query[i] == '_'):
                    i += 1

            word = query[start:i]
            upper = word.upper()

            if '.' not in word:
                if upper in KEYWORDS:
                    tokens.append(Token("KEYWORD", upper))
                elif upper == "TRUE":
                    tokens.append(Token("BOOL_LIT", True))
                elif upper == "FALSE":
                    tokens.append(Token("BOOL_LIT", False))
                else:
                    tokens.append(Token("IDENTIFIER", word))
            else:
                # table.column stays as IDENTIFIER
                tokens.append(Token("IDENTIFIER", word))
            continue

        # ── Skip unknown character ─────────────────────────────
        i += 1

    return tokens