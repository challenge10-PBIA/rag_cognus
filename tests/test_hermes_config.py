"""Spec 009 — perfil Hermes: config, Grafana MCP, skills e orquestrador (estático, sem rede)."""

from __future__ import annotations

import fnmatch
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
HERMES = ROOT / "hermes"
SKILLS = HERMES / "skills"
TOKEN_RE = re.compile(r"\bgl(?:sa|c)_[A-Za-z0-9+/=_\-]{16,}")
WRITE_TOOLS = ("update_*", "create_*", "delete_*", "add_*", "patch_*", "ask_assistant")
REF_RE = re.compile(r"`([^`\s]+)`")
REPO_PREFIXES = ("src/", "tests/", "specs/", "hermes/", "docs/", ".claude/")


def _config(tmp_path: Path) -> dict:
    # AC-1: mesma substituição do install.sh (sed "s#__REPO__#$REPO#g").
    text = (HERMES / "config.yaml").read_text(encoding="utf-8")
    text = text.replace("__REPO__", str(tmp_path))
    assert "__REPO__" not in text
    data = yaml.safe_load(text)
    assert isinstance(data, dict)
    return data


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert match, f"{path} sem frontmatter"
    return yaml.safe_load(match.group(1))


def _strings(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return []


# AC-1
def test_config_carrega_e_grafana_desligado(tmp_path):
    grafana = _config(tmp_path)["mcp_servers"]["grafana"]
    assert grafana["enabled"] is False


# AC-2 (ajuste: fonte é o .env do repo, lido pelo wrapper hermes/mcp/grafana.sh)
def test_grafana_usa_wrapper_sem_segredo_no_config(tmp_path):
    grafana = _config(tmp_path)["mcp_servers"]["grafana"]
    assert grafana["command"] == str(tmp_path / "hermes" / "mcp" / "grafana.sh")
    assert grafana.get("lazy") is True
    assert not grafana.get("env"), "URL e token vêm do .env do repo, não do config"
    values = _strings({k: grafana.get(k) for k in ("url", "headers", "env", "args")})
    for value in values:
        assert not TOKEN_RE.search(value), "token literal no config"
        assert "://" not in value and "grafana.net" not in value and "Bearer" not in value
        assert "${" not in value, value


# AC-2
def test_grafana_so_ferramentas_de_leitura(tmp_path):
    include = _config(tmp_path)["mcp_servers"]["grafana"]["tools"]["include"]
    assert include
    for tool in include:
        assert not any(fnmatch.fnmatch(tool, pat) for pat in WRITE_TOOLS), tool


# AC-3
def test_skills_tem_frontmatter_valido():
    folders = sorted(p for p in SKILLS.iterdir() if p.is_dir())
    names = {p.name for p in folders}
    assert {"rag-avatar-agent", "rag-observability-agent"} <= names
    for folder in folders:
        meta = _frontmatter(folder / "SKILL.md")
        assert meta["name"] == folder.name
        assert str(meta.get("description") or "").strip()


# AC-3
@pytest.mark.parametrize("skill", ["rag-avatar-agent", "rag-observability-agent"])
def test_skill_de_agente_cita_caminhos_reais_e_a_criar(skill):
    text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
    existing, future = [], []
    for line in text.splitlines():
        for ref in REF_RE.findall(line):
            path = ref.split("::")[0].rstrip(".,;:")
            if not path.startswith(REPO_PREFIXES):
                continue
            if (ROOT / path).exists():
                existing.append(path)
            else:
                assert "a criar" in line, f"{skill}: `{path}` não existe e não está 'a criar'"
                future.append(path)
    assert any(p.endswith(".py") for p in existing), f"{skill}: nenhum arquivo real citado"
    assert future, f"{skill}: nenhum caminho marcado 'a criar'"
    assert "pytest" in text or "hermes/harness/check.py" in text


# AC-4
def test_orquestrador_tem_papeis_avatar_e_obs():
    text = (SKILLS / "rag-orchestrator" / "SKILL.md").read_text(encoding="utf-8")
    table = [line for line in text.splitlines() if line.startswith("|")]
    for role, skill in (("avatar", "rag-avatar-agent"), ("obs", "rag-observability-agent")):
        assert any(f"`{role}`" in line and skill in line for line in table), role
        assert re.search(rf"^\*\*{role}\*\* .*{skill}", text, re.M | re.S), role


# AC-4
def test_install_sh_valido_e_mostra_grafana_e_paralelo():
    install = HERMES / "install.sh"
    bash = shutil.which("bash")
    assert bash
    proc = subprocess.run([bash, "-n", str(install)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    text = install.read_text(encoding="utf-8")
    assert "GRAFANA_URL" in text and "GRAFANA_SERVICE_ACCOUNT_TOKEN" in text
    assert "config set mcp_servers.grafana.enabled true" in text
    assert "OLLAMA_NUM_PARALLEL 1" in text
    assert not TOKEN_RE.search(text)


# ---------- wrapper stdio do Grafana MCP (lê só 2 chaves do .env do repo) ----------
WRAPPER = HERMES / "mcp" / "grafana.sh"
FAKE_TOKEN = "gl" + "sa_" + "abcdefghijklmnop0123456789"


def _fake_docker(tmp_path: Path) -> tuple[Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    dump = tmp_path / "docker.txt"
    docker = bin_dir / "docker"
    docker.write_text(f'#!/bin/sh\n{{ printf "%s\\n" "$*"; env; }} > "{dump}"\n')
    docker.chmod(0o755)
    return bin_dir, dump


def _run_wrapper(tmp_path: Path, env_text: str, extra_env: dict | None = None):
    bin_dir, dump = _fake_docker(tmp_path)
    env_file = tmp_path / ".env"
    env_file.write_text(env_text, encoding="utf-8")
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "GRAFANA_ENV_FILE": str(env_file)}
    env |= extra_env or {}
    proc = subprocess.run(
        [shutil.which("bash"), str(WRAPPER)], capture_output=True, text=True, env=env
    )
    return proc, dump


def test_wrapper_executavel_e_sintaxe_valida():
    assert WRAPPER.stat().st_mode & 0o111, "grafana.sh precisa ser executável"
    proc = subprocess.run([shutil.which("bash"), "-n", str(WRAPPER)], capture_output=True)
    assert proc.returncode == 0
    text = WRAPPER.read_text(encoding="utf-8")
    assert not TOKEN_RE.search(text)
    assert not re.search(r"^\s*(source|\.)\s", text, re.M), "não pode dar source no .env"
    assert "eval" not in text


def test_wrapper_exporta_so_as_duas_chaves_e_nao_imprime(tmp_path):
    env_text = (
        "# comentário\n"
        "DATABRICKS_TOKEN=dapi-nao-pode-vazar\n"
        "export GRAFANA_URL='https://exemplo.grafana.net'\n"
        f'GRAFANA_SERVICE_ACCOUNT_TOKEN="{FAKE_TOKEN}"\n'
        "OUTRA=$(touch /tmp/nao-executa)\n"
    )
    proc, dump = _run_wrapper(tmp_path, env_text)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == "" and proc.stderr == ""
    lines = dump.read_text().splitlines()
    assert lines[0] == (
        "run --rm -i -e GRAFANA_URL -e GRAFANA_SERVICE_ACCOUNT_TOKEN mcp/grafana -t stdio"
    )
    exported = dict(line.split("=", 1) for line in lines[1:] if "=" in line)
    assert exported["GRAFANA_URL"] == "https://exemplo.grafana.net"
    assert exported["GRAFANA_SERVICE_ACCOUNT_TOKEN"] == FAKE_TOKEN
    assert "DATABRICKS_TOKEN" not in exported and "OUTRA" not in exported


def test_wrapper_ambiente_tem_precedencia(tmp_path):
    env_text = (
        f"GRAFANA_URL=https://do-arquivo.grafana.net\nGRAFANA_SERVICE_ACCOUNT_TOKEN={FAKE_TOKEN}\n"
    )
    proc, dump = _run_wrapper(tmp_path, env_text, {"GRAFANA_URL": "https://do-env.grafana.net"})
    assert proc.returncode == 0, proc.stderr
    assert "GRAFANA_URL=https://do-env.grafana.net" in dump.read_text().splitlines()


def test_wrapper_sem_token_falha_claro_sem_valores(tmp_path):
    env_text = "GRAFANA_URL=https://exemplo.grafana.net\nGRAFANA_SERVICE_ACCOUNT_TOKEN=\n"
    proc, dump = _run_wrapper(tmp_path, env_text)
    assert proc.returncode != 0
    assert not dump.exists(), "não pode chamar o docker sem token"
    assert "GRAFANA_SERVICE_ACCOUNT_TOKEN" in proc.stderr
    assert "exemplo.grafana.net" not in proc.stderr + proc.stdout


# ---------- Spec 015 — desempenho do perfil no Mac de 24 GB ----------
KEEP_TOOLSETS = {"terminal", "file", "skills", "todo", "memory", "delegation"}
DROP_TOOLSETS = {"browser", "code_execution", "image_gen", "tts", "computer_use"}


# AC-1
def test_015_contexto_alinhado_e_ate_32k(tmp_path):
    model = _config(tmp_path)["model"]
    assert model["context_length"] == model["ollama_num_ctx"]
    assert model["ollama_num_ctx"] <= 32768


# AC-2
def test_015_raciocinio_desligado(tmp_path):
    assert _config(tmp_path)["agent"]["reasoning_effort"] == "none"


# AC-3
def test_015_um_filho_por_vez(tmp_path):
    assert _config(tmp_path)["delegation"]["max_concurrent_children"] <= 1


# AC-4
def test_015_toolsets_enxutos(tmp_path):
    disabled = set(_config(tmp_path)["agent"]["disabled_toolsets"])
    assert DROP_TOOLSETS <= disabled
    assert not KEEP_TOOLSETS & disabled


# AC-5
def test_015_compressao_e_grafana(tmp_path):
    cfg = _config(tmp_path)
    assert cfg["compression"]["threshold"] >= 0.75
    grafana = cfg["mcp_servers"]["grafana"]
    assert grafana["enabled"] is False and grafana["lazy"] is True


# AC-6
def test_015_harness_orienta_changed_na_iteracao():
    text = (SKILLS / "rag-harness" / "SKILL.md").read_text(encoding="utf-8")
    assert "--changed" in text and "só no fim" in text


# AC-8
def test_015_install_sugere_um_slot_e_mesmo_contexto(tmp_path):
    text = (HERMES / "install.sh").read_text(encoding="utf-8")
    ctx = _config(tmp_path)["model"]["ollama_num_ctx"]
    assert "launchctl setenv OLLAMA_NUM_PARALLEL 1" in text
    assert f"launchctl setenv OLLAMA_CONTEXT_LENGTH {ctx}" in text
    assert "OLLAMA_FLASH_ATTENTION 1" in text and "OLLAMA_KV_CACHE_TYPE q8_0" in text


# AC-7
def test_015_docs_de_desempenho():
    root = ROOT / "README.md"
    for path in (HERMES / "README.md", root):
        text = path.read_text(encoding="utf-8")
        assert "Ajustes por hardware" in text, path
        for key in ("OLLAMA_FLASH_ATTENTION=1", "OLLAMA_KV_CACHE_TYPE=q8_0", "launchctl setenv"):
            assert key in text, (path, key)
    study = ROOT / "docs" / "estudos" / "hermes-desempenho.md"
    assert study.exists()
    index = (ROOT / "docs" / "estudos" / "README.md").read_text(encoding="utf-8")
    assert "(hermes-desempenho.md)" in index
