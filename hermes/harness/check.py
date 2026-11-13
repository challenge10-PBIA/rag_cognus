"""Harness de verificação para agentes: lint, formato e testes com saída curta.

Uso:
    python hermes/harness/check.py              # tudo (igual ao CI)
    python hermes/harness/check.py --changed    # só testes ligados ao diff do git
    python hermes/harness/check.py tests/test_chain.py -k citacao

Grava o resultado em .hermes-runs/last_harness.json (lido pelo painel e pelos hooks).
Sai com código 0 só se todas as etapas passarem.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / ".hermes-runs"
MAX_LINES = 40  # o modelo local lê melhor saídas curtas


def _python() -> str:
    venv = ROOT / ".venv" / "bin" / "python"
    return str(venv) if venv.exists() else sys.executable


def _run(name: str, cmd: list[str]) -> dict:
    started = time.time()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    output = (proc.stdout + proc.stderr).strip().splitlines()
    if proc.returncode != 0:
        # Mantém o fim, onde ficam o resumo e o primeiro erro.
        tail = output[-MAX_LINES:]
    else:
        tail = output[-3:]
    return {
        "step": name,
        "ok": proc.returncode == 0,
        "seconds": round(time.time() - started, 1),
        "cmd": " ".join(cmd),
        "output": tail,
    }


def _changed_files() -> list[str]:
    cmds = (
        ["git", "diff", "--name-only", "HEAD"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    )
    files: set[str] = set()
    for cmd in cmds:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        files.update(line for line in proc.stdout.splitlines() if line.endswith(".py"))
    return sorted(files)


def _tests_for(files: list[str]) -> list[str]:
    tests: set[str] = set()
    for f in files:
        path = Path(f)
        if path.parts and path.parts[0] == "tests" and path.name.startswith("test_"):
            tests.add(f)
        elif path.parts[:2] == ("src", "rag_cognus"):
            candidate = Path("tests") / f"test_{path.stem}.py"
            if (ROOT / candidate).exists():
                tests.add(str(candidate))
    if any(Path(f).name in {"conftest.py", "config.py"} for f in files):
        return []  # mudança transversal: roda tudo
    return sorted(tests)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--changed", action="store_true", help="só testes ligados ao diff")
    parser.add_argument("--no-lint", action="store_true", help="pula ruff")
    args, pytest_args = parser.parse_known_args()

    py = _python()
    steps: list[dict] = []
    lint_paths = ["src", "tests", "hermes"]

    if not args.no_lint:
        steps.append(_run("ruff-check", [py, "-m", "ruff", "check", *lint_paths]))
        steps.append(_run("ruff-format", [py, "-m", "ruff", "format", "--check", *lint_paths]))

    targets = list(pytest_args)
    if args.changed and not targets:
        # Sem teste mapeado (ou mudança transversal) => lista vazia => pytest roda tudo.
        targets = _tests_for(_changed_files())
    steps.append(
        _run(
            "pytest", [py, "-m", "pytest", "-q", "-x", "--tb=short", "-p", "no:warnings", *targets]
        )
    )

    ok = all(s["ok"] for s in steps)
    result = {
        "ok": ok,
        "ts": time.time(),
        "steps": steps,
        "agent": os.environ.get("HERMES_PROFILE"),
    }
    RUNS.mkdir(exist_ok=True)
    (RUNS / "last_harness.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    with (RUNS / "events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "ts": result["ts"],
                    "event": "harness",
                    "ok": ok,
                    "steps": {s["step"]: s["ok"] for s in steps},
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    for s in steps:
        mark = "PASS" if s["ok"] else "FAIL"
        print(f"[{mark}] {s['step']} ({s['seconds']}s) :: {s['cmd']}")
        if not s["ok"]:
            print("\n".join("    " + line for line in s["output"]))
    print("HARNESS OK" if ok else "HARNESS FALHOU — corrija o primeiro erro acima e rode de novo.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
