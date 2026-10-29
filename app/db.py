import os
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "progress.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS progress (
    mode TEXT NOT NULL,
    item_id TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    correct INTEGER NOT NULL DEFAULT 0,
    streak INTEGER NOT NULL DEFAULT 0,
    learned INTEGER NOT NULL DEFAULT 0,
    excluded INTEGER NOT NULL DEFAULT 0,
    last_seen REAL,
    field_stats TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (mode, item_id)
);
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT NOT NULL,
    item_id TEXT NOT NULL,
    ts REAL NOT NULL,
    all_correct INTEGER NOT NULL,
    score REAL NOT NULL,
    details TEXT NOT NULL,
    streak_before INTEGER NOT NULL,
    attempt_no INTEGER NOT NULL,
    overridden INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS attempts_item ON attempts (mode, item_id);
CREATE TABLE IF NOT EXISTS decks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS deck_pairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deck_id INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    sv TEXT NOT NULL,
    en TEXT NOT NULL
);
"""


def db_path():
    return Path(os.environ.get("SWEDISH_APP_DB", DEFAULT_DB))


def connect(path=None):
    path = Path(path or db_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn
