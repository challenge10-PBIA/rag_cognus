import pytest
from pydantic import BaseModel

from rag_cognus.config import Settings
from rag_cognus.llm import make_ollama


def test_llm_settings_from_env(monkeypatch):  # AC-1
    monkeypatch.setenv("OLLAMA_NUM_CTX", "32768")
    monkeypatch.setenv("OLLAMA_KEEP_ALIVE", "1h")
    monkeypatch.setenv("OLLAMA_FAST_MODEL", "qwen3.5:4b")
    settings = Settings.from_env()
    assert (settings.num_ctx, settings.keep_alive, settings.fast) == (32768, "1h", "qwen3.5:4b")


def test_llm_settings_defaults(monkeypatch):  # AC-1
    for name in ("OLLAMA_NUM_CTX", "OLLAMA_KEEP_ALIVE", "OLLAMA_FAST_MODEL"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings.from_env()
    assert (settings.num_ctx, settings.keep_alive) == (16384, "30m")
    assert settings.fast == settings.chat_model


def test_rejects_tiny_context():  # AC-1
    with pytest.raises(ValueError, match="num_ctx"):
        Settings(num_ctx=1024)


def test_make_ollama_uses_shared_context():  # AC-1
    class Out(BaseModel):
        text: str

    chat = make_ollama(Settings(num_ctx=12000, keep_alive="5m"), Out, model="m", num_predict=99)
    assert (chat.model, chat.num_ctx, chat.keep_alive, chat.num_predict) == ("m", 12000, "5m", 99)
    assert chat.format == Out.model_json_schema()


ONLINE_VARS = ("MLFLOW_ONLINE_EXPERIMENT", "RAG_ONLINE_EVAL", "SPEECH_PLEONASM_LLM")


def test_online_eval_defaults(monkeypatch):  # spec 004 AC-D1
    for name in ONLINE_VARS:
        monkeypatch.delenv(name, raising=False)
    settings = Settings.from_env()
    assert settings.online_experiment == "rag-cognus-online"
    assert settings.online_eval is True
    assert settings.speech_pleonasm_llm is False


def test_online_eval_from_env(monkeypatch):  # spec 004 AC-D1 + spec 003
    monkeypatch.setenv("MLFLOW_ONLINE_EXPERIMENT", "meu-online")
    monkeypatch.setenv("RAG_ONLINE_EVAL", "false")
    monkeypatch.setenv("SPEECH_PLEONASM_LLM", "1")
    settings = Settings.from_env()
    assert (settings.online_experiment, settings.online_eval) == ("meu-online", False)
    assert settings.speech_pleonasm_llm is True


def test_invalid_bool_flag_is_rejected(monkeypatch):  # spec 004 AC-D1
    monkeypatch.setenv("RAG_ONLINE_EVAL", "talvez")
    with pytest.raises(ValueError, match="RAG_ONLINE_EVAL"):
        Settings.from_env()


def test_tracking_uri_still_rejects_databricks(monkeypatch):  # spec 004 AC-D1
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "databricks://perfil")
    with pytest.raises(ValueError, match="não é um MLflow local"):
        Settings.from_env()


def test_env_example_documents_online_eval():  # spec 004 AC-D2
    from pathlib import Path

    text = (Path(__file__).parents[1] / ".env.example").read_text()
    assert "MLFLOW_TRACKING_URI=http://127.0.0.1:5001" in text
    for name in ("MLFLOW_EXPERIMENT_NAME=", "MLFLOW_ONLINE_EXPERIMENT=", "RAG_ONLINE_EVAL="):
        assert name in text
    assert "SPEECH_PLEONASM_LLM=" in text
    assert "autoavaliação" in text


# ---------- spec 010: opções do LLM por papel ----------

LLM_VARS = (
    "OLLAMA_TEMPERATURE",
    "OLLAMA_JUDGE_TEMPERATURE",
    "OLLAMA_FAST_TEMPERATURE",
    "OLLAMA_SEED",
    "OLLAMA_TOP_P",
    "OLLAMA_TOP_K",
    "OLLAMA_REPEAT_PENALTY",
    "OLLAMA_PRESENCE_PENALTY",
    "OLLAMA_JUDGE_PRESENCE_PENALTY",
    "OLLAMA_GENERATOR_NUM_PREDICT",
    "OLLAMA_JUDGE_NUM_PREDICT",
    "OLLAMA_FAST_NUM_PREDICT",
    "OLLAMA_THINK",
    "OLLAMA_JUDGE_THINK",
    "OLLAMA_JUDGE_NUM_CTX",
    "OLLAMA_FAST_NUM_CTX",
    "OLLAMA_TIMEOUT",
)
SAMPLING = ("top_p", "top_k", "repeat_penalty", "presence_penalty", "seed")


@pytest.fixture
def clean_llm_env(monkeypatch):
    for name in (*LLM_VARS, "OLLAMA_NUM_CTX", "OLLAMA_KEEP_ALIVE", "OLLAMA_FAST_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("OLLAMA_JUDGE_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_CHAT_MODEL", raising=False)
    return monkeypatch


class Out(BaseModel):
    text: str


@pytest.mark.parametrize("role", ["generator", "judge", "fast"])
def test_ollama_options_defaults_match_current_payload(clean_llm_env, role):  # 010 AC-1
    from rag_cognus.llm import ollama_options

    options = ollama_options(Settings.from_env(), role)
    assert options["temperature"] == 0 and options["think"] is False
    assert (options["num_ctx"], options["keep_alive"], options["timeout"]) == (16384, "30m", 300)
    assert not set(SAMPLING) & set(options)


def test_llm_role_settings_from_env(clean_llm_env):  # 010 AC-2
    values = {
        "OLLAMA_TEMPERATURE": "0.2",
        "OLLAMA_JUDGE_TEMPERATURE": "0",
        "OLLAMA_FAST_TEMPERATURE": "0.1",
        "OLLAMA_SEED": "42",
        "OLLAMA_TOP_P": "0.8",
        "OLLAMA_TOP_K": "20",
        "OLLAMA_REPEAT_PENALTY": "1.0",
        "OLLAMA_PRESENCE_PENALTY": "0",
        "OLLAMA_JUDGE_PRESENCE_PENALTY": "0.5",
        "OLLAMA_GENERATOR_NUM_PREDICT": "1000",
        "OLLAMA_JUDGE_NUM_PREDICT": "800",
        "OLLAMA_FAST_NUM_PREDICT": "256",
        "OLLAMA_THINK": "false",
        "OLLAMA_JUDGE_THINK": "true",
        "OLLAMA_JUDGE_NUM_CTX": "8192",
        "OLLAMA_FAST_NUM_CTX": "4096",
        "OLLAMA_TIMEOUT": "120",
    }
    for name, value in values.items():
        clean_llm_env.setenv(name, value)
    s = Settings.from_env()
    assert (s.temperature, s.judge_temperature, s.fast_temperature) == (0.2, 0.0, 0.1)
    assert (s.seed, s.top_p, s.llm_top_k, s.repeat_penalty) == (42, 0.8, 20, 1.0)
    assert (s.presence_penalty, s.judge_presence_penalty) == (0.0, 0.5)
    assert (s.generator_num_predict, s.judge_num_predict, s.fast_num_predict) == (1000, 800, 256)
    assert (s.think, s.judge_think) == (False, True)
    assert (s.judge_num_ctx, s.fast_num_ctx, s.timeout) == (8192, 4096, 120.0)


@pytest.mark.parametrize(
    "name,value",
    [
        ("OLLAMA_TEMPERATURE", "2.5"),
        ("OLLAMA_JUDGE_TEMPERATURE", "-0.1"),
        ("OLLAMA_FAST_TEMPERATURE", "3"),
        ("OLLAMA_TOP_P", "0"),
        ("OLLAMA_TOP_P", "1.5"),
        ("OLLAMA_GENERATOR_NUM_PREDICT", "10"),
        ("OLLAMA_JUDGE_NUM_PREDICT", "63"),
        ("OLLAMA_TIMEOUT", "0"),
        ("OLLAMA_SEED", "abc"),
    ],
)
def test_invalid_llm_settings_name_the_variable(clean_llm_env, name, value):  # 010 AC-2
    clean_llm_env.setenv(name, value)
    with pytest.raises(ValueError, match=name):
        Settings.from_env()


def test_unknown_role_is_rejected():  # 010 AC-2
    from rag_cognus.llm import ollama_options

    with pytest.raises(ValueError, match="Papel"):
        ollama_options(Settings(), "critico")
    with pytest.raises(ValueError, match="Papel"):
        make_ollama(Settings(), Out, role="critico")


def test_make_ollama_sends_explicit_options():  # 010 AC-3
    from langchain_core.messages import HumanMessage

    settings = Settings(presence_penalty=0.0, repeat_penalty=1.0, seed=42, top_p=0.8)
    chat = make_ollama(settings, Out, role="generator", num_predict=900)
    params = chat._chat_params([HumanMessage("x")])
    assert params["options"] == {
        "presence_penalty": 0.0,
        "repeat_penalty": 1.0,
        "seed": 42,
        "top_p": 0.8,
        "temperature": 0,
        "num_ctx": 16384,
        "num_predict": 900,
    }
    assert params["think"] is False


def test_default_payload_is_unchanged():  # 010 AC-1/AC-3: sem variáveis novas = payload atual
    from langchain_core.messages import HumanMessage

    params = make_ollama(Settings(), Out, num_predict=700)._chat_params([HumanMessage("x")])
    assert params["options"] == {"temperature": 0, "num_ctx": 16384, "num_predict": 700}
    assert params["think"] is False and params["keep_alive"] == "30m"


@pytest.mark.parametrize("role,field", [("judge", "judge"), ("fast", "fast")])
def test_role_num_ctx_only_for_another_model(role, field):  # 010 AC-4
    from rag_cognus.llm import ollama_options

    ctx = {f"{field}_num_ctx": 8192}
    for same in ("", "qwen3.5:9b"):
        settings = Settings(**ctx, **{f"{field}_model": same})
        assert ollama_options(settings, role)["num_ctx"] == 16384
    settings = Settings(**ctx, **{f"{field}_model": "outro:7b"})
    assert ollama_options(settings, role)["num_ctx"] == 8192
    assert ollama_options(settings, role)["model"] == "outro:7b"


def _record_roles(monkeypatch):
    """Troca make_ollama por um gravador que ainda constrói o ChatOllama (sem rede)."""
    import rag_cognus.llm as llm

    calls = []
    real = llm.make_ollama

    def recorder(settings, schema, *, role="generator", **kwargs):
        chat = real(settings, schema, role=role, **kwargs)
        calls.append((schema.__name__, role, chat.num_predict))
        return chat

    for module in (
        "rag_cognus.chain",
        "rag_cognus.judges",
        "rag_cognus.agents.evidence",
        "rag_cognus.agents.communication",
        "rag_cognus.agents.agents_judges",
        "rag_cognus.llm",  # api.app importa make_ollama dentro de make_pleonasm_checker
    ):
        monkeypatch.setattr(f"{module}.make_ollama", recorder)
    return calls


def _build_all(documents, settings):
    from rag_cognus.agents.agents_judges import make_communication_judge, make_evidence_judge
    from rag_cognus.agents.communication import CommunicationAgent
    from rag_cognus.agents.evidence import EvidenceAgent
    from rag_cognus.api.app import make_pleonasm_checker
    from rag_cognus.chain import RagPipeline
    from rag_cognus.judges import make_judge
    from rag_cognus.retrieval import GoldRetriever

    retriever = GoldRetriever(documents, settings)
    RagPipeline(retriever, settings)
    EvidenceAgent(retriever, settings)
    CommunicationAgent(settings)
    make_judge(settings)
    make_evidence_judge(settings)
    make_communication_judge(settings)
    make_pleonasm_checker(settings)


def test_each_call_declares_its_role(monkeypatch, documents):  # 010 AC-5
    calls = _record_roles(monkeypatch)
    _build_all(documents, Settings())
    assert [(name, role) for name, role, _ in calls] == [
        ("Answer", "generator"),
        ("SubQuestions", "fast"),
        ("SynthesisDraft", "generator"),
        ("AdaptationDraft", "generator"),
        ("ResponseJudgment", "judge"),
        ("EvidenceJudgment", "judge"),
        ("CommunicationJudgment", "judge"),
        ("PleonasmCheck", "fast"),
    ]


def test_num_predict_defaults_and_role_override(monkeypatch, documents):  # 010 AC-6
    calls = _record_roles(monkeypatch)
    _build_all(documents, Settings())
    assert [n for _, _, n in calls] == [900, 200, 1200, 1500, 700, 600, 600, 300]
    calls.clear()
    _build_all(documents, Settings(judge_num_predict=1000))
    assert [n for _, _, n in calls] == [900, 200, 1200, 1500, 1000, 1000, 1000, 300]
    calls.clear()
    _build_all(documents, Settings(fast_num_predict=250))
    assert [n for _, _, n in calls] == [900, 250, 1200, 1500, 700, 600, 600, 250]


def _load_env_example(monkeypatch):
    from pathlib import Path

    text = (Path(__file__).parents[1] / ".env.example").read_text()
    names = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        value = value.split("#", 1)[0].strip()
        names.append(name.strip())
        monkeypatch.setenv(name.strip(), value)
    return names


def test_env_example_keeps_current_options(clean_llm_env):  # 010 AC-9
    from rag_cognus.llm import ollama_options

    _load_env_example(clean_llm_env)
    clean_llm_env.setenv("DATABRICKS_HOST", "")
    clean_llm_env.setenv("DATABRICKS_TOKEN", "")
    settings = Settings.from_env()
    for role in ("generator", "judge", "fast"):
        options = ollama_options(settings, role)
        assert options["temperature"] == 0 and options["think"] is False
        assert (options["num_ctx"], options["timeout"]) == (16384, 300)
        assert not set(SAMPLING) & set(options)


@pytest.mark.xfail(
    strict=True, reason="aguarda colar o bloco da spec 010 no .env.example (remova o xfail)"
)
def test_env_example_lists_llm_variables(clean_llm_env):  # 010 AC-9
    names = _load_env_example(clean_llm_env)
    assert set(LLM_VARS) <= set(names)
    assert "OLLAMA_FAST_MODEL" in names and not Settings.from_env().fast_model
