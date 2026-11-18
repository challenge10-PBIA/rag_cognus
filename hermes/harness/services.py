"""Status dos serviços locais (e do Grafana, se configurado) em uma linha cada.

Uso:
    python hermes/harness/services.py

Faz um GET sem autenticação (timeout de 2 s) em cada serviço e grava o resultado em
.hermes-runs/services.json; o hook inject_context repassa esse cache ao modelo por 5 min,
sem fazer rede a cada chamada. Nunca envia nem imprime tokens: o Grafana responde
/api/health sem credencial. Só stdlib.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".hermes-runs" / "services.json"
TIMEOUT = 2.0
REPO_ENV = ROOT / ".env"  # só GRAFANA_URL é lida daqui; o token nunca

HttpGet = Callable[[str, float], int]


def http_get(url: str, timeout: float) -> int:
    """Status HTTP do GET, ou 0 se não conectou. Sem cabeçalhos de autenticação."""
    request = urllib.request.Request(url, headers={"User-Agent": "rag-cognus-services"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:  # noqa: S310
            return int(resp.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except (OSError, ValueError):
        return 0


def _env_file_value(key: str, env_file: Path) -> str:
    """Lê só a chave pedida do .env do repo, linha a linha (sem executar nada)."""
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, sep, value = line.strip().partition("=")
            if sep and name.removeprefix("export ").strip() == key:
                return value.strip().strip("'\"")
    except OSError:
        pass
    return ""


def targets(env: Mapping[str, str], env_file: Path | None = None) -> list[tuple[str, str]]:
    mlflow = env.get("MLFLOW_TRACKING_URI", "")
    if not mlflow.startswith(("http://", "https://")):
        mlflow = "http://127.0.0.1:5001"
    ollama = env.get("OLLAMA_BASE_URL") or "http://127.0.0.1:11434"
    found = [
        ("mlflow", mlflow.rstrip("/") + "/health"),
        ("ollama", ollama.rstrip("/") + "/api/tags"),
        ("api", "http://127.0.0.1:8001/v1/health"),
    ]
    grafana = env.get("GRAFANA_URL") or (
        _env_file_value("GRAFANA_URL", env_file) if env_file else ""
    )
    if grafana.startswith(("http://", "https://")):
        found.append(("grafana", grafana.rstrip("/") + "/api/health"))
    return found


def check(get: HttpGet, env: Mapping[str, str], env_file: Path | None = None) -> list[dict]:
    results = []
    for name, url in targets(env, env_file):
        status = get(url, TIMEOUT)
        results.append({"name": name, "url": url, "up": 200 <= status < 400, "status": status})
    return results


def main(
    http_get: HttpGet = http_get,
    env: Mapping[str, str] | None = None,
    out: Path = CACHE,
    env_file: Path | None = None,
) -> int:
    if env is None:
        env, env_file = os.environ, REPO_ENV
    results = check(http_get, env, env_file)
    for item in results:
        mark = "UP" if item["up"] else "DOWN"
        print(f"[{mark}] {item['name']} {item['url']}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"ts": time.time(), "services": results}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
