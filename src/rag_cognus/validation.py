"""Gera perguntas para validar o RAG Cognus com >= 50 questões (base para relatório PDF)."""

from __future__ import annotations

METRICS = {  # mesmas notas do judges.py
    "context_relevance": "Relevância do contexto",
    "groundedness": "Fidelidade às fontes",
    "answer_relevance": "Relevância da resposta",
    "accuracy": "Acurácia",
    "professionalism": "Profissionalismo",
}

NICHE_TOPICS = {  # perguntas-base por nicho
    "todos": [
        "Como organizar uma apresentação sobre liderança e comunicação?",
        "Quais técnicas ajudam a responder perguntas difíceis em reuniões?",
        "Que dicas existem para lidar com gagueira e disfluências ao falar em público?",
    ],
}


def generate_validated_questions(niches=None, n_qs: int = 50) -> list[str]:
    """Gera n_qs questões (padrão 50) alternando as perguntas-base dos nichos pedidos."""
    topics = NICHE_TOPICS if not niches else {n: NICHE_TOPICS[n] for n in niches}
    base = [q for questions in topics.values() for q in questions]
    if not base:
        raise ValueError("Nenhuma pergunta-base para os nichos informados.")
    return [f"{base[i % len(base)]} (questão {i + 1:03d})" for i in range(n_qs)]
