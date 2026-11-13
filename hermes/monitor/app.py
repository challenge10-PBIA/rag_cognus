"""Painel ao vivo dos agentes Hermes no rag_cognus.

    .venv/bin/streamlit run hermes/monitor/app.py --server.port 8502

Fontes:
- `.hermes-runs/events.jsonl`  — gravado pelos hooks (tool calls, bloqueios, subagent_stop,
  lint, harness).
- `$HERMES_HOME/cache/delegation/live/<delegation_id>/task-<n>.log` — log ao vivo que o
  Hermes escreve para cada subagente.
"""

from __future__ import annotations

import json
import os
import time
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / ".hermes-runs"
EVENTS = RUNS / "events.jsonl"
ACTIVE_SECONDS = 15


def _hermes_homes() -> list[Path]:
    homes = []
    if os.environ.get("HERMES_HOME"):
        homes.append(Path(os.environ["HERMES_HOME"]))
    base = Path.home() / ".hermes"
    homes.append(base / "profiles" / os.environ.get("HERMES_PROFILE_NAME", "ragdev"))
    homes.append(base)
    return [h for h in homes if h.exists()]


def load_events(limit: int) -> pd.DataFrame:
    if not EVENTS.exists():
        return pd.DataFrame()
    lines = EVENTS.read_text(encoding="utf-8").splitlines()[-limit:]
    rows = []
    for line in lines:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    df = pd.DataFrame(rows)
    if not df.empty and "ts" in df:
        df["hora"] = df["ts"].map(lambda t: time.strftime("%H:%M:%S", time.localtime(t)))
    if "event" not in df:
        df["event"] = None
    if "session" not in df:
        df["session"] = None
    return df


def delegation_tasks() -> list[dict]:
    tasks = []
    for home in _hermes_homes():
        live = home / "cache" / "delegation" / "live"
        if not live.exists():
            continue
        for log in live.glob("*/task-*.log"):
            stat = log.stat()
            tasks.append(
                {
                    "delegation": log.parent.name,
                    "task": log.stem,
                    "path": log,
                    "mtime": stat.st_mtime,
                    "size": stat.st_size,
                    "active": time.time() - stat.st_mtime < ACTIVE_SECONDS,
                }
            )
    return sorted(tasks, key=lambda t: t["mtime"], reverse=True)


def tail(path: Path, n: int) -> str:
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - 64_000))
            text = fh.read().decode("utf-8", errors="replace")
    except OSError as exc:
        return f"(erro lendo log: {exc})"
    return "\n".join(text.splitlines()[-n:])


def role_of(text: str | None) -> str:
    if text and text.startswith("[") and "]" in text:
        return text[1 : text.index("]")]
    return "—"


st.set_page_config(page_title="Hermes · subagentes", layout="wide")
st.title("Hermes · subagentes do rag_cognus")

with st.sidebar:
    refresh = st.slider("Atualizar a cada (s)", 1, 30, 2)
    max_events = st.number_input("Eventos carregados", 100, 50_000, 3000, step=500)
    log_lines = st.slider("Linhas por log de subagente", 10, 400, 60)
    only_active = st.toggle("Só subagentes ativos", value=False)
    st.caption(f"Eventos: `{EVENTS}`")
    st.caption("Hermes home: " + (", ".join(f"`{h}`" for h in _hermes_homes()) or "nenhum"))
    if st.button("Limpar eventos", type="secondary") and EVENTS.exists():
        EVENTS.unlink()


@st.fragment(run_every=refresh)
def live_view() -> None:
    df = load_events(int(max_events))
    tasks = delegation_tasks()

    active = [t for t in tasks if t["active"]]
    harness_file = RUNS / "last_harness.json"
    harness = json.loads(harness_file.read_text()) if harness_file.exists() else None
    tool_calls = int((df["event"] == "pre_tool_call").sum()) if not df.empty else 0
    blocked = int((df["event"] == "blocked").sum()) if not df.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Subagentes ativos", len(active), help=f"log alterado nos últimos {ACTIVE_SECONDS}s")
    c2.metric("Tool calls", tool_calls)
    c3.metric("Bloqueados pelo guard", blocked)
    c4.metric(
        "Harness",
        "—" if harness is None else ("OK" if harness["ok"] else "FALHOU"),
        help=None if harness is None else time.strftime("%H:%M:%S", time.localtime(harness["ts"])),
    )

    tab_live, tab_done, tab_tl, tab_h = st.tabs(
        ["Subagentes ao vivo", "Subagentes concluídos", "Linha do tempo", "Harness"]
    )

    with tab_live:
        shown = active if only_active else tasks[:12]
        if not shown:
            st.info(
                "Nenhum log de subagente ainda. Eles aparecem quando o agente chama "
                "`delegate_task`. No terminal do Hermes: Ctrl+T (ou F6) abre o roster ao vivo."
            )
        for t in shown:
            dot = "🟢" if t["active"] else "⚪"
            age = int(time.time() - t["mtime"])
            label = f"{dot} {t['delegation']} / {t['task']} · {age}s atrás · {t['size'] // 1024} KB"
            with st.expander(label, expanded=t["active"]):
                st.code(tail(t["path"], log_lines), language="text")
                st.caption(f"`tail -f {t['path']}`")

    with tab_done:
        stops = df[df["event"] == "subagent_stop"] if not df.empty else pd.DataFrame()
        if stops.empty:
            st.info("Nenhum subagent_stop registrado ainda.")
        for _, row in stops.iloc[::-1].iterrows():
            status = row.get("status") or "?"
            icon = {"completed": "✅", "failed": "❌", "error": "💥", "interrupted": "⏸"}.get(
                status, "•"
            )
            dur = row.get("duration_ms")
            dur_s = f"{dur / 1000:.1f}s" if isinstance(dur, (int, float)) else "?"
            goal = row.get("goal") or row.get("summary") or ""
            title = f"{icon} [{role_of(goal) if row.get('goal') else row.get('role') or '—'}] "
            title += f"{status} · {dur_s} · pai {str(row.get('parent'))[:8]}"
            with st.expander(title):
                if row.get("goal"):
                    st.markdown(f"**Objetivo:** {row['goal']}")
                st.markdown(f"**Resumo devolvido:**\n\n{row.get('summary') or '_vazio_'}")
                tools = row.get("tools")
                if isinstance(tools, list) and tools:
                    st.dataframe(pd.DataFrame(tools), hide_index=True, use_container_width=True)
                    counts = Counter(t.get("tool_name") for t in tools)
                    st.caption(" · ".join(f"{k}×{v}" for k, v in counts.most_common()))

    with tab_tl:
        if df.empty:
            st.info("Sem eventos. Confirme que o Hermes foi aberto com o perfil ragdev.")
        else:
            sessions = sorted(df["session"].dropna().unique().tolist())
            pick = st.multiselect("Sessões", sessions, default=sessions[-4:], key="sess")
            kinds = sorted(df["event"].dropna().unique().tolist())
            default_kinds = [
                k for k in kinds if k in {"pre_tool_call", "blocked", "subagent_stop", "harness"}
            ]
            ev = st.multiselect("Eventos", kinds, default=default_kinds, key="kinds")
            view = df[df["event"].isin(ev)]
            if pick:
                view = view[view["session"].isin(pick) | view["session"].isna()]
            if not view.empty and "session" in view:
                per = view.groupby(view["session"].fillna("—").str[:8])["event"].count()
                st.bar_chart(per, horizontal=True, height=160)
            cols = [
                c
                for c in ("hora", "session", "event", "tool", "path", "reason", "status", "input")
                if c in view
            ]
            st.dataframe(view[cols].iloc[::-1], hide_index=True, use_container_width=True)

    with tab_h:
        if harness is None:
            st.info("Rode `python hermes/harness/check.py`.")
        else:
            for s in harness["steps"]:
                st.markdown(f"{'✅' if s['ok'] else '❌'} **{s['step']}** · {s['seconds']}s")
                if not s["ok"]:
                    st.code("\n".join(s["output"]), language="text")
        lint = RUNS / "last_lint.txt"
        if lint.exists():
            st.warning("Lint pendente após a última edição")
            st.code(lint.read_text(), language="text")


live_view()
