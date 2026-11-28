"""Peças comuns dos cenários (spec 034)."""

from __future__ import annotations

import re
import unicodedata


class ScenarioSkip(Exception):
    """O avaliador não roda (ex.: fala curta). A mensagem vai para `mode_result_error`."""


def normalize(text: str) -> str:
    """Minúsculas, sem acento nem pontuação, espaços únicos: compara trecho com a fala."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())
