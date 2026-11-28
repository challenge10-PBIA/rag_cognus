from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from dotenv import load_dotenv

from rag_cognus.agents.schemas import AUDIENCES, CONTEXTS
from rag_cognus.config import Settings


def port_in_use(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def run_agents(args, settings: Settings, retriever, text: str | None = None):
    """Comandos synthesize/adapt: imprime o resultado (e as notas, com --judge) em JSON."""
    from rag_cognus.agents import agents_judges as aj
    from rag_cognus.agents.communication import CommunicationAgent
    from rag_cognus.agents.evidence import EvidenceAgent
    from rag_cognus.agents.pipeline import EvidenceToAudience
    from rag_cognus.agents.schemas import AudienceProfile

    if args.command == "synthesize":
        result = EvidenceAgent(retriever, settings).run(args.topic, args.niche)
        if args.judge:
            judge = aj.make_evidence_judge(settings)
            result["scores"] = aj.as_scores(aj.judge_evidence(judge, result))
    else:
        profile = AudienceProfile(
            audience=args.audience, context=args.context, minutes=args.minutes, tone=args.tone
        )
        communication = CommunicationAgent(settings)
        if args.topic:
            pipeline = EvidenceToAudience(EvidenceAgent(retriever, settings), communication)
            result = pipeline.run(args.topic, profile, args.niche)
            adapted = result["communication"]
        else:
            result = adapted = communication.run(text, profile)
        if args.judge:
            judge = aj.make_communication_judge(settings)
            result["scores"] = aj.as_scores(aj.judge_communication(judge, adapted))
    print(json.dumps(result, ensure_ascii=False, indent=2))


MLFLOW_HINT = "rode `rag-cognus mlflow-local` e confira MLFLOW_TRACKING_URI no .env."


def _http_get(url: str, timeout: float):
    import httpx

    return httpx.get(url, timeout=timeout)


def _mlflow_client(uri: str):
    from mlflow import MlflowClient

    return MlflowClient(tracking_uri=uri)


def mlflow_check(settings: Settings, http_get=_http_get, client_factory=_mlflow_client) -> int:
    """Confere o MLflow local: servidor no ar e experimentos de lote/online. 0 = ok."""
    uri = settings.tracking_uri
    print(f"MLflow: {uri}")
    if uri.startswith(("http://", "https://")):
        try:
            status = http_get(uri.rstrip("/") + "/health", timeout=2).status_code
        except Exception as exc:  # conexão recusada, timeout...
            print(f"Servidor: não responde ({type(exc).__name__}); {MLFLOW_HINT}")
            return 1
        if not 200 <= status < 300:
            print(f"Servidor: respondeu HTTP {status}; {MLFLOW_HINT}")
            return 1
        print("Servidor: ok")
    else:
        print("Servidor: não se aplica (tracking em arquivo local)")
    try:
        client = client_factory(uri)
        batch = client.get_experiment_by_name(settings.experiment)
        print(f"Experimento de lote {settings.experiment}: {'ok' if batch else 'ausente'}")
        if client.get_experiment_by_name(settings.online_experiment):
            print(f"Experimento online {settings.online_experiment}: ok")
        else:
            client.create_experiment(settings.online_experiment)
            print(f"Experimento online {settings.online_experiment}: criado")
    except Exception as exc:
        print(f"Erro ao consultar experimentos ({type(exc).__name__}: {exc}); {MLFLOW_HINT}")
        return 1
    return 0


MLFLOW_HEALTH_TTL = 30.0
MLFLOW_HEALTH_CACHE: dict[str, tuple[float, bool]] = {}


def mlflow_available(
    uri: str, *, now: float | None = None, http_get=_http_get, ttl: float = MLFLOW_HEALTH_TTL
) -> bool:
    """MLflow responde em `{uri}/health` (2xx, timeout 2 s)? Resultado em cache por `ttl` s.

    URIs sem servidor (sqlite:, file:, caminho) contam como disponíveis.
    """
    if not uri.startswith(("http://", "https://")):
        return True
    import time

    now = time.monotonic() if now is None else now
    cached = MLFLOW_HEALTH_CACHE.get(uri)
    if cached and now - cached[0] < ttl:
        return cached[1]
    try:
        ok = 200 <= http_get(uri.rstrip("/") + "/health", timeout=2).status_code < 300
    except Exception:  # conexão recusada, timeout...
        ok = False
    MLFLOW_HEALTH_CACHE[uri] = (now, ok)
    return ok


def mlflow_local_env(environ=None) -> tuple[dict[str, str], str]:
    """Ambiente do `mlflow server` com o Ollama como LLM dos juízes (spec 012).

    Só preenche o que falta em `environ` (quem já configurou manda). Devolve o ambiente e uma
    linha para o terminal com o juiz e a base efetivos, nunca o valor de uma chave.
    """
    from rag_cognus.evaluation import ui_judge_env

    environ = dict(os.environ if environ is None else environ)
    notice = ""
    try:
        settings = Settings.from_env()
    except ValueError as exc:  # .env inválido não impede o MLflow de subir
        settings = Settings()
        notice = f"Aviso: .env inválido ({exc}); juízes com os padrões do Settings.\n"
    extra = ui_judge_env(settings)
    if environ.get("OPENAI_BASE_URL"):  # mesma base com o nome novo do SDK da OpenAI
        extra.pop("OPENAI_API_BASE")
    env = {**extra, **{k: v for k, v in environ.items() if v or k not in extra}}
    base = env.get("OPENAI_API_BASE") or env.get("OPENAI_BASE_URL", "")
    judge = env["MLFLOW_GENAI_JUDGE_DEFAULT_MODEL"]
    return env, f"{notice}Juízes da UI: {judge} (base {base})"


def serve_api(host: str, port: int):
    import uvicorn

    from rag_cognus.api.app import Services, create_app
    from rag_cognus.evaluation import configure_tracking

    # Se o MLflow cair com a API no ar, um pedido não deve ficar minutos em retry/backoff.
    os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "2")
    os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", "10")
    settings = Settings.from_env()
    warning = (
        "Aviso: MLflow indisponível ({}); a avaliação online tenta de novo a cada "
        f"pedido (checagem em cache por {MLFLOW_HEALTH_TTL:.0f} s). {MLFLOW_HINT}"
    )
    if not mlflow_available(settings.tracking_uri):
        # set_experiment faria retries HTTP por minutos; a API sobe sem esperar (AC-D5).
        import mlflow

        from rag_cognus.config import ensure_local_tracking

        mlflow.set_tracking_uri(ensure_local_tracking(settings.tracking_uri))
        print(warning.format(f"{settings.tracking_uri} não responde"))
    else:
        try:
            configure_tracking(settings)
        except Exception as exc:  # sem MLflow a API funciona; o tracing não é desligado
            print(warning.format(exc))
    print(f"Cognus API em http://{host}:{port}  (documentação: /docs)")
    uvicorn.run(create_app(Services(settings)), host=host, port=port)


VOICE_EXTRA_HINT = "Instale o extra de voz: pip install -e '.[voice]'"


def _piper_installed() -> bool:
    import importlib.util

    return importlib.util.find_spec("piper") is not None


def voice_download(
    settings: Settings,
    voices: list[str] | None = None,
    force: bool = False,
    list_only: bool = False,
    run=subprocess.run,
    installed=_piper_installed,
) -> int:
    """Baixa vozes do Piper para `PIPER_DATA_DIR` com o módulo do próprio pacote (spec 027)."""
    from rag_cognus import voice

    if not installed():
        print(VOICE_EXTRA_HINT)
        return 1
    module = [sys.executable, "-m", "piper.download_voices"]
    if list_only:
        result = run(module, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Não foi possível listar as vozes: {result.stderr.strip()}")
            return 1
        for line in result.stdout.splitlines():
            if line.strip().startswith("pt_BR-"):
                print(line.strip())
        return 0
    data_dir = Path(settings.piper_data_dir)
    code = 0
    for name in voices or [settings.piper_voice]:
        model = data_dir / f"{name}.onnx"
        if not force and model.is_file() and Path(f"{model}.json").is_file():
            print(f"{name}: já existe em {data_dir} (use --force para baixar de novo)")
            continue
        print(f"{name}: baixando para {data_dir}…")
        command = [*module, name, "--data-dir", str(data_dir)]
        if force:
            command.append("--force-redownload")
        result = run(command)
        if result.returncode != 0:
            print(f"{name}: falha no download (código {result.returncode})")
            code = 1
    print(json.dumps(voice.voice_status(settings), ensure_ascii=False))
    return code


REPO_ROOT = Path(__file__).resolve().parents[2]
PRESENTATION_DIR = REPO_ROOT.parent / "frontend_UI" / "public" / "presentation"
AUDIO_EXT = {"audio/mpeg": ".mp3", "audio/wav": ".wav"}


def _pregen_key(settings: Settings, text: str) -> str:
    """sha256 de provedor + voz + texto normalizado: muda quando o áudio precisa mudar."""
    from rag_cognus import voice

    provider = voice.provider_for(settings, "presentation")
    voice_id = settings.piper_voice if provider == "piper" else settings.elevenlabs_voice_id
    raw = f"{provider}|{voice_id}|{voice.normalize_text(text)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def voice_pregen(
    settings: Settings,
    roteiro: Path,
    out: Path,
    force: bool = False,
    only: list[str] | None = None,
    yes: bool = False,
    synth=None,
    ask=input,
) -> int:
    """Pré-gera o áudio do modo apresentação a partir do roteiro (spec 028 AC-2)."""
    from rag_cognus import voice

    synth = synth or voice.synthesize
    if not Path(roteiro).is_file():
        print(f"Roteiro não encontrado: {roteiro} (use --roteiro CAMINHO).")
        return 2
    steps = json.loads(Path(roteiro).read_text("utf-8"))["steps"]
    ids = [step["id"] for step in steps]
    unknown = [sid for sid in only or [] if sid not in ids]
    if unknown:
        print(f"Passos inexistentes no roteiro: {', '.join(unknown)}")
        return 2
    out = Path(out)
    manifest_path = out / "manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8")) if manifest_path.is_file() else {}
    todo = []
    for step in steps:
        if only and step["id"] not in only:
            continue
        key = _pregen_key(settings, step["text"])
        entry = manifest.get(step["id"], {})
        fresh = entry.get("sha256") == key and (out / entry.get("file", "")).is_file()
        if force or not fresh:
            todo.append((step, key))
    if not todo:
        print("Nada a gerar: todos os passos estão atualizados (use --force para refazer).")
        return 0
    chars = sum(len(voice.normalize_text(step["text"])) for step, _ in todo)
    provider = voice.provider_for(settings, "presentation")
    print(f"{len(todo)} passo(s) a gerar, {chars} caracteres, provedor {provider}.")
    print("Passos: " + ", ".join(step["id"] for step, _ in todo))
    if not yes and ask("Gerar? [s/N] ").strip().lower() not in {"s", "sim"}:
        print("Nada gerado.")
        return 1
    missing = []
    for step, key in todo:
        try:
            result = synth(settings, step["text"], purpose="presentation")
        except (voice.VoiceUnavailable, voice.InvalidText) as exc:
            print(f"{step['id']}: {exc}")
            missing.append(step["id"])
            continue
        name = step["id"] + AUDIO_EXT.get(result.media_type, ".mp3")
        voice._write_atomic(out / name, result.audio)
        manifest[step["id"]] = {"file": name, "sha256": key, "provider": result.provider}
        data = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        voice._write_atomic(manifest_path, data.encode("utf-8"))
        print(f"{step['id']}: {name} ({result.provider})")
    if missing:
        print(f"Faltaram: {', '.join(missing)}. Os demais foram mantidos; rode de novo.")
        return 1
    return 0


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Cognus: Gold → LangChain/Ollama → MLflow local")
    parser.add_argument("--snapshot", default=".cache/gold.jsonl")
    sub = parser.add_subparsers(dest="command", required=True)
    server = sub.add_parser("mlflow-local", help="Abrir o MLflow open source local")
    server.add_argument("--port", type=int, default=5001)
    server.add_argument("--data-dir", default=".cache/mlflow")
    sub.add_parser("mlflow-check", help="Conferir o MLflow local e os experimentos")
    api = sub.add_parser("api", help="Subir a API do front web (FastAPI, OpenAPI em /docs)")
    api.add_argument("--host", default="127.0.0.1")
    api.add_argument("--port", type=int, default=8001)
    exporter = sub.add_parser(
        "mlflow-exporter", help="Expor métricas do MLflow local em /metrics (Prometheus)"
    )
    exporter.add_argument("--host", default="127.0.0.1", help="0.0.0.0 expõe na rede local (evite)")
    exporter.add_argument("--port", type=int, default=9105)
    vd = sub.add_parser("voice-download", help="Baixar a voz local do mascote (Piper)")
    vd.add_argument(
        "--voice", action="append", help="Voz, ex. pt_BR-cadu-medium (repetível; padrão do .env)"
    )
    vd.add_argument("--force", action="store_true", help="Baixar de novo mesmo se já existir")
    vd.add_argument("--list", action="store_true", help="Listar as vozes pt_BR disponíveis")
    pg = sub.add_parser("voice-pregen", help="Pré-gerar o áudio do modo apresentação")
    pg.add_argument(
        "--roteiro",
        type=Path,
        default=PRESENTATION_DIR / "roteiro.json",
        help="roteiro.json (padrão: ../frontend_UI/public/presentation/roteiro.json)",
    )
    pg.add_argument(
        "--out",
        type=Path,
        default=PRESENTATION_DIR / "audio",
        help="Pasta dos áudios e do manifest.json (padrão: .../presentation/audio)",
    )
    pg.add_argument("--force", action="store_true", help="Refazer mesmo os passos inalterados")
    pg.add_argument("--only", action="append", help="Gerar só este passo (id; repetível)")
    pg.add_argument("--yes", action="store_true", help="Não pedir confirmação")
    sub.add_parser("sync-gold", help="Ler a Gold com OAuth e SQL Warehouse")
    ask = sub.add_parser("ask")
    ask.add_argument("query")
    ask.add_argument("--niche")
    ask.add_argument("--backend", choices=["bm25", "dense"], default=None)
    ask.add_argument("--judge", action="store_true", help="Mostrar as notas do juiz")
    syn = sub.add_parser("synthesize", help="Agente de evidências: síntese de um tema")
    syn.add_argument("topic")
    syn.add_argument("--niche")
    syn.add_argument("--judge", action="store_true", help="Notas do juiz para a síntese")
    ad = sub.add_parser("adapt", help="Agente de comunicação: adaptar ao público")
    source = ad.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="Texto a adaptar")
    source.add_argument("--file", help="Arquivo .txt com o texto")
    source.add_argument("--topic", help="Tema: evidências da Gold → texto adaptado")
    ad.add_argument("--audience", choices=list(AUDIENCES), default="leigo")
    ad.add_argument("--context", choices=list(CONTEXTS), default="palestra")
    ad.add_argument("--minutes", type=float, default=3)
    ad.add_argument("--tone", choices=["neutro", "formal", "informal"], default="neutro")
    ad.add_argument("--niche", help="Nicho para a busca (com --topic)")
    ad.add_argument("--judge", action="store_true", help="Notas do juiz para a adaptação")
    ev = sub.add_parser("evaluate", help="Avaliar e registrar no MLflow local")
    ev.add_argument("--dataset", default="data/evaluation/questions.jsonl")
    ev.add_argument("--backend", choices=["bm25", "dense"], default=None)
    ev.add_argument("--k", type=int, default=None)
    ev.add_argument("--generate", action="store_true", help="Gerar respostas com o LLM local")
    ev.add_argument("--judge", action="store_true", help="Notas de qualidade (requer --generate)")
    ev.add_argument("--limit", type=int)
    args = parser.parse_args()

    if args.command == "mlflow-local":
        if not 1 <= args.port <= 65535:
            parser.error("Porta inválida")
        if port_in_use(args.port):
            parser.error(
                f"A porta {args.port} já está em uso (no macOS a 5000 é do AirPlay). "
                "Use --port com outra porta e ajuste MLFLOW_TRACKING_URI."
            )
        folder = Path(args.data_dir).resolve()
        folder.mkdir(parents=True, exist_ok=True)
        env, judge_line = mlflow_local_env()
        print(f"MLflow open source em http://127.0.0.1:{args.port}")
        print(judge_line)
        command = [
            sys.executable,
            "-m",
            "mlflow",
            "server",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.port),
            "--backend-store-uri",
            "sqlite:///" + str(folder / "mlflow.db"),
            "--serve-artifacts",
            "--artifacts-destination",
            str(folder / "artifacts"),
        ]
        raise SystemExit(subprocess.call(command, env=env))

    if args.command == "api":
        serve_api(args.host, args.port)
        return

    if args.command == "mlflow-exporter":
        from rag_cognus import mlflow_exporter

        mlflow_exporter.serve(Settings.from_env(), args.host, args.port)
        return

    if args.command == "voice-download":
        raise SystemExit(
            voice_download(
                Settings.from_env(), voices=args.voice, force=args.force, list_only=args.list
            )
        )

    if args.command == "voice-pregen":
        raise SystemExit(
            voice_pregen(
                Settings.from_env(),
                args.roteiro,
                args.out,
                force=args.force,
                only=args.only,
                yes=args.yes,
            )
        )

    if args.command == "mlflow-check":
        try:
            check_settings = Settings.from_env()
        except ValueError as exc:  # inclui URI fora do MLflow local
            print(f"{exc}\nCorrija o .env e {MLFLOW_HINT}")
            raise SystemExit(1) from None
        raise SystemExit(mlflow_check(check_settings))

    settings = Settings.from_env()
    if getattr(args, "backend", None):
        settings = replace(settings, backend=args.backend)
    if getattr(args, "k", None) is not None:
        settings = replace(settings, top_k=args.k)
    from rag_cognus.gold import load_from_databricks, load_snapshot, save_snapshot

    if args.command == "sync-gold":
        docs = load_from_databricks(settings)
        print(json.dumps(save_snapshot(docs, args.snapshot, settings.gold_view), indent=2))
        return

    from rag_cognus.evaluation import configure_tracking, evaluate, load_cases
    from rag_cognus.judges import make_judge
    from rag_cognus.retrieval import GoldRetriever

    configure_tracking(settings)
    if args.command == "adapt" and not args.topic:
        text = args.text if args.text is not None else Path(args.file).read_text()
        run_agents(args, settings, None, text)
        return
    retriever = GoldRetriever(load_snapshot(args.snapshot), settings)
    if args.command in {"synthesize", "adapt"}:
        run_agents(args, settings, retriever)
        return
    if args.command == "ask":
        from rag_cognus.chain import RagPipeline
        from rag_cognus.judges import as_dict, judge_response

        result = RagPipeline(retriever, settings).predict(args.query, args.niche)
        if args.judge:
            result["scores"] = as_dict(judge_response(make_judge(settings), args.query, result))
        result.pop("retrieved_context", None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.judge and not args.generate:
        parser.error("--judge avalia respostas; use junto com --generate")
    cases = load_cases(args.dataset)
    if args.limit is not None:
        if args.limit < 1:
            parser.error("--limit deve ser positivo")
        cases = cases[: args.limit]
    pipeline = None
    if args.generate:
        from rag_cognus.chain import RagPipeline

        pipeline = RagPipeline(retriever, settings)
    judge = make_judge(settings) if args.judge else None
    summary = evaluate(cases, retriever, settings, pipeline, judge)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nVeja no MLflow: {settings.tracking_uri}")
    if summary["metrics"].get("error/mean"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
