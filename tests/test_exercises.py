"""Testes do catálogo curado de exercícios (spec 005). Sem rede."""

import copy
import datetime as dt
import json
import re
import socket

import pytest

from rag_cognus import exercises
from rag_cognus.exercises import (
    CATEGORIAS,
    PILARES,
    exercises_for,
    load_exercises,
)

ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

VALIDO = {
    "id": "teste-01",
    "titulo": "Exercício de teste",
    "categoria": "respiracao",
    "pilares": ["pace", "pauses"],
    "passos": ["Faça isto.", "Depois aquilo."],
    "duracao_min": 5,
    "nivel": "iniciante",
    "fonte": {
        "titulo": "Fonte",
        "autor": "Autor",
        "ano": 2019,
        "url": "https://doi.org/10.0000/x",
        "tipo": "artigo",
    },
    "verificado_em": "2026-01-01",
}


def _write(tmp_path, items, aviso="Conteúdo educativo. Não substitui avaliação."):
    path = tmp_path / "ex.json"
    path.write_text(
        json.dumps({"versao": 1, "aviso": aviso, "exercicios": items}), encoding="utf-8"
    )
    return path


def _with(**changes):
    item = copy.deepcopy(VALIDO)
    for key, value in changes.items():
        if "__" in key:
            outer, inner = key.split("__")
            item[outer][inner] = value
        else:
            item[key] = value
    return item


@pytest.fixture
def no_network(monkeypatch):
    def _blocked(*args, **kwargs):
        raise AssertionError("rede acessada durante os testes")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)


# AC-1
def test_ac1_arquivo_real_tem_campos_e_tipos(no_network):
    items = load_exercises()
    assert isinstance(items, list) and items
    for item in items:
        assert isinstance(item["id"], str) and item["id"]
        assert isinstance(item["titulo"], str) and item["titulo"].strip()
        assert item["categoria"] in CATEGORIAS
        assert item["pilares"] and set(item["pilares"]) <= set(PILARES)
        assert len(item["pilares"]) == len(set(item["pilares"]))
        assert len(item["passos"]) >= 2 and all(p.strip() for p in item["passos"])
        assert isinstance(item["duracao_min"], int) and 1 <= item["duracao_min"] <= 30
        assert item["nivel"] in ("iniciante", "intermediario", "avancado")
        fonte = item["fonte"]
        assert fonte["titulo"].strip() and fonte["autor"].strip()
        assert 1950 <= fonte["ano"] <= dt.date.today().year
        assert fonte["url"].startswith("https://")
        assert fonte["tipo"] in ("artigo", "livro", "instituicao")
        assert dt.date.fromisoformat(item["verificado_em"]) <= dt.date.today()


# AC-2
def test_ac2_campo_ausente_cita_id_e_campo(tmp_path):
    item = copy.deepcopy(VALIDO)
    del item["fonte"]
    with pytest.raises(ValueError, match="teste-01") as err:
        load_exercises(_write(tmp_path, [item]))
    assert "fonte" in str(err.value)


def test_ac2_sem_id_cita_indice(tmp_path):
    item = copy.deepcopy(VALIDO)
    del item["id"]
    with pytest.raises(ValueError, match=r"0") as err:
        load_exercises(_write(tmp_path, [item]))
    assert "id" in str(err.value)


def test_ac2_subcampo_de_fonte_ausente(tmp_path):
    item = copy.deepcopy(VALIDO)
    del item["fonte"]["autor"]
    with pytest.raises(ValueError, match="autor"):
        load_exercises(_write(tmp_path, [item]))


# AC-3
@pytest.mark.parametrize(
    ("changes", "valor"),
    [
        ({"pilares": ["pace", "tom"]}, "tom"),
        ({"categoria": "danca"}, "danca"),
        ({"nivel": "expert"}, "expert"),
        ({"fonte__tipo": "blog"}, "blog"),
    ],
)
def test_ac3_valor_fora_da_lista_e_citado(tmp_path, changes, valor):
    with pytest.raises(ValueError, match=valor):
        load_exercises(_write(tmp_path, [_with(**changes)]))


def test_ac3_pilares_vazio_ou_repetido(tmp_path):
    with pytest.raises(ValueError, match="pilares"):
        load_exercises(_write(tmp_path, [_with(pilares=[])]))
    with pytest.raises(ValueError, match="pilares"):
        load_exercises(_write(tmp_path, [_with(pilares=["pace", "pace"])]))


def test_passos_e_duracao_invalidos(tmp_path):
    with pytest.raises(ValueError, match="passos"):
        load_exercises(_write(tmp_path, [_with(passos=["só um"])]))
    with pytest.raises(ValueError, match="duracao_min"):
        load_exercises(_write(tmp_path, [_with(duracao_min=45)]))
    with pytest.raises(ValueError, match="duracao_min"):
        load_exercises(_write(tmp_path, [_with(duracao_min=True)]))


# AC-4
@pytest.mark.parametrize("url", ["http://exemplo.org", "", "ftp://x"])
def test_ac4_url_sem_https(tmp_path, url):
    with pytest.raises(ValueError, match="https"):
        load_exercises(_write(tmp_path, [_with(fonte__url=url)]))


# AC-5
@pytest.mark.parametrize(
    "changes",
    [
        {"verificado_em": "16/11/2026"},
        {"verificado_em": (dt.date.today() + dt.timedelta(days=1)).isoformat()},
        {"fonte__ano": 1949},
        {"fonte__ano": dt.date.today().year + 1},
        {"fonte__ano": "2019"},
    ],
)
def test_ac5_datas_e_ano_invalidos(tmp_path, changes):
    with pytest.raises(ValueError):
        load_exercises(_write(tmp_path, [_with(**changes)]))


# AC-6
def test_ac6_ids_reais_unicos_e_kebab():
    ids = [item["id"] for item in load_exercises()]
    assert len(ids) == len(set(ids))
    assert all(ID_RE.match(i) for i in ids)


def test_ac6_id_duplicado_ou_fora_do_padrao(tmp_path):
    with pytest.raises(ValueError, match="teste-01"):
        load_exercises(_write(tmp_path, [VALIDO, copy.deepcopy(VALIDO)]))
    with pytest.raises(ValueError, match="Teste_01"):
        load_exercises(_write(tmp_path, [_with(id="Teste_01")]))


# AC-7
def test_ac7_cobertura_minima():
    items = load_exercises()
    assert len(items) >= 12
    for pilar in PILARES:
        n = sum(pilar in item["pilares"] for item in items)
        assert n >= 2, f"pilar {pilar} tem {n} exercício(s)"
    for cat in CATEGORIAS:
        assert any(item["categoria"] == cat for item in items), f"sem categoria {cat}"
    assert len({item["fonte"]["url"] for item in items}) >= 3


# AC-8
def test_ac8_aviso_no_topo():
    raw = json.loads(exercises.DEFAULT_PATH.read_text(encoding="utf-8"))
    assert "não substitui" in raw["aviso"]
    assert "fonoaudiológica" in raw["aviso"]


def test_ac8_aviso_ausente_falha(tmp_path):
    with pytest.raises(ValueError, match="aviso"):
        load_exercises(_write(tmp_path, [VALIDO], aviso=""))


# AC-9
def test_ac9_exercises_for_filtra_e_mantem_ordem():
    todos = [item["id"] for item in load_exercises() if "pauses" in item["pilares"]]
    got = exercises_for("pauses", limit=2)
    assert len(got) <= 2
    assert all("pauses" in item["pilares"] for item in got)
    assert [item["id"] for item in got] == todos[:2]
    assert exercises_for("pauses", limit=0) == []


# AC-10
def test_ac10_pilar_invalido_lista_validos():
    with pytest.raises(ValueError) as err:
        exercises_for("tom")
    for pilar in PILARES:
        assert pilar in str(err.value)


# AC-11
def test_ac11_sem_rede(no_network, tmp_path):
    load_exercises()
    load_exercises(_write(tmp_path, [VALIDO]))
    exercises_for("diction", limit=1)
