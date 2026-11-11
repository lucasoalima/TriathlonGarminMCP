# Atribuição e escopo de autoria

Honestidade sobre o que é meu e o que é de terceiros — importante por ser material
de portfólio acadêmico.

## O que ESTE repositório contém (autoria própria — Lucas Soares de Lima)

A **camada determinística de coaching de triatlo** e a **camada de avaliação**:

- `src/triathlon_coach/` — motor de regras, *safety gate* e auditoria de sessão do agente:
  - `engine.py` — `plan_triathlon_week`, `validate_training_decision`, `classify_completed_activity`,
    `adjust_today_workout`, `weekly_coach_review`, `plan_training_block`.
  - `mediator_audit.py` — `audit_coach_mediator_session` (auditoria do trace do LLM contra o protocolo).
  - `checkin.py`, `planning.py` — check-in subjetivo e template de semana.
- `eval/` — harness de avaliação, datasets rotulados à mão e métricas.
- `triathlon_coach_llm/` — backends de LLM e comparação de modelos.
- `tests/` — testes das camadas acima (unidade + integração, offline).

Esses módulos são **de minha autoria** e foram escritos como extensão por cima do servidor-base.

## O que NÃO está aqui (projeto-base de terceiros)

O servidor MCP base — **[Taxuspt/garmin_mcp](https://github.com/Taxuspt/garmin_mcp)**,
© Alexandre Domingues, licença MIT — que expõe 110+ ferramentas da API do Garmin
(atividades, sono, FC, treinos, etc.). **Esse código não é meu e não está incluído neste
repositório.** A minha camada foi desenhada para rodar *dentro* dele (as ferramentas aqui
são registradas no servidor via `engine.register_tools(app)`), mas aqui ela roda de forma
isolada e testável, sem a base.

- Projeto-base: https://github.com/Taxuspt/garmin_mcp (MIT, © Alexandre Domingues)
- Biblioteca de acesso ao Garmin usada pela base: `python-garminconnect` (cyberjunky), MIT.

Se você quiser executar as ferramentas conectadas ao Garmin de verdade, use o servidor-base
e adicione estes módulos a ele. Para fins de avaliação/portfólio, este repositório roda sozinho.

## Como citar minha contribuição (sem exagero)

> "Deterministic coaching/guardrail layer and evaluation harness built on top of the
> open-source Garmin MCP server (Taxuspt/garmin_mcp, MIT). The base server's 110+ Garmin
> tools are the author's extension target, not the author's work."
