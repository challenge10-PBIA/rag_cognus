"""Spec 009 AC-5 — guard bloqueia exposição de tokens do Grafana (sem rede)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parents[1] / "hermes" / "hooks" / "guard.py"
# Montados por concatenação para o próprio guard não barrar a escrita deste arquivo.
FAKE_SA = "gl" + "sa_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6_0a1b2c3d"
FAKE_CLOUD = "gl" + "c_" + "eyJvIjoiMTIzIiwibiI6InN0YWNrIiwiayI6ImFiYyJ9"


def _run(tool: str, tool_input: dict) -> subprocess.CompletedProcess:
    payload = {"tool_name": tool, "tool_input": tool_input, "session_id": "teste"}
    return subprocess.run(
        [sys.executable, str(GUARD)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=GUARD.parent,
    )


@pytest.mark.parametrize(
    "cmd",
    [
        "echo $GRAFANA_SERVICE_ACCOUNT_TOKEN",
        "echo ${GRAFANA_SERVICE_ACCOUNT_TOKEN}",
        "printenv GRAFANA_SERVICE_ACCOUNT_TOKEN",
        f"export GRAFANA_SERVICE_ACCOUNT_TOKEN={FAKE_SA}",
        f"curl -H 'Authorization: Bearer {FAKE_CLOUD}' https://x.grafana.net/api/health",
    ],
)
def test_guard_bloqueia_token_no_terminal(cmd):
    proc = _run("terminal", {"command": cmd})
    assert proc.returncode == 2
    assert "[guard]" in proc.stderr
    assert "token" in proc.stderr.lower() or "segredo" in proc.stderr.lower()
    assert FAKE_SA not in proc.stderr and FAKE_CLOUD not in proc.stderr


@pytest.mark.parametrize(
    ("tool", "tool_input"),
    [
        ("write_file", {"path": "notas.txt", "content": f"token={FAKE_SA}\n"}),
        ("patch", {"path": "hermes/config.yaml", "patch": f"+  token: {FAKE_CLOUD}\n"}),
        ("Edit", {"file_path": "x.md", "old_string": "a", "new_string": FAKE_SA}),
    ],
)
def test_guard_bloqueia_token_em_arquivo(tool, tool_input):
    proc = _run(tool, tool_input)
    assert proc.returncode == 2
    assert "token" in proc.stderr.lower()
    assert FAKE_SA not in proc.stderr and FAKE_CLOUD not in proc.stderr


@pytest.mark.parametrize(
    ("tool", "tool_input"),
    [
        ("terminal", {"command": "curl -s http://127.0.0.1:5001/health"}),
        ("write_file", {"path": "docs/x.md", "content": "Tokens começam com `glsa_`.\n"}),
    ],
)
def test_guard_libera_uso_normal(tool, tool_input):
    proc = _run(tool, tool_input)
    assert proc.returncode == 0, proc.stderr
