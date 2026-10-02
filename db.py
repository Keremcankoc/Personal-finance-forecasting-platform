"""
db.py
=====
Thin wrapper around pyodbc that all data-access code in the project goes
through. Provides:

* a single connection helper (`get_connection`)
* a context-managed cursor (`cursor_scope`)
* convenience helpers `execute`, `query_one`, `query_all`, `query_scalar`
* a `script_runner` that splits a multi-batch T-SQL file on `GO` and runs
  the batches in order (used by the seed script and the dump loader)
* parameterised loader for the advanced queries file

Every helper uses **parameterised queries (`?` placeholders)**.
String concatenation of user input into SQL is never done anywhere in the
project — see queries/advanced_queries.sql and the GUI views.
"""
from __future__ import annotations

import os
import re
from contextlib import contextmanager
from typing import Any, Iterable, Iterator, Sequence

import pyodbc

from config import build_connection_string


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------
def get_connection(autocommit: bool = False, database: str | None = None) -> pyodbc.Connection:
    """
    Open a new connection. Pass `database=None` to keep the value from
    config.py, or override it (e.g. `database="master"` when bootstrapping).
    """
    cs = build_connection_string()
    if database is not None:
        cs = re.sub(r"DATABASE=[^;]+;", f"DATABASE={database};", cs)
    conn = pyodbc.connect(cs, autocommit=autocommit)
    # Make pyodbc return Python str (not bytes) for nvarchar columns
    conn.setdecoding(pyodbc.SQL_CHAR, encoding="utf-8")
    conn.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-8")
    conn.setencoding(encoding="utf-8")
    return conn


@contextmanager
def cursor_scope(autocommit: bool = False) -> Iterator[pyodbc.Cursor]:
    """Context manager that yields a cursor and commits/rolls back on exit."""
    conn = get_connection(autocommit=autocommit)
    try:
        cur = conn.cursor()
        yield cur
        if not autocommit:
            conn.commit()
    except Exception:
        if not autocommit:
            conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------
def execute(sql: str, params: Sequence[Any] = ()) -> int:
    """Run an INSERT/UPDATE/DELETE; return rowcount."""
    with cursor_scope() as cur:
        cur.execute(sql, params)
        return cur.rowcount


def execute_returning_id(sql: str, params: Sequence[Any] = ()) -> int:
    """
    Run an INSERT and return the new identity value.
    The caller must NOT include `SELECT SCOPE_IDENTITY()` in `sql`; we append it.
    """
    with cursor_scope() as cur:
        cur.execute(sql + "; SELECT CAST(SCOPE_IDENTITY() AS INT) AS NewID;", params)
        # SCOPE_IDENTITY may sit on a second result set
        while cur.description is None:
            if not cur.nextset():
                break
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else -1


def query_all(sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    """Run a SELECT, return all rows as a list of dicts."""
    with cursor_scope() as cur:
        cur.execute(sql, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def query_one(sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
    """Run a SELECT, return the first row as a dict (or None)."""
    rows = query_all(sql, params)
    return rows[0] if rows else None


def query_scalar(sql: str, params: Sequence[Any] = ()) -> Any:
    """Run a SELECT and return the first column of the first row."""
    with cursor_scope() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row else None


# ---------------------------------------------------------------------------
# Multi-batch script runner (handles `GO` separators)
# ---------------------------------------------------------------------------
_GO_RE = re.compile(r"^\s*GO\s*(?:--.*)?$", re.IGNORECASE | re.MULTILINE)


def split_batches(script: str) -> list[str]:
    """Split a T-SQL script on `GO` lines into individual batches."""
    parts = _GO_RE.split(script)
    return [p.strip() for p in parts if p and p.strip()]


def run_script(script: str, *, database: str | None = None,
               autocommit: bool = True) -> None:
    """
    Run a multi-batch T-SQL script. Connects to `database` (or the configured
    one if None). Useful for creating the database, installing the schema,
    and loading the dump.
    """
    conn = get_connection(autocommit=autocommit, database=database)
    try:
        cur = conn.cursor()
        for batch in split_batches(script):
            cur.execute(batch)
            # Drain any result sets so the next batch can start
            try:
                while cur.nextset():
                    pass
            except pyodbc.ProgrammingError:
                pass
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Advanced queries loader
# ---------------------------------------------------------------------------
_QUERIES_PATH = os.path.join(os.path.dirname(__file__), "queries", "advanced_queries.sql")


def load_advanced_queries() -> dict[str, str]:
    """
    Parse queries/advanced_queries.sql and return a dict of
    {query_name: sql_text}. Each query block in that file is delimited by
    a header comment of the form `-- @name=Q1`.
    """
    if not os.path.exists(_QUERIES_PATH):
        return {}
    with open(_QUERIES_PATH, "r", encoding="utf-8") as fh:
        text = fh.read()

    blocks: dict[str, str] = {}
    current_name: str | None = None
    current_lines: list[str] = []
    for line in text.splitlines():
        m = re.match(r"\s*--\s*@name\s*=\s*(\S+)", line)
        if m:
            if current_name and current_lines:
                blocks[current_name] = "\n".join(current_lines).strip()
            current_name = m.group(1)
            current_lines = []
        else:
            if current_name is not None:
                current_lines.append(line)
    if current_name and current_lines:
        blocks[current_name] = "\n".join(current_lines).strip()
    return blocks


def run_named_query(name: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
    """Run one of the queries from advanced_queries.sql by its @name tag."""
    blocks = load_advanced_queries()
    if name not in blocks:
        raise KeyError(f"Query '{name}' not found in advanced_queries.sql")
    return query_all(blocks[name], params)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
def healthcheck() -> tuple[bool, str]:
    """Return (ok, message). Used by main.py to verify connectivity at startup."""
    try:
        with cursor_scope(autocommit=True) as cur:
            cur.execute("SELECT @@VERSION;")
            row = cur.fetchone()
            return True, str(row[0]).splitlines()[0] if row else "connected"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
