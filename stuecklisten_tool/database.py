"""Utility functions for interacting with the SQLite database."""

from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path
from typing import Iterator

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS parts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_number TEXT NOT NULL UNIQUE,
        description TEXT,
        supplier TEXT,
        price REAL,
        store_link TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS bill_of_materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        part_id INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
        quantity REAL NOT NULL CHECK(quantity > 0),
        UNIQUE(product_id, part_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS product_requirements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
        quantity REAL NOT NULL CHECK(quantity >= 0),
        UNIQUE(product_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        note TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS version_items (
        version_id INTEGER NOT NULL REFERENCES versions(id) ON DELETE CASCADE,
        product_name TEXT NOT NULL,
        part_number TEXT NOT NULL,
        part_description TEXT,
        supplier TEXT,
        price REAL,
        quantity REAL NOT NULL,
        PRIMARY KEY (version_id, product_name, part_number)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS version_demands (
        version_id INTEGER NOT NULL REFERENCES versions(id) ON DELETE CASCADE,
        product_name TEXT NOT NULL,
        quantity REAL NOT NULL,
        PRIMARY KEY (version_id, product_name)
    )
    """,
]


def get_connection(path: str | Path) -> sqlite3.Connection:
    """Return a SQLite connection with sensible defaults."""
    path = Path(path)
    if path != Path(":memory:"):
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database(conn: sqlite3.Connection) -> None:
    """Create all required tables if they are missing."""
    with conn:
        for statement in SCHEMA:
            conn.execute(statement)


@contextlib.contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Context manager that wraps statements inside a transaction."""
    try:
        conn.execute("BEGIN")
        yield conn
    except Exception:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
