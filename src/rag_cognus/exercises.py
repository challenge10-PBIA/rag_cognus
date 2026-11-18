"""Catálogo curado de exercícios de comunicação oral (spec 005).

Lê `data/exercicios.json` (versionado no git). Nada vem do Databricks nem de LLM.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = ROOT / "data" / "exercicios.json"

PILARES = ("pace", "pauses", "fillers", "clarity", "diction")
CATEGORIAS = (
    "respiracao",
    "articulacao",
    "aquecimento_vocal",
    "ritmo_pausas",
    "vicios_linguagem",
    "projecao",
)
NIVEIS = ("iniciante", "intermediario", "avancado")
TIPOS_FONTE = ("artigo", "livro", "instituicao")
CAMPOS = (
    "id",
    "titulo",
    "categoria",
    "pilares",
    "passos",
    "duracao_min",
    "nivel",
    "fonte",
    "verificado_em",
)
CAMPOS_FONTE = ("titulo", "autor", "ano", "url", "tipo")
_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _texto(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _inteiro(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validar(item, idx: int) -> None:
    if not isinstance(item, dict):
        raise ValueError(f"exercício no índice {idx}: deve ser um objeto")
    ref = item.get("id") if _texto(item.get("id")) else f"índice {idx}"

    def erro(campo: str, msg: str) -> ValueError:
        return ValueError(f"exercício {ref}: campo '{campo}' {msg}")

    for campo in CAMPOS:
        if campo not in item:
            raise erro(campo, "ausente")
    if not _texto(item["id"]) or not _ID_RE.match(item["id"]):
        raise erro("id", f"inválido: {item['id']!r} (use kebab-case minúsculo)")
    if not _texto(item["titulo"]):
        raise erro("titulo", "vazio")
    if item["categoria"] not in CATEGORIAS:
        raise erro("categoria", f"inválida: {item['categoria']!r}; válidas: {CATEGORIAS}")
    pilares = item["pilares"]
    if not isinstance(pilares, list) or not pilares:
        raise erro("pilares", "deve ser lista não vazia")
    for pilar in pilares:
        if pilar not in PILARES:
            raise erro("pilares", f"valor inválido: {pilar!r}; válidos: {PILARES}")
    if len(set(pilares)) != len(pilares):
        raise erro("pilares", "tem itens repetidos")
    passos = item["passos"]
    if not isinstance(passos, list) or len(passos) < 2 or not all(map(_texto, passos)):
        raise erro("passos", "deve ter ao menos 2 textos não vazios")
    dur = item["duracao_min"]
    if not _inteiro(dur) or not 1 <= dur <= 30:
        raise erro("duracao_min", f"deve ser inteiro entre 1 e 30, veio {dur!r}")
    if item["nivel"] not in NIVEIS:
        raise erro("nivel", f"inválido: {item['nivel']!r}; válidos: {NIVEIS}")

    fonte = item["fonte"]
    if not isinstance(fonte, dict):
        raise erro("fonte", "deve ser um objeto")
    for campo in CAMPOS_FONTE:
        if campo not in fonte:
            raise erro(f"fonte.{campo}", "ausente")
    for campo in ("titulo", "autor"):
        if not _texto(fonte[campo]):
            raise erro(f"fonte.{campo}", "vazio")
    hoje = dt.date.today()
    ano = fonte["ano"]
    if not _inteiro(ano) or not 1950 <= ano <= hoje.year:
        raise erro("fonte.ano", f"deve ser inteiro entre 1950 e {hoje.year}, veio {ano!r}")
    url = fonte["url"]
    if not isinstance(url, str) or not url.startswith("https://"):
        raise erro("fonte.url", f"deve começar com https://, veio {url!r}")
    if fonte["tipo"] not in TIPOS_FONTE:
        raise erro("fonte.tipo", f"inválido: {fonte['tipo']!r}; válidos: {TIPOS_FONTE}")

    verificado = item["verificado_em"]
    try:
        data = dt.date.fromisoformat(verificado)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", verificado):
            raise ValueError
    except (TypeError, ValueError):
        raise erro("verificado_em", f"deve ser data ISO AAAA-MM-DD, veio {verificado!r}")
    if data > hoje:
        raise erro("verificado_em", f"não pode ser futura: {verificado}")


def load_exercises(path: Path | None = None) -> list[dict]:
    """Lê e valida o catálogo; devolve a lista `exercicios` na ordem do arquivo."""
    path = Path(path) if path is not None else DEFAULT_PATH
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("catálogo deve ser um objeto JSON com 'aviso' e 'exercicios'")
    if not _texto(raw.get("aviso")):
        raise ValueError("catálogo sem campo 'aviso' (aviso educativo obrigatório)")
    items = raw.get("exercicios")
    if not isinstance(items, list):
        raise ValueError("catálogo sem lista 'exercicios'")
    vistos: set[str] = set()
    for idx, item in enumerate(items):
        _validar(item, idx)
        if item["id"] in vistos:
            raise ValueError(f"exercício {item['id']}: campo 'id' duplicado")
        vistos.add(item["id"])
    return items


@lru_cache(maxsize=1)
def _catalogo() -> tuple[dict, ...]:
    return tuple(load_exercises())


def exercises_for(pillar: str, limit: int = 2) -> list[dict]:
    """Até `limit` exercícios do catálogo padrão que treinam `pillar`, na ordem do arquivo."""
    if pillar not in PILARES:
        raise ValueError(f"pilar inválido: {pillar!r}; válidos: {', '.join(PILARES)}")
    if limit <= 0:
        return []
    found = [item for item in _catalogo() if pillar in item["pilares"]]
    return [json.loads(json.dumps(item)) for item in found[:limit]]
