"""pre_tool_call: bloqueia comandos destrutivos, arquivos protegidos e (opcional) código sem teste.

TDD estrito é opt-in: exporte HERMES_TDD_STRICT=1 antes de abrir o Hermes. Nesse modo,
editar `src/rag_cognus/<mod>.py` só é permitido se `tests/test_<mod>.py` já estiver
modificado no diff (o teste vermelho vem primeiro).
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from _common import ROOT, log_event, read_payload, rel, reply, tool_path

DANGEROUS = [
    (r"\brm\s+-\w*r\w*\s+(/|~|\$HOME|\.{1,2}/?)(\s|$)", "rm -r em raiz/home/projeto inteiro"),
    (r"\bgit\s+push\b", "git push só com pedido explícito do usuário"),
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard descarta trabalho"),
    (r"\bgit\s+clean\s+-[a-z]*f", "git clean -f apaga arquivos não versionados"),
    (r"\bgit\s+checkout\s+--\s+\.", "git checkout -- . descarta alterações"),
    (
        r"\brag-cognus\s+(sync-gold|evaluate)\b",
        "comando acessa Databricks/LLM real; peça ao usuário",
    ),
    (r"databricks://", "tracking no Databricks é proibido neste projeto"),
    (r"\bcat\s+\.env\b|\bprintenv\b.*TOKEN", "não exponha segredos do .env"),
]
PROTECTED = (".env", "uv.lock", "mlruns/", "mlartifacts/", "data/", ".git/")
WRITE_TOOLS = {"write_file", "patch", "edit_file", "create_file"}


def _block(reason: str, payload: dict) -> None:
    log_event(
        {
            "event": "blocked",
            "session": payload.get("session_id"),
            "tool": payload.get("tool_name"),
            "reason": reason,
        }
    )
    reply({"decision": "block", "reason": f"[guard] {reason}"})


def _modified(path: str) -> bool:
    out = subprocess.run(
        ["git", "status", "--porcelain", "--", path], cwd=ROOT, capture_output=True, text=True
    ).stdout
    return bool(out.strip())


def main() -> None:
    p = read_payload()
    tool = p.get("tool_name") or ""
    tool_input = p.get("tool_input") or {}

    if tool == "terminal":
        cmd = str(tool_input.get("command") or tool_input.get("cmd") or "")
        for pattern, reason in DANGEROUS:
            if re.search(pattern, cmd):
                return _block(f"{reason}: `{cmd[:120]}`", p)
        return reply()

    if tool in WRITE_TOOLS:
        path = rel(tool_path(tool_input)) or ""
        if any(path == item.rstrip("/") or path.startswith(item) for item in PROTECTED):
            return _block(f"arquivo protegido: {path}", p)
        if os.environ.get("HERMES_TDD_STRICT") == "1":
            parts = Path(path).parts
            if parts[:2] == ("src", "rag_cognus") and path.endswith(".py"):
                test = Path("tests") / f"test_{Path(path).stem}.py"
                if (ROOT / test).exists() and not _modified(str(test)):
                    return _block(
                        f"TDD estrito: escreva/atualize {test} (teste vermelho) antes de editar "
                        f"{path}",
                        p,
                    )
    reply()


if __name__ == "__main__":
    main()
