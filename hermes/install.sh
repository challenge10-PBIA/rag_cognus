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
chmod +x "$REPO"/hermes/hooks/*.py "$REPO"/hermes/harness/check.py
mkdir -p "$REPO/.hermes-runs"

echo "→ config instalada em $PROFILE_DIR/config.yaml"
echo
echo "Próximos passos:"
echo "  1. Ollama com slots paralelos (pai + 2 subagentes) e contexto fixo:"
echo "       launchctl setenv OLLAMA_NUM_PARALLEL 3 && launchctl setenv OLLAMA_CONTEXT_LENGTH 32768"
echo "       (Linux: Environment=OLLAMA_NUM_PARALLEL=3 no systemd do ollama) e reinicie o Ollama"
echo "  2. ollama pull qwen3.5:9b"
echo "  3. $PROFILE doctor"
echo "  4. Painel:  .venv/bin/streamlit run hermes/monitor/app.py --server.port 8502"
echo "  5. Agente:  cd $REPO && $PROFILE      (aceite os hooks na 1ª vez)"
echo "     TDD estrito: HERMES_TDD_STRICT=1 $PROFILE"
