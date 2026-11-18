# 010 — Onboarding guiado pelo mascote

- **Status:** aprovada
- **Módulos (backend):** `src/rag_cognus/api/app.py`, `src/rag_cognus/api/schemas.py`,
  `src/rag_cognus/api/store.py`
- **Módulos (front, `frontend_UI`):** novo `src/components/onboarding/`,
  `src/components/app-shell.tsx`, `src/components/nav.tsx` (âncoras do tour),
  `src/components/profile/profile-view.tsx` (exporta o editor do mascote; botão "Rever
  tutorial"), `src/app/globals.css`, `src/lib/api/*`
- **Testes:** `tests/test_api.py`; front: typecheck/lint/build
- **Depende de:** specs 008 e 009

## Problema
No primeiro acesso o app abre direto no Início com nome "Você", meta de 10 min e mascote
padrão. Ninguém explica o que é cada tela, nem testa o microfone antes da primeira gravação,
que é onde o usuário mais trava.

## Comportamento esperado
No primeiro acesso, o mascote conduz um passo a passo animado, que dá para pular e retomar:

1. **Boas-vindas** — o mascote se apresenta.
2. **Privacidade** — o usuário escolhe se permite ou não o registro de dados de uso do app.
3. **Seu nome e meta diária** (minutos).
4. **Seu mascote** — mesmo editor do Perfil, com prévia ao vivo.
5. **Teste do microfone** — grava ~5 s localmente e mostra o nível; nada é enviado. Pode
   pular.
6. **Tour** — destaca Gravar, Início, Métricas, Pergunte ao Cognus e Perfil, um por vez,
   com o mascote explicando cada um em uma frase.
7. **Pronto** — "Fazer minha primeira prática" (vai para `/gravar`) ou "Explorar".

O progresso é salvo no backend; o tutorial pode ser revisto pelo Perfil. Quando o tutorial
mudar de forma relevante, a versão sobe e ele reaparece uma vez.

## Contrato
- `GET /v1/onboarding` → `{version, completed_version|null, completed_at|null, step|null,
  needed: bool}`; `needed = completed_version != version`.
- `PUT /v1/onboarding` `{step?: Step, status?: "completed"|"skipped"|"reset"}` →
  mesmo corpo do GET.
- `Step ∈ {welcome, privacy, profile, mascot, microphone, tour, done}`.
- `GET /v1/privacy` → `{tracking_allowed: bool|null, decided_at: str|null,
  policy_version: int, decided_version: int|null}`; `null` = ainda não decidiu.
- `PUT /v1/privacy` `{tracking_allowed: bool}` → mesmo corpo do GET.

## Critérios de aceite — backend (engenheiro-ia)
- **AC-1:** Banco novo → `needed=true`, `step=null`, `completed_version=null`.
- **AC-2:** `PUT {step}` grava o passo atual (retomar de onde parou); passo fora de `Step`
  → 422.
- **AC-3:** `PUT {status: "completed"}` e `{status: "skipped"}` gravam
  `completed_version = ONBOARDING_VERSION` e `completed_at` (ISO); `needed=false`. Pular
  conta como concluído (não insistir).
- **AC-4:** `PUT {status: "reset"}` ("Rever tutorial") limpa `completed_version` e `step` →
  `needed=true`.
- **AC-5:** `completed_version` menor que `ONBOARDING_VERSION` → `needed=true` (testado
  trocando a constante via monkeypatch).
- **AC-6:** Estado persiste em `app_state` (spec 009 AC-10), sem tocar na tabela `profile`;
  abrir o mesmo banco duas vezes não falha.
- **AC-7:** Funciona sem Ollama, Gold ou MLflow.
- **AC-7a (consentimento):** Banco novo → `tracking_allowed=null`. `PUT /v1/privacy` grava a
  escolha, `decided_at` (ISO) e `decided_version = PRIVACY_POLICY_VERSION`; corpo sem
  `tracking_allowed` ou com chave extra → 422. Persiste em `app_state`. **Hoje a escolha não
  liga nem desliga nenhum registro**: é guardada para recursos futuros, que devem tratar
  `null` e `false` como "não permitido" e pedir de novo quando `decided_version` for menor
  que `PRIVACY_POLICY_VERSION`.
- **AC-7b:** `ONBOARDING_VERSION` sobe para 2: quem concluiu a versão 1 vê o tutorial de novo
  e responde ao consentimento.

## Critérios de aceite — front
- **AC-8:** `<Onboarding>` montado no `AppShell`; abre quando `needed` e não está em
  `/gravar*`. É um `role="dialog" aria-modal="true"` com título por passo, foco preso, e
  indicador "Passo N de 7" (`aria-current` no passo atual).
- **AC-9:** Cada passo tem "Voltar" (exceto o 1º), "Continuar" e "Pular tutorial"; pular
  envia `status: "skipped"`. Avançar envia `PUT {step}`; recarregar a página retoma no
  passo salvo.
- **AC-10:** Passo "Seu nome e meta": valida nome 1–60 e meta 1–240; salva com
  `PUT /v1/profile` (mantendo o mascote) antes de avançar; erro da API em `ErrorBox`.
- **AC-11:** Passo "Seu mascote" reaproveita o editor do Perfil (componente exportado, sem
  duplicar paleta); salvar é opcional (padrão já é válido).
- **AC-12:** Passo "Microfone" usa `useRecorder`: botão "Testar 5 s", barra de nível ao vivo,
  resultado "Ouvi você bem" / "Muito baixo — aproxime-se do microfone" pela energia média;
  permissão negada mostra como liberar e permite seguir. O áudio não é enviado à API.
- **AC-13:** Tour: o diálogo vira um balão do mascote ancorado no item `[data-tour=<id>]`
  visível (barra lateral no desktop, barra inferior no mobile), com recorte destacando o
  item; sem âncora visível o balão fica centralizado. "Próximo" percorre
  `gravar → inicio → metricas → cognus → perfil`.
- **AC-14:** Passo final: "Fazer minha primeira prática" envia `completed` e navega para
  `/gravar`; "Explorar" envia `completed` e fecha.
- **AC-15:** Animação: troca de passo desliza/dissolve em ≤ 300 ms e o mascote muda de
  expressão (`feliz` nas boas-vindas e no fim, `neutro` nos formulários, `pensativo` no
  microfone até o resultado). `prefers-reduced-motion` → troca instantânea.
- **AC-16:** Perfil ganha "Rever tutorial" (`PUT {status: "reset"}`), que reabre o
  onboarding.
- **AC-17:** Responsivo a 360 px sem rolagem horizontal; controles ≥ 44 × 44 px com foco
  visível.

- **AC-18 (consentimento):** Passo "Privacidade": duas opções explícitas ("Permitir" /
  "Não permitir") num `role="radiogroup"`, nenhuma pré-marcada na primeira vez; "Continuar"
  só habilita após a escolha, que é salva com `PUT /v1/privacy` antes de avançar. O texto diz
  que dá para mudar no Perfil e não promete o que o app ainda não faz. "Pular tutorial" não
  registra escolha (fica `null` = não permitido).
- **AC-19:** Perfil mostra "Dados de uso" (`role="switch"`) com a escolha atual
  (`null` aparece desligado com o texto "Você ainda não escolheu") e permite mudar.

## Fora de escopo
- Login/múltiplos usuários; tour por tela interna (só navegação principal); vídeo.

## Plano
| Passo | Arquivo | Subagente | Verificação |
|---|---|---|---|
| 1 | `tests/test_api.py` → `store.py`, `schemas.py`, `app.py` | engenheiro-ia | AC-1…AC-7 |
| 2 | `onboarding/*`, `app-shell.tsx`, `nav.tsx`, `profile-view.tsx`, `globals.css` | front | AC-8…AC-17 |
| 3 | ambos | líder | `check.py` + `npm run typecheck && lint && build` |
