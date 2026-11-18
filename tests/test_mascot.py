"""Spec 008 — paleta fechada do mascote (AC-1)."""

import pytest

from rag_cognus import mascot

FIELDS = ("skin", "headwear", "headwear_color", "shirt")


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
        "skin": "pele_3",
        "headwear": "gorro",
        "headwear_color": "petroleo",
        "shirt": "menta",
    }
    assert mascot.DEFAULT_MASCOT == default

    custom = {"skin": "pele_6", "headwear": "nenhum", "headwear_color": "ruivo", "shirt": "coral"}
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
