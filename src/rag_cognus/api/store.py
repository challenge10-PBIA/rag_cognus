"""Persistência local do produto (SQLite + áudio em disco). Nada sai da máquina."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

DEFAULT_PROFILE = {"name": "Você", "daily_goal_minutes": 10, "mascot": None}

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
CREATE TABLE IF NOT EXISTS evaluations (
    ask_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    judge_model TEXT,
    mlflow_logged INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    metrics_json TEXT,
    judges_json TEXT
);
CREATE TABLE IF NOT EXISTS app_state (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL
);
"""
INTERRUPTED = "Avaliação interrompida."


class Store:
    def __init__(self, folder: str | Path):
        self.folder = Path(folder)
        self.audio_dir = self.folder / "sessions"
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.folder / "cognus.db", check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(SCHEMA)
        # Spec 006, AC-11: bancos antigos ganham a coluna sem perder hábitos (idempotente).
        columns = {r["name"] for r in self._db.execute("PRAGMA table_info(habits)")}
        if "exercise_id" not in columns:
            self._db.execute("ALTER TABLE habits ADD COLUMN exercise_id TEXT")
        # Spec 008, AC-5: perfil antigo ganha o mascote (JSON) sem perder nome e meta.
        columns = {r["name"] for r in self._db.execute("PRAGMA table_info(profile)")}
        if "mascot_json" not in columns:
            self._db.execute("ALTER TABLE profile ADD COLUMN mascot_json TEXT")
        # Avaliação pendente de um processo anterior nunca vai terminar (spec 004, AC-4).
        self._db.execute(
            "UPDATE evaluations SET status = 'error', error = ? WHERE status = 'pending'",
            (INTERRUPTED,),
        )
        self._db.commit()

    def _query(self, sql: str, params=()) -> list[sqlite3.Row]:
        with self._lock:
            rows = self._db.execute(sql, params).fetchall()
            self._db.commit()
            return rows

    # ---------- perfil ----------
    def profile(self) -> dict:
        """Perfil salvo; `mascot` é o JSON gravado (dict) ou None se ausente/ilegível."""
        rows = self._query("SELECT name, daily_goal_minutes, mascot_json FROM profile WHERE id = 1")
        if not rows:
            return dict(DEFAULT_PROFILE)
        row = dict(rows[0])
        try:
            mascot = json.loads(row.pop("mascot_json") or "null")
        except ValueError:
            mascot = None  # JSON corrompido: a API aplica o padrão (spec 008 AC-4)
        return row | {"mascot": mascot}

    def save_profile(self, name: str, daily_goal_minutes: int, mascot: dict | None = None) -> dict:
        """`mascot=None` mantém o salvo; um dict substitui o objeto inteiro (spec 008 AC-3)."""
        mascot_json = None if mascot is None else json.dumps(mascot, ensure_ascii=False)
        self._query(
            "INSERT INTO profile (id, name, daily_goal_minutes, mascot_json) VALUES (1, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET name = excluded.name, "
            "daily_goal_minutes = excluded.daily_goal_minutes, "
            "mascot_json = COALESCE(excluded.mascot_json, profile.mascot_json)",
            (name, daily_goal_minutes, mascot_json),
        )
        return self.profile()

    # ---------- estado do app (spec 009 AC-10, spec 010 AC-6) ----------
    def state(self, key: str, default=None):
        rows = self._query("SELECT value_json FROM app_state WHERE key = ?", (key,))
        if not rows:
            return default
        try:
            return json.loads(rows[0]["value_json"])
        except ValueError:
            return default

    def set_state(self, key: str, value) -> None:
        self._query(
            "INSERT INTO app_state (key, value_json) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json",
            (key, json.dumps(value, ensure_ascii=False)),
        )

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
    def add_habit(
        self,
        created_at: str,
        text: str,
        session_id: str | None,
        exercise_id: str | None = None,
    ) -> dict:
        with self._lock:
            cursor = self._db.execute(
                "INSERT INTO habits (created_at, text, session_id, exercise_id) "
                "VALUES (?, ?, ?, ?)",
                (created_at, text, session_id, exercise_id),
            )
            self._db.commit()
        return {
            "id": cursor.lastrowid,
            "created_at": created_at,
            "text": text,
            "session_id": session_id,
            "exercise_id": exercise_id,
        }

    def habits(self) -> list[dict]:
        rows = self._query(
            "SELECT id, created_at, text, session_id, exercise_id FROM habits ORDER BY id"
        )
        return [dict(r) for r in rows]

    # ---------- avaliação online do /v1/ask (spec 004) ----------
    def create_evaluation(
        self, ask_id: str, created_at: str, status: str, judge_model: str | None
    ) -> None:
        self._query(
            "INSERT INTO evaluations (ask_id, created_at, status, judge_model) VALUES (?, ?, ?, ?)",
            (ask_id, created_at, status, judge_model),
        )

    def finish_evaluation(
        self,
        ask_id: str,
        finished_at: str,
        status: str,
        *,
        metrics: dict | None = None,
        judges: list[dict] | None = None,
        mlflow_logged: bool = False,
        error: str | None = None,
    ) -> None:
        self._query(
            "UPDATE evaluations SET finished_at = ?, status = ?, metrics_json = ?, "
            "judges_json = ?, mlflow_logged = ?, error = ? WHERE ask_id = ?",
            (
                finished_at,
                status,
                None if metrics is None else json.dumps(metrics, ensure_ascii=False),
                None if judges is None else json.dumps(judges, ensure_ascii=False),
                int(mlflow_logged),
                error,
                ask_id,
            ),
        )

    def evaluation(self, ask_id: str) -> dict | None:
        rows = self._query("SELECT * FROM evaluations WHERE ask_id = ?", (ask_id,))
        if not rows:
            return None
        row = dict(rows[0])
        return {
            "ask_id": row["ask_id"],
            "status": row["status"],
            "metrics": json.loads(row["metrics_json"]) if row["metrics_json"] else None,
            "judges": json.loads(row["judges_json"]) if row["judges_json"] else [],
            "judge_model": row["judge_model"],
            "mlflow_logged": bool(row["mlflow_logged"]),
            "error": row["error"],
            "created_at": row["created_at"],
            "finished_at": row["finished_at"],
        }
