"""pre_llm_call: injeta estado mínimo do repo (arquivos alterados, harness, lint).

Mantido bem curto porque roda a cada chamada do modelo, inclusive nos subagentes.
"""

from __future__ import annotations

import json
import subprocess
import time

from _common import ROOT, RUNS, read_payload, reply

MAX_FILES = 12


def main() -> None:
    read_payload()
    lines: list[str] = []

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True
    ).stdout.splitlines()
    if status:
        shown = ", ".join(s[3:] for s in status[:MAX_FILES])
        more = f" (+{len(status) - MAX_FILES})" if len(status) > MAX_FILES else ""
        lines.append(f"Arquivos alterados: {shown}{more}")

    harness = RUNS / "last_harness.json"
    if harness.exists():
        try:
            data = json.loads(harness.read_text())
            age = int((time.time() - data.get("ts", 0)) / 60)
            failed = [s["step"] for s in data.get("steps", []) if not s.get("ok")]
            state = "OK" if data.get("ok") else f"FALHOU em {', '.join(failed)}"
            lines.append(f"Último harness: {state} (há {age} min)")
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    lint = RUNS / "last_lint.txt"
    if lint.exists():
        lines.append("Lint pendente após última edição:\n" + lint.read_text()[:600])

    reply({"context": "[estado do repo]\n" + "\n".join(lines)} if lines else {})


if __name__ == "__main__":
    main()
