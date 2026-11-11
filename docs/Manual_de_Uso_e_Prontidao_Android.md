# Copiloto do Corpo — Modo de Uso + Prontidão para Android

---

# Parte 1 — Modo de uso do usuário (ponta a ponta)

Como o usuário vive o app, do primeiro toque ao uso contínuo.

### 0. Descoberta e instalação
Baixa na Play Store (ou entra pela lista de espera/assessoria parceira) e abre pela primeira vez.

### 1. Boas-vindas + consentimento (LGPD)
Tela curta explicando o que o app faz ("seu copiloto de treino e recuperação") e pedindo **consentimento** para tratar dados de saúde (dado sensível). Sem consentimento, não avança.

### 2. Conectar o wearable
Conecta a fonte de dados: **Garmin** (ou Apple Health / Health Connect no Android para quem usa Amazfit/Xiaomi/etc.). Uma conexão já basta para começar — "traga o seu wearable".

### 3. Onboarding / anamnese (essencial primeiro)
Responde o **essencial** (Blocos 1–3): objetivo e modalidade, tem prova e quando, experiência, estrutura (dias/semana, sessões/dia, horário que acorda), se tem assessoria, **PAR-Q+** (segurança) e lesões. Isso vira o **Perfil do Atleta**. O resto (zonas, nutrição, preferências) aprofunda depois, via uso.

### 4. Definir o "planejado"
Dois caminhos:
- **Tem assessoria** → **importa o plano** (cola a planilha/PDF/WhatsApp; a IA estrutura). O Copiloto coexiste com o coach.
- **Não tem** → o Copiloto monta um plano semanal periodizado a partir do perfil.

### 5. Uso diário (o coração do produto)
- **Manhã (no horário que ele acorda):** recebe uma **notificação** com a **Decisão do Dia** — o que treinar ou recuperar, já modulado pela prontidão (sono/HRV/carga). Verde = segue; amarelo = reduz; vermelho = leve/descanso.
- **Abre o app (Início):** vê o **score de prontidão**, os treinos de hoje e a sugestão do dia.
- **Vida acontece:** toca em **"E se…"** (dormi mal / só tenho 30 min / pulei o treino / estou com dor) e o plano se reajusta **com segurança**, sem criar picos de lesão.
- **Depois do treino:** ao sincronizar do Garmin, o Copiloto **relê o que foi feito** e reavalia o resto do dia/semana (gatilho pós-treino).
- **Coach:** pergunta qualquer coisa ("posso treinar forte hoje?", "por que meu HRV caiu?") e recebe resposta contextual e segura.

### 6. Ritmo semanal
- **Insights:** vê zonas (FC/ritmo/potência) que **se atualizam sozinhas** conforme os treinos fortes, o **radar de risco** e a tendência de HRV.
- **Nutrição:** combustível do dia por carga, carbo por sessão e estratégia de prova quando houver.
- **Resumo da semana** e ajustes de rumo.

### 7. Uso contínuo (o que retém)
Memória de longo prazo aprende o corpo dele; o produto fica melhor com o tempo. Re-anamnese leve por gatilho (nova prova, lesão, mudança de fase). O valor chega **pela notificação** — ele não precisa "abrir o app todo dia" para ser bem servido.

**Em uma frase:** consentir → conectar wearable → anamnese → importar/gerar plano → receber a decisão do dia todo dia e ajustar em 1 toque → evoluir com segurança.

---

# Parte 2 — Está pronto para compilar num projeto Android?

## Resposta direta: **ainda não.** O que temos é um **protótipo de design + lógica** (excelente como base e prova de conceito), não um app compilável.

**Por quê:** os módulos rodam como **HTML/JS dentro do Cowork** e dependem de "pontes" que **só existem aqui** — `window.cowork.callMcpTool` (Garmin via conector de desenvolvimento), `window.cowork.askClaude` (IA) e `runScheduledTask` (agendamento). Num APK Android essas pontes não existem. Ou seja: o **desenho das telas, a lógica de decisão, o fluxo e a integração com o Garmin estão provados** — mas falta a **camada de produção** por baixo.

## O que já está pronto (aproveitável)
- **UX/UI** dark completa e navegável (base de design).
- **Lógica de produto:** motor de decisão (prontidão verde/amarelo/vermelho), radar de risco, replanejamento seguro, zonas automáticas, nutrição por carga, parser de planilha por IA.
- **Fluxo end-to-end** (onboarding → plano → decisão → agendamento) e o schema do Perfil/Plano.
- **Prova de que o dado do Garmin vira decisão real** (rodou com seus dados).
- Estratégia, mercado, deck e riscos (documentos anteriores).

## O que falta para virar um app Android de verdade
| Camada | Hoje (protótipo) | Para produção |
|---|---|---|
| **Frontend mobile** | HTML/JS no Cowork | App em **React Native/Expo**, **Flutter** ou **Capacitor** (embrulha o web) |
| **Backend/API** | nenhum (roda no navegador) | Servidor: contas, dados, motor de decisão, orquestração |
| **Integração Garmin** | conector MCP (dev) | **Garmin Connect Developer Program** real: OAuth 2.0 + webhooks (precisa de aprovação) |
| **Outros wearables** | — | **Health Connect (Android)** e Apple Health |
| **IA** | `askClaude` do Cowork | LLM chamado **no servidor** (sua API key) + guardrails + cache/custo |
| **Login/contas** | — | Auth (e-mail/Google/Apple) |
| **Dados/memória** | `localStorage` do navegador | Banco de dados por usuário (o **moat** de memória longitudinal) |
| **Notificações/agendamento** | tarefa do Cowork | **Cron no servidor + push (FCM)** para a decisão matinal; **webhook Garmin** para o pós-treino |
| **Segurança/LGPD/ANVISA** | mínimo | Criptografia, consentimento, residência de dados, escopo bem-estar |
| **Publicação** | — | Build assinado, conta Play Console, revisão da loja |

## Caminho recomendado até o MVP Android
1. **Fechar o Perfil do Produto (1 semana):** congelar telas do MVP (Início, Coach/decisão, Plano, Perfil) e o schema de dados.
2. **Backend fino + Auth + DB (2–4 semanas):** contas, armazenar perfil/plano/histórico, endpoints do motor de decisão, IA server-side com guardrails.
3. **Integração Garmin real (2–4 semanas, + tempo de aprovação):** solicitar o Developer Program, OAuth, ingestão de sono/HRV/carga/atividades + webhook pós-treino. Adicionar Health Connect.
4. **App mobile (3–6 semanas):** recomendo começar com **Capacitor** (reaproveita boa parte da UI web que já temos → chega rápido no Android) e migrar para **React Native/Flutter** se precisar de mais nativo. Push via FCM.
5. **Segurança/LGPD + loja (1–2 semanas):** conformidade, consentimento, política de privacidade, build assinado, publicação em beta fechado (com a assessoria parceira).

**Ordem de grandeza (a validar):** um MVP Android testável em beta fechado ≈ **2–3 meses** com 1–2 devs full-stack + integração Garmin, reusando esta base. Sem "big bang": beta fechado primeiro (dogfood + assessoria), depois abertura.

## Decisão-chave de stack
- **Mais rápido:** Capacitor/Ionic embrulhando a UI web atual + backend Node/Python. Aproveita o que já existe; ótimo para o beta.
- **Mais nativo/escalável:** React Native (Expo) ou Flutter. Melhor a longo prazo; custa mais tempo agora.
Recomendação: **Capacitor para o beta**, reavaliar para RN/Flutter na hora de escalar.

## Riscos técnicos que decidem o cronograma
- **Aprovação do Garmin Developer Program** (prazo externo) — começar já.
- **Custo de IA por usuário** — resolver no servidor (cache, roteamento de modelo).
- **Confiabilidade dos webhooks/sync** — a robustez de integração é o que os concorrentes erram (Etapa 1).
- **LGPD com dado de saúde** — privacy-by-design desde o primeiro commit.

## Conclusão honesta
Temos a coisa mais difícil de acertar — **o produto certo, o desenho e a lógica que decidem com segurança a partir de dados reais**. O que falta é **engenharia de produção conhecida** (backend, auth, integrações oficiais, packaging), não invenção. Não é "compilar o que existe": é **reconstruir esta base como app + servidor**. A boa notícia: nada aqui é incerto — é execução, e a base encurta muito o caminho.

**Próximo passo sugerido:** eu monto o **escopo técnico do MVP Android** (telas congeladas + modelo de dados + contratos de API + checklist do Garmin Developer Program) para virar um plano de build acionável. Quer?
