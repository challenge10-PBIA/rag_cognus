---
name: docker-grafana-alloy
description: Extensão Grafana do Docker Desktop não aceita config própria; host.docker.internal alcança 127.0.0.1 do Mac (testado)
metadata:
  type: reference
---

- Extensão Grafana do Docker Desktop (2.0.0): container `grafana-docker-desktop-extension-alloy`,
  `grafana/alloy:v1.0.0`, config em volume nomeado `..._alloy-volume` gerado pelo backend da
  extensão. Compose dela em `~/Library/Containers/com.docker.docker/Data/extensions/grafana_docker-desktop-extension/vm/docker-compose.yaml`.
  Inspecionar só `.Mounts`/`.Config.Cmd` (Env tem token). Por isso o projeto usa Alloy próprio
  em `infra/alloy/` (spec 017), UI em 127.0.0.1:12346.
- Docker Desktop do Mac: container conecta em `host.docker.internal:PORT` mesmo com o serviço
  escutando só em 127.0.0.1 (testado 2026-11-18 com bash /dev/tcp na imagem do alloy, --rm).
- `alloy fmt` offline: `docker run --rm --network none -v <cfg>:/tmp/c.alloy:ro --entrypoint /bin/alloy grafana/alloy:v1.0.0 fmt /tmp/c.alloy`.

Relacionado: [[guard-quirks]].
