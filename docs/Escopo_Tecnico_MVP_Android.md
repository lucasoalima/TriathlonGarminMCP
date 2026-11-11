# Escopo Técnico — MVP Android (Copiloto do Corpo)

Documento de build acionável, derivado do protótipo validado. Objetivo: sair do protótipo (HTML/Cowork) para um **app Android em beta fechado** com backend, integração Garmin real e IA no servidor.

> **Ajuste crítico de realidade (das APIs reais do Garmin):** a Health API entrega dado **cru** (sono, HRV, estresse, body battery, FC repouso) e a Activity API entrega **atividades via PING/webhook**. As métricas *calculadas* que usamos no protótipo (training status, TSB, ACWR, readiness) são **proprietárias do Garmin Connect e não vêm na API pública**. Portanto, **o backend calcula a carga e a prontidão** a partir do dado cru + atividades. Isso está refletido no motor de decisão abaixo.

---

## 1. Escopo do MVP (corte enxuto)

**ENTRA (v1 beta):**
- Login + consentimento LGPD.
- Conectar **Garmin** (OAuth) — 1 fonte já basta. Health Connect fica para a v1.1.
- Onboarding essencial (Blocos 1–3: objetivo, estrutura, PAR-Q+, lesões) → Perfil.
- Importar plano por **IA (colar texto/planilha)** OU plano de base gerado.
- **Decisão do dia** (prontidão + treinos feitos + sugestão modulada + botões "E se…").
- **Coach** (perguntas por IA, com contexto).
- **Insights** (zonas automáticas + radar de risco).
- **Nutrição** (carbo por carga + estratégia de prova).
- **Notificação matinal** (push) + **reavaliação pós-treino** (webhook Garmin).

**NÃO ENTRA (depois):** Apple Health, escrever treino de volta no relógio (Training API), marketplace de coaches, versão web, B2B/cockpit, pagamentos, upload de PDF/imagem (v1 é colar texto), multi-idioma.

**Métrica-norte do beta:** retenção D30/D90 + "não treino sem isso".

---

## 2. Telas congeladas (v1)

| # | Tela | Função | Componentes-chave | Estados |
|---|------|--------|-------------------|---------|
| 1 | **Splash/Login** | entrar | logo, botões e-mail/Google/Apple | logado / deslogado |
| 2 | **Consentimento** | LGPD | texto + checkbox + aceitar | bloqueia se não aceitar |
| 3 | **Conectar wearable** | OAuth Garmin | botão "Conectar Garmin", status | conectado / erro / pendente |
| 4 | **Onboarding** | anamnese essencial (stepper) | perguntas + PAR-Q+ + barra de progresso | incompleto / concluído |
| 5 | **Importar/Gerar plano** | plano | textarea + "interpretar (IA)" / "gerar base" + revisão | vazio / interpretado / salvo |
| 6 | **Início (Home)** | resumo | anel de prontidão, chips (sono/HRV/carga), próximo treino | carregando / ok / sem dado |
| 7 | **Coach** | decisão + perguntas | decisão do dia, botões "E se…", chat IA | verde/amarelo/vermelho |
| 8 | **Insights** | zonas + risco | tabelas de zonas, radar de risco, sparkline HRV | com/sem limiares |
| 9 | **Nutrição** | combustível | metas do dia, por sessão, calculadora de prova | — |
| 10 | **Perfil/Ajustes** | perfil + agendamento | resumo do perfil, horário matinal, gerenciar conexões | — |

---

## 3. Arquitetura (visão)

```
[App Android (Capacitor/RN)]
   │  HTTPS (JWT)
   ▼
[Backend API]  ── Auth ──▶ (provedor de identidade)
   ├── DB (Postgres) ....... perfil, plano, atividades, prontidão, histórico (memória)
   ├── Motor de decisão ..... calcula carga/prontidão + modula plano (determinístico)
   ├── LLM (server) ......... Coach + parser de planilha (com guardrails)
   ├── Scheduler (cron) ..... decisão matinal → push (FCM)
   └── Integrações
         ├── Garmin Health API (PING/push: sono, HRV, estresse, RHR)
         ├── Garmin Activity API (PING: atividades concluídas)
         └── (v1.1) Health Connect
```
Princípio: **cálculo e IA no servidor** (nunca a chave de IA no app); o app é a camada de apresentação + captura.

---

## 4. Modelo de dados (entidades e campos-chave)

- **User**: id, email, auth_provider, created_at, locale, tz.
- **Consent**: user_id, lgpd_aceito (bool), versao, data, ip.
- **DeviceConnection**: user_id, provider(garmin), oauth_tokens (criptografados), scopes, status, last_sync.
- **Profile (anamnese)**: user_id, objetivo{tipo, esportes[], multiesporte, prova{tem,data,prioridade}, obj_sem_prova, fase}, nivel, estrutura{dias_semana, sessoes_dia, hora_acordar, dia_longo}, coach{tem, modo}, saude{parq[], liberacao_medica}, lesoes[], preferencias{autonomia, tom}, updated_at.
- **Plan**: user_id, origem(importado|gerado|assessoria), status, semana[] → **PlannedSession**: dia(0-6), ordem, esporte, tipo, zona, duracao_min, obs.
- **RawWellness** (do Garmin): user_id, date, sleep{h, score, deep, rem, light}, hrv{last_night, weekly_avg, status}, rhr, stress, body_battery. (ingestão via webhook)
- **Activity** (do Garmin): user_id, garmin_activity_id, sport, start_time, duration_s, distance_m, avg_hr, max_hr, training_effect?, manual(bool). (ingestão via webhook)
- **LoadState** (calculado): user_id, date, acute_load, chronic_load, ratio(ACWR), tsb, ramp — **derivado das Activities** (o backend calcula, não o Garmin).
- **Zones** (calculado/estimado): user_id, sport, lthr, ftp, css, threshold_pace, zonas[], origem, updated_at.
- **Readiness/Decision** (por dia): user_id, date, score(0-100), state(green/amber/red), risk{level, factors[]}, sessoes_feitas[], sugestao, texto_decisao, contexto(dormiu/30min/pulou/dor|null).
- **NutritionTargets** (por dia): user_id, date, carb_g, prot_g, agua_ml, sodio_mg, por_sessao[].
- **NotificationSchedule**: user_id, tipo(matinal|pos_treino), hora, ativo, last_run.

---

## 5. Contratos de API (REST — v1)

Auth: `Authorization: Bearer <jwt>` em todas (exceto webhooks Garmin, que usam assinatura própria).

**Auth & conta**
- `POST /auth/login` · `POST /auth/refresh` · `GET /me`
- `POST /consent` {lgpd:true, versao}

**Conexões**
- `GET /connections` · `GET /connections/garmin/oauth-url` · `GET /connections/garmin/callback` (OAuth) · `DELETE /connections/garmin`

**Perfil / anamnese**
- `GET /profile` · `PUT /profile` (schema do §4)

**Plano**
- `POST /plan/import` {texto} → chama LLM parser → retorna plano estruturado (para revisão)
- `POST /plan` (salvar plano revisado) · `GET /plan` · `POST /plan/generate` {perfil} (plano de base)

**Decisão / dia**
- `GET /today` → {readiness, decision, sessoes_feitas, sugestao, risk, chips}
- `POST /today/context` {contexto:"dormiu|30min|pulou|dor"} → recalcula e retorna decisão modulada
- `POST /coach/ask` {pergunta} → resposta IA contextual

**Insights / nutrição**
- `GET /zones` · `GET /nutrition/today` · `GET /nutrition/race?horas=`

**Agendamento**
- `GET /schedule` · `PUT /schedule` {matinal:{hora,ativo}, pos_treino:{ativo}}

**Webhooks Garmin (entrada, sem JWT — validação por credencial)**
- `POST /webhooks/garmin/wellness` (PING → busca e grava RawWellness)
- `POST /webhooks/garmin/activity` (PING → grava Activity → dispara reavaliação pós-treino + push)
- Regra: responder **HTTP 200 em poucos segundos**; processamento **assíncrono** (fila).

---

## 6. Motor de decisão (server-side)

**Ingestão:** webhooks gravam RawWellness + Activity → job calcula **LoadState** (acute = média móvel exponencial ~7d do training load; chronic ~28d; ACWR = acute/chronic; TSB = chronic − acute) e atualiza **Zones** quando há esforço forte.

**Prontidão (determinística, explicável):** combina sono (score/h), HRV (status vs. baseline), LoadState (ACWR/TSB), overreaching → **score 0–100** + estado verde/amarelo/vermelho + **radar de risco** (mesmas regras do protótipo).

**Decisão do dia:** compara **planejado (Plan)** × **executado (Activities de hoje)** × **prontidão** → sessão(ões) restante(s) modulada(s); botões "E se…" reprocessam com segurança (nunca elevam carga acima do seguro).

**Camada IA (LLM no servidor):** (a) **parser de planilha** → JSON do Plan; (b) **Coach** → reescreve a decisão em linguagem humana e responde perguntas, **ancorado** na decisão determinística (não a contradiz) e nos guardrails. Guardrails: sem prescrição médica; parar em dor; escalar sinais de alerta; respeitar liberação médica do PAR-Q+.

---

## 7. Checklist — Garmin Connect Developer Program

1. **Solicitar acesso** no Garmin Developer Portal (Connect Developer Program). Prazo externo — **iniciar já**. ([Overview](https://developer.garmin.com/gc-developer-program/), [Health API](https://developer.garmin.com/gc-developer-program/health-api/))
2. **APIs a habilitar:**
   - **Health API** — sono, HRV noturna, estresse, body battery, FC repouso, respiração (dado cru de recuperação). Suporta **Ping/Pull ou Push**. ([Health API](https://developer.garmin.com/gc-developer-program/health-api/))
   - **Activity API** — atividades concluídas via **PING** (callbackURL, activityId, nome, flag "Manual"). ([Activity API](https://developer.garmin.com/gc-developer-program/activity-api/), [PING notes](https://developerportal.garmin.com/blog/garmin-connect-activity-id-available-through-activity-file-summary-endpoint-activity-api))
   - **Training API** (v2, opcional) — *escrever* treino/plano de volta no relógio. Fica para depois do beta.
3. **OAuth 2.0 com PKCE** — fluxo de conexão no app; guardar tokens **criptografados** no backend.
4. **Webhooks (PING):** um callback por tipo de dado; responder **200 em segundos**; processar assíncrono (fila). Assinar/validar origem.
5. **Assinar só os feeds necessários** (customized data feeds) — minimização de dados (LGPD).
6. **Backfill inicial** dos últimos ~28 dias (para calcular chronic load) no momento da conexão.
7. **Termos/branding do Garmin** e requisitos de exibição — revisar no onboarding do programa.

> Nota: **não** dá para obter "training status/TSB/readiness" prontos — calcular no backend (§6). Confirmar no portal quais campos de treino/VO2 vêm no payload de atividade.

**Outras integrações (v1/v1.1):**
- **Health Connect (Android)** — para wearables baratos (Amazfit/Xiaomi) — v1.1.
- **LLM** (Claude/GPT) server-side com API key própria + guardrails + cache/roteamento de custo.
- **Push:** Firebase Cloud Messaging (FCM).
- **Auth:** provedor de identidade (e-mail + Google + Apple).

---

## 8. Segurança / LGPD (não-negociável)
- Dado de saúde = **sensível**: base legal por **consentimento** explícito e versionado.
- Criptografia em repouso (tokens, dados de saúde) e em trânsito (TLS).
- Minimização (só os feeds usados), retenção definida, **exportar/apagar** self-service.
- Residência de dados no Brasil/região; DPO; log de acesso.
- Escopo **bem-estar** (fora de dispositivo médico/ANVISA) — sem diagnóstico/tratamento.

---

## 9. Stack recomendada (beta)
- **App:** **Capacitor** embrulhando a UI web já existente (chega rápido no Android) → migrar para React Native/Flutter na escala.
- **Backend:** Node (NestJS) ou Python (FastAPI) — REST + fila (Redis/SQS) para webhooks.
- **DB:** PostgreSQL. **Cache/fila:** Redis. **Push:** FCM. **Infra:** um provedor gerenciado (Render/Fly/AWS).
- **Repo:** monorepo — `/app` (mobile), `/api` (backend), `/shared` (schemas/tipos), `/infra`.

---

## 10. Roadmap de build (sprints de ~2 semanas)

- **S0 — Fundação:** repo, CI, auth, DB, telas congeladas em Capacitor (navegação + mock). Solicitar Garmin Developer Program.
- **S1 — Perfil + plano:** onboarding, PAR-Q+, parser de planilha (LLM), salvar Plan.
- **S2 — Garmin real:** OAuth + webhooks (wellness + activity) + backfill + LoadState.
- **S3 — Motor de decisão:** prontidão, risco, decisão do dia, botões "E se", Coach IA.
- **S4 — Zonas + nutrição + push:** cálculo de zonas, nutrição, cron matinal + FCM, reavaliação pós-treino.
- **S5 — Segurança/LGPD + beta:** conformidade, exportar/apagar, build assinado, **beta fechado** (você + 1 assessoria).

**Definition of Ready (beta):** um triatleta conecta o Garmin, importa o plano, recebe a decisão do dia por push, ajusta em 1 toque, e o pós-treino reavalia — com dados reais e sem travar em permissão.

---

## 11. Riscos e dependências
- **Aprovação Garmin** (prazo externo) → iniciar no S0; sem ela, usar Health Connect/entrada manual como fallback no beta.
- **Cálculo de carga fiel** (substituir os campos prontos do Garmin) → validar contra o que o app do Garmin mostra.
- **Custo de IA por usuário** → server-side com cache + modelo roteado.
- **Confiabilidade dos webhooks/sync** → fila + retries + idempotência (é onde os concorrentes falham).
- **LGPD** → privacy-by-design desde o S0.

### Fontes (Garmin)
[Developer Program](https://developer.garmin.com/gc-developer-program/) · [Health API](https://developer.garmin.com/gc-developer-program/health-api/) · [Activity API](https://developer.garmin.com/gc-developer-program/activity-api/) · [Training API](https://developer.garmin.com/gc-developer-program/training-api/) · [PING/activityId](https://developerportal.garmin.com/blog/garmin-connect-activity-id-available-through-activity-file-summary-endpoint-activity-api) · [Guia de dados](https://openwearables.io/blog/garmin-connect-api-developer-guide-activities-health-metrics)
