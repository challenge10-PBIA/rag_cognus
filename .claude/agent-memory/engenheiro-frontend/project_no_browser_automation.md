---
name: no-browser-automation
description: Na máquina do frontend_UI não há Chrome/Chromium/Playwright e o safaridriver não sobe; ensaio de navegador fica como checklist manual
metadata:
  type: project
---

Em 2026-11-23 (spec 028) não havia Chrome, Chromium, Playwright nem Puppeteer instalados, e
`safaridriver -p 4444` saiu sem abrir porta (provavelmente falta "Permitir automação remota",
que pede sudo). O dev (`next dev` na 3000) e a API (8001) costumam estar no ar.

**Why:** gastei tempo tentando automatizar o ensaio; sem `npm install` autorizado não dá para
trazer um navegador.

**How to apply:** prove o que der com curl (arquivos de `public/`, status das rotas, headers da
API) e entregue um checklist manual de navegador no relatório; não tente de novo sem o líder
autorizar instalar algo. Veja também [[dev-css-stale-tailwind-turbopack]].
