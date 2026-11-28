"""Cenários por modo de treino (spec 034): briefing antes de gravar + avaliador do modo."""

from __future__ import annotations

import json

from rag_cognus.scenarios import pitch
from rag_cognus.scenarios.base import ScenarioSkip

# Modo da API → cenário. Modos fora daqui seguem como antes (spec 034 AC-3).
SCENARIOS = {"pitch_venda": pitch}
# Campos internos aceitos além dos do briefing (rodada de objeção, spec 035 AC-6).
INTERNAL_FIELDS = {"pitch_venda": {"objecao_de"}}


def briefing_fields(mode: str) -> list[dict]:
    scenario = SCENARIOS.get(mode)
    return [dict(field) for field in scenario.BRIEFING] if scenario else []


def validate_briefing(mode: str, raw: str | None) -> dict | None:
    """Valida o JSON do formulário. Levanta ValueError com mensagem em português (AC-2)."""
    fields = {f["id"]: f for f in briefing_fields(mode)}
    if not fields:
        if raw not in (None, ""):
            raise ValueError("Este modo não usa briefing.")
        return None
    try:
        data = json.loads(raw) if raw not in (None, "") else {}
    except ValueError as exc:
        raise ValueError("Briefing inválido: envie um JSON.") from exc
    if not isinstance(data, dict):
        raise ValueError("Briefing inválido: envie um objeto JSON.")
    allowed = set(fields) | INTERNAL_FIELDS.get(mode, set())
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ValueError(f"Campo desconhecido no briefing: {', '.join(unknown)}.")
    clean = {}
    for key, value in data.items():
        if not isinstance(value, str):
            raise ValueError(f"O campo {key} do briefing deve ser texto.")
        value = value.strip()
        field = fields.get(key)
        if field and field["max_length"] and len(value) > field["max_length"]:
            raise ValueError(f"O campo {key} aceita até {field['max_length']} caracteres.")
        if field and field["kind"] == "choice" and value not in {o["id"] for o in field["options"]}:
            raise ValueError(f"Opção desconhecida para {key}: {value}.")
        if value:
            clean[key] = value
    for key, field in fields.items():
        if field["required"] and key not in clean:
            raise ValueError(f"Preencha o campo obrigatório do briefing: {key}.")
    return clean


__all__ = ["SCENARIOS", "ScenarioSkip", "briefing_fields", "validate_briefing"]
