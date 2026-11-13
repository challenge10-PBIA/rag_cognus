"""Utilitários compartilhados pelos hooks do Hermes (somente stdlib)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / ".hermes-runs"
EVENTS = RUNS / "events.jsonl"


def read_payload() -> dict:
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return {}


def reply(obj: dict | None = None) -> None:
    sys.stdout.write(json.dumps(obj or {}, ensure_ascii=False))


def log_event(record: dict) -> None:
    RUNS.mkdir(exist_ok=True)
    record.setdefault("ts", time.time())
    with EVENTS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def tool_path(tool_input: dict | None) -> str | None:
    if not isinstance(tool_input, dict):
        return None
    for key in ("path", "file_path", "filename", "target_file"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def rel(path: str | None) -> str | None:
    if not path:
        return None
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return path
