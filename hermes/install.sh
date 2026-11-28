#!/usr/bin/env bash
# Instala o perfil Hermes "ragdev" apontando para este repositório.
# Uso: bash hermes/install.sh            (rode no computador onde o Hermes está instalado)
set -euo pipefail

PROFILE="${HERMES_PROFILE_NAME:-ragdev}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE_DIR="$HOME/.hermes/profiles/$PROFILE"

command -v hermes >/dev/null || {
  echo "hermes não encontrado. Instale: curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash"
  exit 1
}
command -v ollama >/dev/null || echo "aviso: ollama não encontrado no PATH"

if [ ! -d "$PROFILE_DIR" ]; then
  echo "→ criando perfil $PROFILE"
  hermes profile create "$PROFILE"
fi

if [ -f "$PROFILE_DIR/config.yaml" ]; then
  cp "$PROFILE_DIR/config.yaml" "$PROFILE_DIR/config.yaml.bak-$(date +%Y%m%d%H%M%S)"
  echo "→ backup da config anterior em $PROFILE_DIR/config.yaml.bak-*"
fi

sed "s#__REPO__#$REPO#g" "$REPO/hermes/config.yaml" > "$PROFILE_DIR/config.yaml"
chmod +x "$REPO"/hermes/hooks/*.py "$REPO"/hermes/harness/check.py \
  "$REPO"/hermes/harness/services.py
mkdir -p "$REPO/.hermes-runs"

echo "→ config instalada em $PROFILE_DIR/config.yaml"
echo
echo "Próximos passos:"
echo "  1. Ollama com 1 slot, contexto igual ao do perfil e KV cache enxuto (spec 015):"
echo "       launchctl setenv OLLAMA_NUM_PARALLEL 1"
echo "       launchctl setenv OLLAMA_CONTEXT_LENGTH 32768"
echo "       launchctl setenv OLLAMA_FLASH_ATTENTION 1"
echo "       launchctl setenv OLLAMA_KV_CACHE_TYPE q8_0"
echo "       launchctl setenv OLLAMA_KEEP_ALIVE 30m"
echo "     No app do Ollama (Settings) deixe Context length em 32k: o app sobrescreve o launchctl."
echo "     Reinicie: osascript -e 'quit app \"Ollama\"' && open -a Ollama"
echo "     (Linux: as mesmas Environment= no systemd do ollama e sudo systemctl restart ollama)"
echo "     No .env do app use OLLAMA_NUM_CTX=32768 (mesmo valor = sem recarregar o modelo)."
echo "  2. ollama pull eriktonon/deepseek-v4.1-flash-1017:latest"
echo "  3. $PROFILE doctor"
echo "  4. Painel:  .venv/bin/streamlit run hermes/monitor/app.py --server.port 8502"
echo "  5. Agente:  cd $REPO && $PROFILE      (aceite os hooks na 1ª vez)"
echo "     TDD estrito: HERMES_TDD_STRICT=1 $PROFILE"
echo "  6. Serviços:  python hermes/harness/services.py   (MLflow, Ollama, API e Grafana)"
echo
echo "Avaliação com juiz (rag-cognus evaluate): também 1 slot (OLLAMA_NUM_PARALLEL 1),"
echo "       o mesmo do dia a dia com o Hermes; não precisa alternar."
echo
echo "Opcional — Grafana Cloud (papel [obs]; passo a passo em docs/estudos/hermes-mcp-grafana.md):"
echo "  a. Na stack https://estevaomaia.grafana.net crie um service account (papel Viewer)"
echo "     e um token para ele."
echo "  b. No .env da raiz do repo ($REPO/.env, ignorado pelo git; nunca no .env.example),"
echo "     preencha (o wrapper hermes/mcp/grafana.sh lê só estas duas chaves):"
echo "       GRAFANA_URL=https://estevaomaia.grafana.net"
echo "       GRAFANA_SERVICE_ACCOUNT_TOKEN=<cole o token aqui>"
echo "  c. $PROFILE config set mcp_servers.grafana.enabled true"
echo "     (volta a false se rodar este install.sh de novo)"
echo "  d. $PROFILE mcp list   (Docker aberto; a 1ª conexão baixa a imagem mcp/grafana)"
