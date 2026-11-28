"""Fábrica única do ChatOllama: opções por papel (gerador, juiz, rápido) vindas do .env.

Usar sempre o mesmo num_ctx por modelo evita que o Ollama recarregue o modelo entre o RAG,
o juiz e os agentes. A saída é forçada a seguir o schema JSON do Pydantic.

Spec 010: as opções são enviadas explicitamente. O que fica vazio no .env não é enviado e
continua valendo o Modelfile do modelo (ex.: repeat_penalty 1.12 no deepseek-v4.1-flash).
"""

from __future__ import annotations

from functools import cache, wraps

import mlflow
from pydantic import BaseModel

from rag_cognus.config import Settings

ROLES = ("generator", "judge", "fast")
# Opções de amostragem que só vão ao Ollama quando definidas no .env.
SAMPLING = ("seed", "top_p", "top_k", "repeat_penalty", "presence_penalty")
# Chaves de `options` no payload do /api/chat.
REQUEST_OPTIONS = ("temperature", "num_ctx", "num_predict", *SAMPLING)


def role_model(settings: Settings, role: str) -> str:
    _check_role(role)
    return {"generator": settings.chat_model, "judge": settings.judge, "fast": settings.fast}[role]


def _check_role(role: str) -> None:
    if role not in ROLES:
        raise ValueError(f"Papel de LLM desconhecido: {role!r} (use generator, judge ou fast).")


def ollama_options(
    settings: Settings, role: str, *, model: str | None = None, num_predict: int | None = None
) -> dict:
    """Opções efetivas de um papel. `num_predict` é o padrão da chamada; o .env tem precedência."""
    _check_role(role)
    model = model or role_model(settings, role)
    temperature, env_predict, think, role_ctx = {
        "generator": (settings.temperature, settings.generator_num_predict, settings.think, None),
        "judge": (
            settings.judge_temperature,
            settings.judge_num_predict,
            settings.judge_think,
            settings.judge_num_ctx,
        ),
        "fast": (
            settings.fast_temperature,
            settings.fast_num_predict,
            settings.think,
            settings.fast_num_ctx,
        ),
    }[role]
    # Mesmo modelo do chat = mesmo num_ctx, senão o Ollama recarrega o modelo.
    same_model = model == settings.chat_model
    presence = settings.presence_penalty
    if role == "judge" and settings.judge_presence_penalty is not None:
        presence = settings.judge_presence_penalty
    options = {
        "model": model,
        "temperature": temperature,
        "think": think,
        "num_ctx": settings.num_ctx if same_model or role_ctx is None else role_ctx,
        "keep_alive": settings.keep_alive,
        "timeout": settings.timeout,
    }
    if (predict := env_predict or num_predict) is not None:
        options["num_predict"] = predict
    sampling = {
        "seed": settings.seed,
        "top_p": settings.top_p,
        "top_k": settings.llm_top_k,
        "repeat_penalty": settings.repeat_penalty,
        "presence_penalty": presence,
    }
    options.update({k: v for k, v in sampling.items() if v is not None})
    return options


def llm_attributes(settings: Settings, role: str, *, num_predict: int | None = None) -> dict:
    """Atributos dos spans LLM (spec 011 AC-10): modelo, papel e opções efetivas."""
    options = ollama_options(settings, role, num_predict=num_predict)
    return {"model": options["model"], "role": role, "options": options}


def tag_llm_span(attributes: dict) -> None:
    span = mlflow.get_current_active_span()
    if span is not None:
        span.set_attributes(attributes)


def untraced_outside_span(fn):
    """Juiz fora de um span manual não abre trace próprio com o autolog (spec 036 AC-2).

    Dentro de um trace as chamadas LangChain seguem como filhas; fora dele, a amostragem 0
    descarta o trace solto (ex.: scorers do `mlflow.genai.evaluate` e o juiz online).
    """
    hidden = mlflow.trace(fn, sampling_ratio_override=0.0)

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if mlflow.get_current_active_span() is None:
            return hidden(*args, **kwargs)
        return fn(*args, **kwargs)

    return wrapper


def trace_tags(settings: Settings, flow: str) -> dict:
    """Tags comuns dos traces (spec 011): os filtros da UI usam `flow`."""
    return {"flow": flow, "chat_model": settings.chat_model, "judge_model": settings.judge}


@cache
def _chat_class():
    from langchain_ollama import ChatOllama

    class OptionsChatOllama(ChatOllama):
        """ChatOllama que envia `options` explícitas (o 1.1.0 não tem presence_penalty)."""

        request_options: dict | None = None

        def _chat_params(self, messages, stop=None, **kwargs):
            if self.request_options is not None and "options" not in kwargs:
                options = dict(self.request_options)
                if stop is not None or self.stop is not None:
                    options["stop"] = stop if stop is not None else self.stop
                kwargs["options"] = options
            return super()._chat_params(messages, stop, **kwargs)

    return OptionsChatOllama


def strict_format(schema: type[BaseModel]) -> dict:
    """JSON schema do `format` com todos os campos obrigatórios, inclusive os aninhados.

    Spec 033: o deepseek-v4.1-flash omitia campos com default (`fontes`, `cited_chunk_ids`)
    e a resposta caía em "sem fontes". O Pydantic continua aceitando o JSON sem eles.
    """
    fmt = schema.model_json_schema()
    for node in (fmt, *fmt.get("$defs", {}).values()):
        if "properties" in node:
            node["required"] = list(node["properties"])
    return fmt


def make_ollama(
    settings: Settings,
    schema: type[BaseModel],
    *,
    role: str = "generator",
    model: str | None = None,
    num_predict: int = 600,
):
    options = ollama_options(settings, role, model=model, num_predict=num_predict)
    return _chat_class()(
        model=options["model"],
        base_url=settings.ollama_url,
        temperature=options["temperature"],
        reasoning=options["think"],  # o raciocínio (think) do modelo base Qwen3.5 triplica o tempo
        format=strict_format(schema),
        num_ctx=options["num_ctx"],
        num_predict=options["num_predict"],
        seed=options.get("seed"),
        top_p=options.get("top_p"),
        top_k=options.get("top_k"),
        repeat_penalty=options.get("repeat_penalty"),
        keep_alive=options["keep_alive"],
        client_kwargs={"timeout": options["timeout"]},
        request_options={k: options[k] for k in REQUEST_OPTIONS if k in options},
    )
