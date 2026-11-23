"""Paleta fechada do mascote do perfil (specs 008 e 018). Fonte única: o front lê da API."""

from __future__ import annotations

import copy


def _opts(*rows: tuple[str, str, str | None]) -> list[dict]:
    return [{"id": i, "label": label, "hex": hex_} for i, label, hex_ in rows]


MASCOT_OPTIONS: dict[str, list[dict]] = {
    "figure": _opts(  # spec 018: primeira chave; reinterpreta o desenho, sem cor própria
        ("masculino", "Masculino", None),
        ("feminino", "Feminino", None),
    ),
    "skin": _opts(
        ("pele_1", "Clara", "#F6D5BF"),
        ("pele_2", "Clara média", "#EBBE97"),
        ("pele_3", "Média", "#D39A63"),
        ("pele_4", "Morena", "#B07647"),
        ("pele_5", "Morena escura", "#87553A"),
        ("pele_6", "Escura", "#5A3825"),
    ),
    "headwear": _opts(
        ("gorro", "Gorro de tricô", None),
        ("cabelo_curto", "Cabelo curto", None),
        ("cabelo_cacheado", "Cabelo cacheado", None),
        ("nenhum", "Sem cabelo", None),
    ),
    "headwear_color": _opts(
        ("petroleo", "Petróleo", "#0F4C5C"),
        ("lavanda", "Lavanda", "#7C78D6"),
        ("menta", "Menta", "#4FB38A"),
        ("coral", "Coral", "#E7735A"),
        ("mostarda", "Mostarda", "#E0A82E"),
        ("grafite", "Grafite", "#2E3338"),
        ("castanho", "Castanho", "#6B4226"),
        ("preto", "Preto", "#1B1B1B"),
        ("loiro", "Loiro", "#D8B25A"),
        ("ruivo", "Ruivo", "#B5532B"),
    ),
    "shirt": _opts(
        ("petroleo", "Petróleo", "#0F4C5C"),
        ("branca", "Branca", "#F7F5FA"),
        ("lavanda", "Lavanda", "#7C78D6"),
        ("menta", "Menta", "#4FB38A"),
        ("coral", "Coral", "#E7735A"),
        ("mostarda", "Mostarda", "#E0A82E"),
    ),
}

DEFAULT_MASCOT: dict = {
    "figure": "masculino",
    "skin": "pele_3",
    "headwear": "gorro",
    "headwear_color": "petroleo",
    "shirt": "menta",
}

IDS: dict[str, tuple[str, ...]] = {
    field: tuple(o["id"] for o in options) for field, options in MASCOT_OPTIONS.items()
}


def normalize(raw: object) -> dict:
    """Mascote completo: campo ausente, de tipo errado ou fora da paleta vira o padrão."""
    data = raw if isinstance(raw, dict) else {}
    return {
        field: value
        if isinstance(value := data.get(field), str) and value in IDS[field]
        else DEFAULT_MASCOT[field]
        for field in MASCOT_OPTIONS
    }


def options() -> dict:
    """Corpo de `GET /v1/profile/mascot/options` (cópia: quem recebe pode mutar)."""
    return {"options": copy.deepcopy(MASCOT_OPTIONS), "default": dict(DEFAULT_MASCOT)}
