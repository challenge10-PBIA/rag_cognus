#!/usr/bin/env bash
# MCP do Grafana (mcp-grafana OSS) em stdio, chamado por mcp_servers.grafana.command.
#
# Fonte das credenciais: o .env da raiz do repo (ignorado pelo git). Lê SÓ GRAFANA_URL e
# GRAFANA_SERVICE_ACCOUNT_TOKEN, linha a linha: nada de source nem de avaliar o arquivo, então
# nenhuma outra variável do .env chega ao contêiner e nada do arquivo é executado.
# Variáveis já exportadas no ambiente vencem o arquivo. Nunca imprime valores.
# GRAFANA_ENV_FILE troca o arquivo lido (usado nos testes).
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${GRAFANA_ENV_FILE:-$REPO/.env}"
# O Hermes pode subir o MCP com PATH curto; o Docker Desktop fica num destes.
PATH="$PATH:/usr/local/bin:/opt/homebrew/bin"

# Grava em $1 o valor da chave $1 no ENV_FILE (última ocorrência; aspas externas removidas).
load_key() {
  local key="$1" line value=""
  [ -r "$ENV_FILE" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line#export }"
    case "$line" in
      "$key="*) value="${line#*=}" ;;
      *) continue ;;
    esac
    case "$value" in
      \"*) value="${value#\"}" && value="${value%%\"*}" ;;
      \'*) value="${value#\'}" && value="${value%%\'*}" ;;
      *) value="${value%%[[:space:]]#*}" && value="${value%"${value##*[![:space:]]}"}" ;;
    esac
  done < "$ENV_FILE"
  printf -v "$key" '%s' "$value"
}

for key in GRAFANA_URL GRAFANA_SERVICE_ACCOUNT_TOKEN; do
  if [ -z "${!key:-}" ]; then
    load_key "$key"
  fi
  if [ -z "${!key:-}" ]; then
    echo "grafana.sh: falta $key (exporte no ambiente ou preencha no .env da raiz do repo)." >&2
    exit 1
  fi
  export "${key?}"
done

exec docker run --rm -i -e GRAFANA_URL -e GRAFANA_SERVICE_ACCOUNT_TOKEN mcp/grafana -t stdio
