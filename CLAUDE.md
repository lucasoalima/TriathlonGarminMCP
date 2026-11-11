# Copiloto do Corpo — contexto do projeto (leia isto primeiro)

> Este arquivo é o "handoff" para o Claude Code continuar de onde paramos (a conversa original foi no Cowork e não transfere; o contexto vive aqui).

## O que é
App de **coaching de treino/recuperação por IA** para atletas de endurance/triatlo, **Brasil-first**. Unifica dados de wearables (Garmin no MVP), calcula carga e prontidão, e entrega **a decisão do dia** — o que treinar ou recuperar — de forma **segura** (nunca sobe a carga a ponto de arriscar lesão). Coexiste com a assessoria do atleta (importa o plano dela). Escopo **bem-estar** (não é conselho médico / fora de dispositivo médico ANVISA).

## Estado atual
- **Validado como protótipo** (UI + lógica) com dados reais de um Garmin. O protótipo visual foi feito em HTML/Cowork e **não** faz parte deste repo.
- **Este repo** contém o começo do código real: o **motor** (pacote `shared`, testado) e o **esqueleto do backend** (`api`).
- O `packages/shared/verify.mjs` roda em Node puro e confere a matemática do motor. O `tsc -p packages/shared` compila sem erros de tipo.

## Estrutura
- `packages/shared/src/` — **motor (TypeScript puro, framework-agnostic):**
  - `types.ts` — Athlete, Activity, DailyWellness, WeeklyPlan, Readiness, etc.
  - `load.ts` — carga por sessão (**TRIMP de Banister** / **TSS**), **CTL/ATL/TSB** (EWMA 42/7), **ACWR**, monotonia.
  - `readiness.ts` — **score 0–100** + estado (verde/amarelo/vermelho) + flags de risco.
  - `decision.ts` — planejado × executado × prontidão → **decisão do dia** + contextos "E se" (dormiu/30min/pulou/dor).
- `packages/api/src/` — esqueleto do backend: `engine.ts` (usa o `shared`), `server.ts`, `routes/` (today, plan, webhooks). Cheio de TODOs.
- `docs/` — specs de referência: **Algoritmo_Calculo_de_Carga.md** (fórmulas exatas), **Escopo_Tecnico_MVP_Android.md** (telas, modelo de dados, contratos de API, checklist Garmin), **Manual_de_Uso_e_Prontidao_Android.md** (jornada + o que falta).

## Como validar
```
node packages/shared/verify.mjs        # espera TRIMP ~82; CTL/ATL/TSB do exemplo
npm install                            # (já corrigido: era "workspace:*" -> "*")
npx tsc -p packages/shared             # deve passar
```

## Integração Garmin — ponto crítico
A API pública do Garmin dá **dado cru** (sono, HRV, estresse, FC, atividades via webhook/PING), mas **NÃO** dá as métricas calculadas (Training Status, TSB, Readiness). Por isso o **backend calcula** carga/prontidão a partir do cru (é o que o `shared` faz). Precisa do **Garmin Connect Developer Program** (OAuth 2.0 PKCE + webhooks) — ver `docs/Escopo_Tecnico_MVP_Android.md` §7.

## Guardrails de produto (não-negociáveis)
1. Segurança > performance: nunca prescrever carga que arrisque lesão; qualquer replanejamento respeita ACWR/rampa.
2. Dor → parar; PAR-Q+ positivo → modo conservador + recomendar profissional. Não é diagnóstico.
3. LGPD: dado de saúde é sensível — consentimento, criptografia, exportar/apagar.

## Próximas tarefas (em ordem)
1. **Parser de plano por IA** (server): texto/planilha → `WeeklyPlan` tipado + validação (Zod). Usar LLM no servidor (chave própria), com fallback e revisão do usuário.
2. **Rota `/today` rodável**: ligar o `engine.computeToday` a dados de exemplo → servidor de demonstração (Fastify) que retorna a decisão do dia.
3. **OAuth Garmin + handlers de webhook** (activity/wellness): responder 200 rápido, processar em fila, dedupe por `garmin_activity_id`, backfill de 42 dias.
4. **Persistência** (Postgres/Prisma): User, Consent, Profile, Plan, Activity, RawWellness, LoadState, Readiness.
5. **App mobile (Capacitor)** reaproveitando a UI do protótipo; push via FCM.

## Convenções
- TypeScript estrito, ESM. Motor puro e testável (sem I/O). Datas em `YYYY-MM-DD`. Validação de entrada com Zod nas rotas.

## Atualização — fonte de dados do MVP: Health Connect (sem CNPJ)
- MVP Android lê o Garmin **via Health Connect** (grátis, sem CNPJ, publicável). Traz: atividades, FC, sono (estágios), SpO2. **NÃO** traz HRV/estresse/Body Battery/training-status.
- O motor já suporta **prontidão sem HRV** (pesos recalibrados: sono .40 / TSB .35 / ACWR .15 / mono .10) — ver `readiness.ts`.
- Abstração `DataSource` (ver `datasource.ts`): implementar `HealthConnectDataSource` no app (Capacitor). Agregador (Terra/Rook) e Garmin-direto entram depois para adicionar HRV.
- Detalhes: `docs/Integracao_Garmin_sem_CNPJ.md`.
