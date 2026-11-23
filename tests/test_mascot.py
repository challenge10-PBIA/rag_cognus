"""Specs 008 e 018 — paleta fechada do mascote (008 AC-1; 018 AC-1…AC-3)."""

import pytest

from rag_cognus import mascot

FIELDS = ("figure", "skin", "headwear", "headwear_color", "shirt")


def test_ac1_options_default_and_normalize():  # AC-1
    options = mascot.MASCOT_OPTIONS
    assert tuple(options) == FIELDS
    assert [o["id"] for o in options["skin"]] == [f"pele_{i}" for i in range(1, 7)]
    assert options["skin"][0] == {"id": "pele_1", "label": "Clara", "hex": "#F6D5BF"}
    assert [o["id"] for o in options["headwear"]] == [
        "gorro",
        "cabelo_curto",
        "cabelo_cacheado",
        "nenhum",
    ]
    assert all(o["hex"] is None for o in options["headwear"])
    assert len(options["headwear_color"]) == 10 and len(options["shirt"]) == 6
    assert options["shirt"][1] == {"id": "branca", "label": "Branca", "hex": "#F7F5FA"}
    for field in FIELDS:
        ids = [o["id"] for o in options[field]]
        assert len(ids) == len(set(ids))
        assert all(set(o) == {"id", "label", "hex"} and o["label"] for o in options[field])
    default = {
        "figure": "masculino",
        "skin": "pele_3",
        "headwear": "gorro",
        "headwear_color": "petroleo",
        "shirt": "menta",
    }
    assert mascot.DEFAULT_MASCOT == default

    custom = {
        "figure": "feminino",
        "skin": "pele_6",
        "headwear": "nenhum",
        "headwear_color": "ruivo",
        "shirt": "coral",
    }
    assert mascot.normalize(custom) == custom
    assert mascot.normalize(custom | {"extra": 1}) == custom
    assert mascot.normalize({"skin": "pele_1", "shirt": 7, "headwear": "chapeu"}) == (
        default | {"skin": "pele_1"}
    )
    for raw in (None, "texto", [], 3):
        assert mascot.normalize(raw) == default
    mascot.normalize(custom)["skin"] = "x"
    assert mascot.DEFAULT_MASCOT["skin"] == "pele_3"  # devolve cópia


@pytest.mark.parametrize("field", FIELDS)
def test_ac1_unknown_id_falls_back_per_field(field):  # AC-1
    assert mascot.normalize({field: "inexistente"}) == mascot.DEFAULT_MASCOT


# ---------- spec 018: figura feminina ----------
OLD_FIELDS = {
    "skin": "pele_5",
    "headwear": "cabelo_cacheado",
    "headwear_color": "ruivo",
    "shirt": "coral",
}


def test_018_ac1_figure_is_first_and_others_unchanged():  # spec 018 AC-1
    options = mascot.MASCOT_OPTIONS
    assert next(iter(options)) == "figure"
    assert options["figure"] == [
        {"id": "masculino", "label": "Masculino", "hex": None},
        {"id": "feminino", "label": "Feminino", "hex": None},
    ]
    assert mascot.IDS["figure"] == ("masculino", "feminino")
    assert [len(options[f]) for f in FIELDS[1:]] == [6, 4, 10, 6]
    assert [o["hex"] for o in options["skin"]] == [
        "#F6D5BF",
        "#EBBE97",
        "#D39A63",
        "#B07647",
        "#87553A",
        "#5A3825",
    ]
    assert [o["id"] for o in options["headwear_color"]] == [
        "petroleo",
        "lavanda",
        "menta",
        "coral",
        "mostarda",
        "grafite",
        "castanho",
        "preto",
        "loiro",
        "ruivo",
    ]
    assert [o["id"] for o in options["shirt"]] == [
        "petroleo",
        "branca",
        "lavanda",
        "menta",
        "coral",
        "mostarda",
    ]


def test_018_ac2_default_mascot():  # spec 018 AC-2
    assert mascot.DEFAULT_MASCOT == {
        "figure": "masculino",
        "skin": "pele_3",
        "headwear": "gorro",
        "headwear_color": "petroleo",
        "shirt": "menta",
    }
    assert mascot.options()["default"] == mascot.DEFAULT_MASCOT


@pytest.mark.parametrize("figure", [7, None, "outro", "", "Feminino"])
def test_018_ac3_bad_figure_becomes_masculino(figure):  # spec 018 AC-3
    got = mascot.normalize(OLD_FIELDS | {"figure": figure})
    assert got == OLD_FIELDS | {"figure": "masculino"}
    assert tuple(got) == FIELDS


def test_018_ac3_feminino_kept_and_old_mascot_gets_masculino():  # spec 018 AC-3
    assert mascot.normalize(OLD_FIELDS | {"figure": "feminino"}) == OLD_FIELDS | {
        "figure": "feminino"
    }
    assert mascot.normalize(OLD_FIELDS) == OLD_FIELDS | {"figure": "masculino"}
