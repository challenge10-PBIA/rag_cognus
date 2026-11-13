"""post_tool_call (write_file|patch): formata e corrige lint do .py editado com ruff.

Silencioso: o resultado aparece no próximo turno via inject_context.py se algo ficar quebrado.
"""

from __future__ import annotations

import subprocess
import sys

from _common import ROOT, RUNS, log_event, read_payload, rel, reply, tool_path


def main() -> None:
    p = read_payload()
    path = rel(tool_path(p.get("tool_input")))
    if not path or not path.endswith(".py") or not (ROOT / path).exists():
        return reply()
    venv = ROOT / ".venv" / "bin" / "python"
    py = str(venv) if venv.exists() else sys.executable
    subprocess.run([py, "-m", "ruff", "format", path], cwd=ROOT, capture_output=True)
    check = subprocess.run(
        [py, "-m", "ruff", "check", "--fix", "--output-format=concise", path],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    RUNS.mkdir(exist_ok=True)
    lint_file = RUNS / "last_lint.txt"
    if check.returncode != 0:
        lint_file.write_text(check.stdout.strip()[-1500:])
    elif lint_file.exists():
        lint_file.unlink()
    log_event(
        {
            "event": "lint",
            "session": p.get("session_id"),
            "path": path,
            "ok": check.returncode == 0,
        }
    )
    reply()


if __name__ == "__main__":
    main()
