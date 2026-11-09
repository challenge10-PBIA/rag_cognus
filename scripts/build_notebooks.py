import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write(name, cells):
    output = []
    for index, (kind, text) in enumerate(cells):
        cell = {
            "cell_type": kind,
            "id": f"cell-{index + 1:02}",
            "metadata": {},
            "source": text.strip().splitlines(keepends=True),
        }
        if kind == "code":
            cell.update(execution_count=None, outputs=[])
        output.append(cell)
    nb = {
        "cells": output,
        "metadata": {
            "kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
            "language_info": {"name": "python", "version": "3.12"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    (ROOT / "notebooks" / name).write_text(json.dumps(nb, ensure_ascii=False, indent=2))


write(
    "01_databricks_avaliacao.ipynb",
    [
        (
            "markdown",
            """# Avaliação da recuperação sobre a Gold — Databricks

Este notebook lê `cognus.gold.vw_rag_conhecimento` com Spark e registra os experimentos
no MLflow do Workspace. Não depende do Ollama para a busca BM25.

O `localhost` do cluster não é o Mac do usuário. A geração pelo Qwen instalado no
Mac está no notebook local 02. Não exponha o Ollama à internet para executar este notebook.
As referências iniciais são rascunhos: sem anotação humana, não haverá Precision/Recall reais.

Execute no Git folder deste repositório ou na cópia do projeto em `/Workspace/Users/<usuario>/rag_cognus`.
""",
        ),
        (
            "code",
            '''%pip install "langchain-core>=1,<2" "langchain-ollama>=1,<2" "mlflow>=3.6,<4" "rank-bm25>=0.2.2,<0.3" "databricks-sdk>=0.70,<1" "python-dotenv>=1,<2"''',
        ),
        ("code", "dbutils.library.restartPython()"),
        (
            "code",
            """from pathlib import Path
import sys
from dataclasses import replace

# Git folder: procura o projeto a partir da pasta atual.
candidates = [Path.cwd(), *Path.cwd().parents]
PROJECT_ROOT = next((p for p in candidates if (p / "src/rag_cognus").is_dir()), None)
if PROJECT_ROOT is None:
    user = spark.sql("SELECT current_user() AS user").first().user
    PROJECT_ROOT = Path("/Workspace/Users") / user / "rag_cognus"
if not (PROJECT_ROOT / "src/rag_cognus").is_dir():
    raise FileNotFoundError("Ajuste PROJECT_ROOT para a pasta deste repositório no Workspace.")
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from rag_cognus.config import Settings
from rag_cognus.gold import load_from_spark
from rag_cognus.retrieval import GoldRetriever
from rag_cognus.evaluation import evaluate, load_cases

user = spark.sql("SELECT current_user() AS user").first().user
settings = replace(Settings(), tracking_uri="databricks",
                   experiment=f"/Users/{user}/rag_cognus_avaliacoes")
documents = load_from_spark(spark, settings.gold_view)
print("Trechos elegíveis lidos da Gold:", len(documents))
cases = load_cases(PROJECT_ROOT / "data/evaluation/questions.jsonl")""",
        ),
        (
            "code",
            """summaries = []
for k in (3, 5):
    config = replace(settings, backend="bm25", top_k=k)
    retriever = GoldRetriever(documents, config)
    summary = evaluate(cases, retriever, config,
                       output_dir="/tmp/rag-cognus-evaluation",
                       run_name=f"gold-bm25-k{k}")
    summaries.append(summary)
    print(summary)
if any(s["metrics"]["error_rate"] for s in summaries):
    raise RuntimeError("Há erros por pergunta; consulte per_case.json no MLflow.")""",
        ),
        (
            "markdown",
            """## Como interpretar

Abra o experimento `/Users/<usuario>/rag_cognus_avaliacoes` e compare os runs.
`niche_metadata_precision_proxy` mede concordância com rótulos da própria Gold,
não relevância semântica. Como as consultas não recebem o nicho esperado como
filtro, não usamos a resposta esperada para facilitar a recuperação.

`precision_at_k`, `recall_at_k`, `hit_at_k` e `mrr_at_k` só aparecem quando há
`label_status=human_verified` e referências de trechos que existem neste snapshot.
Revise candidatos e edite o dataset antes de comparar qualidade real.

O snapshot pode ser salvo com `save_snapshot` para levar os mesmos trechos à
execução local. O comando local `rag-cognus sync-gold` já faz essa leitura diretamente
via SQL Warehouse, sem publicar os documentos no GitHub.
""",
        ),
    ],
)
write(
    "02_local_qwen.ipynb",
    [
        (
            "markdown",
            """# RAG local — Qwen3.5 9B / Ollama + Gold + MLflow

Execute localmente depois de instalar o projeto e copiar `.env.example` para `.env`.
Configure o SQL Warehouse e autentique com `databricks auth login --profile projeto`.
O modelo `qwen3.5:9b` gera respostas; `embeddinggemma:latest` é usado somente
quando `backend=dense`. A Gold já está segmentada: não há nova divisão dos trechos.
""",
        ),
        (
            "code",
            """from pathlib import Path
import sys
from dataclasses import replace
from dotenv import load_dotenv

PROJECT_ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents]
                    if (p / "src/rag_cognus").is_dir())
sys.path.insert(0, str(PROJECT_ROOT / "src"))
load_dotenv(PROJECT_ROOT / ".env")
from rag_cognus.config import Settings
from rag_cognus.gold import load_from_databricks, load_snapshot, save_snapshot
from rag_cognus.retrieval import GoldRetriever
from rag_cognus.chain import RagPipeline
from rag_cognus.evaluation import configure_tracking, evaluate, load_cases

settings = Settings.from_env()
SNAPSHOT = PROJECT_ROOT / ".cache/gold.jsonl"
# Atualização explícita: nenhuma troca silenciosa de snapshot durante os experimentos.
ATUALIZAR_SNAPSHOT = False
if ATUALIZAR_SNAPSHOT or not SNAPSHOT.exists():
    documents = load_from_databricks(settings)
    print(save_snapshot(documents, SNAPSHOT, settings.gold_view))
documents = load_snapshot(SNAPSHOT)
configure_tracking(settings)
print("Gold:", len(documents), "trechos; modelo:", settings.chat_model)""",
        ),
        (
            "code",
            """# Troque para "dense" para comparar com embeddings locais.
config = replace(settings, backend="bm25", top_k=5)
retriever = GoldRetriever(documents, config)
rag = RagPipeline(retriever, config)
answer = rag.predict("Como organizar uma apresentação clara para meu público?")
print(answer["response"])
print(answer["citations"])""",
        ),
        (
            "code",
            """cases = load_cases(PROJECT_ROOT / "data/evaluation/questions.jsonl")
# Comece pequeno: cada pergunta usa uma chamada ao Qwen se houver contexto.
summary = evaluate(cases[:2], retriever, config, pipeline=rag,
                   output_dir=PROJECT_ROOT / "outputs", run_name="qwen-smoke")
print(summary)
if summary["metrics"]["error_rate"]:
    raise RuntimeError("Consulte o arquivo per_case.json do run.")""",
        ),
        (
            "markdown",
            """## Avaliação por juiz opcional

`evaluate_groundedness` usa o próprio Qwen como juiz e registra resultados com
`mlflow.genai.evaluate`. É uma autoavaliação exploratória, sujeita ao viés do mesmo
modelo; não equivale a revisão humana ou avaliação clínica. Abstenções recebem
`not_scored`, não aprovação automática de groundedness.

Para usar outro juiz, adapte a configuração do modelo de forma explícita.
Inicie o servidor com `rag-cognus mlflow-local` e abra `http://127.0.0.1:5000`.
Para executar a suite completa, use `python scripts/eval_local.py --judge`.
""",
        ),
        (
            "code",
            """# Ative somente quando quiser fazer chamadas adicionais ao modelo local.
EXECUTAR_JUIZ = False
if EXECUTAR_JUIZ:
    from rag_cognus.evaluation import evaluate_groundedness
    results = PROJECT_ROOT / "outputs" / f"{summary['run_id']}.json"
    print(evaluate_groundedness(results, settings))""",
        ),
    ],
)

write(
    "03_revisar_referencias.ipynb",
    [
        (
            "markdown",
            """# Revisão humana das referências de avaliação

As 14 perguntas iniciais são rascunhos. Os nichos esperados não são prova de que um
trecho responde à pergunta. Leia os candidatos e marque IDs relevantes somente após
conferir o apoio na fonte. Incluir também exemplos fora do escopo evita aprovar um
RAG que responde a tudo.

O exemplo a seguir roda localmente, após sincronizar a Gold. As referências devem
ser independentes do retriever que será avaliado; examine candidatos de BM25,
busca densa e fontes originais para reduzir viés e falsos negativos.
""",
        ),
        (
            "code",
            """from pathlib import Path
import sys, json
from dotenv import load_dotenv
PROJECT_ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents]
                    if (p / "src/rag_cognus").is_dir())
sys.path.insert(0, str(PROJECT_ROOT / "src"))
load_dotenv(PROJECT_ROOT / ".env")
from rag_cognus.config import Settings
from rag_cognus.gold import load_snapshot
from rag_cognus.retrieval import GoldRetriever
from rag_cognus.evaluation import load_cases

path = PROJECT_ROOT / "data/evaluation/questions.jsonl"
cases = load_cases(path)
documents = load_snapshot(PROJECT_ROOT / ".cache/gold.jsonl")
index = 0
case = cases[index]
print(case["inputs"]["query"])
for doc in GoldRetriever(documents, Settings()).search(case["inputs"]["query"], k=10):
    print("\\nID:", doc.metadata["chunk_id"], "Fonte:", doc.metadata.get("source_url"))
    print(doc.page_content)""",
        ),
        (
            "code",
            """# Preencha depois de ler os textos e conferir as fontes.
REVISADO_POR_HUMANO = False
RELEVANT_CHUNK_IDS = []
EXPECTED_FACTS = []
SHOULD_ABSTAIN = None

if REVISADO_POR_HUMANO:
    known = {d.metadata["chunk_id"] for d in documents}
    if not set(RELEVANT_CHUNK_IDS).issubset(known):
        raise ValueError("IDs ausentes do snapshot atual.")
    if not RELEVANT_CHUNK_IDS and SHOULD_ABSTAIN is not True:
        raise ValueError("Informe referências ou marque o caso como abstenção esperada.")
    case["expectations"].update(label_status="human_verified",
                                relevant_chunk_ids=RELEVANT_CHUNK_IDS,
                                expected_facts=EXPECTED_FACTS,
                                should_abstain=SHOULD_ABSTAIN)
    path.write_text("\\n".join(json.dumps(c, ensure_ascii=False) for c in cases) + "\\n")
    print("Referências salvas. Revise o diff do dataset antes de compartilhar.")
else:
    print("Dataset preservado; nenhuma referência foi marcada como revisada.")""",
        ),
    ],
)
write(
    "04_metodologia_avaliacao.ipynb",
    [
        ("markdown", (ROOT / "docs/avaliacao.md").read_text()),
        ("markdown", (ROOT / "docs/resultados_iniciais.md").read_text()),
    ],
)
write(
    "05_contexto_fontes_e_correlacao.ipynb",
    [
        ("markdown", (ROOT / "docs/contexto_metricas.md").read_text()),
        (
            "code",
            """from pathlib import Path
import json
import pandas as pd
root = next(p for p in [Path.cwd(), *Path.cwd().parents]
            if (p / 'src/rag_cognus').is_dir())
report = root / 'outputs/context_evaluation_summary.json'
if report.exists():
    result = json.loads(report.read_text())
    display(pd.DataFrame([result['metrics']]))
    display(pd.DataFrame(result['correlations']))
    print('Run local:', result['run_id'])
else:
    print('Execute context-eval para gerar os resultados locais.')""",
        ),
    ],
)
print("Cinco notebooks IPYNB gerados")
