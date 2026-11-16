"""Persistência local do produto (SQLite + áudio em disco). Nada sai da máquina."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

DEFAULT_PROFILE = {"name": "Você", "daily_goal_minutes": 10}

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT NOT NULL,
    daily_goal_minutes INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    result_json TEXT NOT NULL,
    record_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS habits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    text TEXT NOT NULL,
    session_id TEXT
);
"""


class Store:
    def __init__(self, folder: str | Path):
        self.folder = Path(folder)
        self.audio_dir = self.folder / "sessions"
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.folder / "cognus.db", check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(SCHEMA)

    def _query(self, sql: str, params=()) -> list[sqlite3.Row]:
        with self._lock:
            rows = self._db.execute(sql, params).fetchall()
            self._db.commit()
            return rows

    # ---------- perfil ----------
    def profile(self) -> dict:
        rows = self._query("SELECT name, daily_goal_minutes FROM profile WHERE id = 1")
        return dict(rows[0]) if rows else dict(DEFAULT_PROFILE)

    def save_profile(self, name: str, daily_goal_minutes: int) -> dict:
        self._query(
            "INSERT INTO profile (id, name, daily_goal_minutes) VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET name = excluded.name, "
            "daily_goal_minutes = excluded.daily_goal_minutes",
            (name, daily_goal_minutes),
        )
        return self.profile()

    # ---------- sessões ----------
    def save_session(self, result: dict, record: dict, audio: bytes) -> None:
        (self.audio_dir / f"{result['session_id']}.wav").write_bytes(audio)
        self._query(
            "INSERT INTO sessions (id, created_at, result_json, record_json) VALUES (?, ?, ?, ?)",
            (
                result["session_id"],
                result["created_at"],
                json.dumps(result, ensure_ascii=False),
                json.dumps(record, ensure_ascii=False),
            ),
        )

    def session(self, session_id: str) -> dict | None:
        rows = self._query("SELECT result_json FROM sessions WHERE id = ?", (session_id,))
        return json.loads(rows[0]["result_json"]) if rows else None

    def sessions(self) -> list[dict]:
        """Resultados completos, mais recentes primeiro."""
        rows = self._query("SELECT result_json FROM sessions ORDER BY created_at DESC")
        return [json.loads(r["result_json"]) for r in rows]

    def records(self) -> list[dict]:
        """Registros enxutos para o cálculo de progresso (ordem cronológica)."""
        rows = self._query("SELECT record_json FROM sessions ORDER BY created_at")
        return [json.loads(r["record_json"]) for r in rows]

    def audio_path(self, session_id: str) -> Path | None:
        path = self.audio_dir / f"{Path(session_id).name}.wav"
        return path if path.exists() else None

    # ---------- hábitos ----------
    def add_habit(self, created_at: str, text: str, session_id: str | None) -> dict:
        with self._lock:
            cursor = self._db.execute(
                "INSERT INTO habits (created_at, text, session_id) VALUES (?, ?, ?)",
                (created_at, text, session_id),
            )
            self._db.commit()
        return {
            "id": cursor.lastrowid,
            "created_at": created_at,
            "text": text,
            "session_id": session_id,
        }

    def habits(self) -> list[dict]:
        rows = self._query("SELECT id, created_at, text, session_id FROM habits ORDER BY id")
        return [dict(r) for r in rows]
