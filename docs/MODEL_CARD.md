# Model / Decision Card — camada de coaching de triatlo

Documento de IA responsável para a camada determinística + avaliação. Cobre finalidade,
dados, métricas medidas, limitações, viés, privacidade e ética.

## Finalidade e design
Sistema **neuro-simbólico**: um motor **determinístico** (regras de ciência do treino)
atua como **guardrail** e **auditor** de um agente LLM (o "mediator", ex.: Claude via MCP).
O LLM conversa e decide a mensagem final; o motor **computa, valida, classifica e sinaliza**,
e o `audit_coach_mediator_session` verifica se o LLM seguiu o protocolo (ordem de ferramentas,
*safety gates*, integridade de dados). Princípio: **segurança acima de performance**.

## Não é
- Não é dispositivo médico nem conselho médico. Escopo **bem-estar/performance**.
- Não diagnostica lesão/doença. Dor → recomenda parar e procurar profissional.
- Não substitui treinador humano; serve de camada de segurança e organização.

## Dados
- **Nenhum dado pessoal** versionado. Os datasets de avaliação (`eval/dataset/*.jsonl`) são
  **sintéticos**, escritos à mão para cobrir casos de segurança e execução.
- Em produção, os dados viriam do servidor MCP base (Garmin) — ver `ATTRIBUTION.md`. Este
  repositório **não acessa a conta do Garmin** e não guarda tokens.

## Métricas medidas (reprodutíveis)
Geradas por `python eval/run_eval.py` e `python -m triathlon_coach_llm.compare`
(ver `eval/results/`). **Números reais, não inventados; datasets pequenos — tratar como indicativo.**

- **Safety gate** (`validate_training_decision`, n=24): acurácia **79%**, recall de "inseguro"
  **75%**, κ de Cohen (motor vs. rótulo humano) **0.58**.
- **Classificação de execução** (campo `status`, n=16): acurácia **94%**, macro-F1 **0.96**, κ **0.91**.
- **Baseline vs. motor** (tarefa seguro/inseguro): o baseline heurístico simples teve **83%**
  de acurácia vs. gold — *acima* do motor (79%) neste conjunto, porque o motor aplica uma regra
  opinativa ("sem natação no domingo") que gera falsos positivos nos rótulos gerais. Ver limitações.

## Limitações conhecidas
1. **`execution_quality` depende de FC.** Sem dados de frequência cardíaca, o campo degenera
   para `"acceptable"`; por isso a avaliação usa o campo `status` (duração/esporte), que é
   robusto sem FC. (Documentado no `eval/run_eval.py`.)
2. **Regras opinativas.** "Sem natação no domingo" é uma preferência pessoal/treino, não uma
   regra universal — penaliza a acurácia contra rótulos gerais (falsos positivos sg06/sg24).
3. **Permissividade a volume.** Excesso de sessões duras na semana entra como *warning*, não
   como bloqueio → o motor pode liberar casos que um humano marcaria como inseguros (sg08/sg22).
4. **Override de dor.** `manual_override_pain=True` desliga o bloqueio de correr com dor — risco
   de bypass do guardrail (sg13). Deveria exigir confirmação explícita e registro.
5. **Datasets pequenos e sintéticos** (24 e 16 casos). Métricas são indicativas, não conclusivas.

## Viés
- Perfil padrão `conservative` / `beginner_returning`: o motor tende a ser cauteloso, o que é
  desejável por segurança, mas pode **subtreinar** atletas avançados. Perfis mais agressivos
  mudam os limites (`DEFAULT_ATHLETE_PROFILE`).
- Regras calibradas para um atleta de triatlo adulto; **não** validadas para outras populações
  (juvenis, gestantes, condições clínicas).

## Privacidade (LGPD)
- Dado de saúde é **sensível**. Este repo evita o problema não armazenando dado pessoal.
- Em produção: consentimento explícito, criptografia em repouso/trânsito, direito de
  exportar/apagar, e **tokens do Garmin nunca no código** (ver `.gitignore` e `.env.example`).

## Uso responsável
Saídas são **restrições técnicas** para um humano/LLM decidir — não ordens. Em dúvida clínica
(dor persistente, sintomas), o sistema recomenda procurar profissional de saúde.
