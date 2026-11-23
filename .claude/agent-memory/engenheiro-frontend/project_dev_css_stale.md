---
name: dev-css-stale-tailwind-turbopack
description: No frontend_UI, `next dev` serve globals.css com uma edição de atraso (loader @tailwindcss/turbopack 4.3.3); reiniciar o dev limpando .next após mexer em tokens
metadata:
  type: project
---

Em `frontend_UI` (Next 16.4.6 + regra `turbopack.rules["*.css"]` com `@tailwindcss/turbopack` 4.3.3),
editar `src/app/globals.css` com o `next dev` ligado deixa o CSS servido UMA edição atrás
(reproduzido em 2026-11-23 com propriedades-sonda: cada edição só aparece após a seguinte).
Suspeita: o loader decide recompilar por mtime e reaproveita o compilador antigo.

**Why:** usuário viu "tema escuro não funciona" e "mascote sem olhos" porque os tokens novos
(`--mascot-ink`, dark) nunca chegaram ao navegador. Next 16 já separa `.next/dev` do build, então
`npm run build` concorrente NÃO era a causa.

**How to apply:** depois de mexer em `globals.css`, pare o dev, `rm -rf .next`, suba de novo e prove
com curl+grep no chunk `[root-of-the-server]__*.css`. Use `var(--token, fallback)` em SVG
(fill/stroke com var inválido somem ou viram preto). Correção definitiva: migrar para
`@tailwindcss/postcss` (pede `npm install`, autorização do líder).
