"""Fábrica única do ChatOllama: mesmo num_ctx/keep_alive em todas as chamadas.

Usar sempre o mesmo num_ctx por modelo evita que o Ollama recarregue o modelo entre o RAG,
o juiz e os agentes. A saída é forçada a seguir o schema JSON do Pydantic.
"""

from __future__ import annotations

from pydantic import BaseModel

from rag_cognus.config import Settings


def make_ollama(
    settings: Settings,
    schema: type[BaseModel],
    *,
    model: str | None = None,
    num_predict: int = 600,
):
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=model or settings.chat_model,
        base_url=settings.ollama_url,
        temperature=0,
        reasoning=False,  # o modo de raciocínio do Qwen triplica o tempo
        format=schema.model_json_schema(),
        num_ctx=settings.num_ctx,
        num_predict=num_predict,
        keep_alive=settings.keep_alive,
        client_kwargs={"timeout": 300},
    )
