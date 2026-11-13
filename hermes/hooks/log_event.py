"""Hook genérico: registra qualquer evento do Hermes em .hermes-runs/events.jsonl.

Alimenta o painel `hermes/monitor/app.py`. Nunca bloqueia nada (sempre responde {}).
"""

from __future__ import annotations

import json

from _common import log_event, read_payload, rel, reply, tool_path

MAX_FIELD = 600


def _short(value) -> str | None:
    if value is None:
        return None
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= MAX_FIELD else text[:MAX_FIELD] + "…"


def main() -> None:
    p = read_payload()
    event = p.get("hook_event_name") or "unknown"
    extra = p.get("extra") or {}
    tool_input = p.get("tool_input")
    record = {
        "event": event,
        "session": p.get("session_id"),
        "profile": p.get("profile"),
        "tool": p.get("tool_name"),
        "path": rel(tool_path(tool_input)),
        "input": _short(tool_input),
    }
    if event == "post_tool_call":
        record["result"] = _short(extra.get("result") or extra.get("output"))
        record["status"] = extra.get("status")
    if event == "subagent_stop":
        record.update(
            parent=extra.get("parent_session_id") or p.get("session_id"),
            role=extra.get("child_role"),
            status=extra.get("child_status"),
            summary=_short(extra.get("child_summary")),
            duration_ms=extra.get("duration_ms"),
            tools=[
                {k: t.get(k) for k in ("tool_name", "status", "input_bytes", "output_bytes")}
                for t in (extra.get("tool_call_history") or [])
                if isinstance(t, dict)
            ],
        )
    # Guarda as chaves extras desconhecidas (ids de subagente, task etc.) de forma resumida.
    record["extra_keys"] = sorted(extra.keys()) if isinstance(extra, dict) else None
    for key in ("subagent_id", "task_id", "delegation_id", "child_session_id", "depth", "goal"):
        if isinstance(extra, dict) and key in extra:
            record[key] = _short(extra[key])
    log_event(record)
    reply()


if __name__ == "__main__":
    main()
