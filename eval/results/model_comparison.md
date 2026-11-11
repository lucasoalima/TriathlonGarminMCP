# Comparacao de abordagens — tarefa do mediator (seguro/inseguro)

> Dataset: 24 casos rotulados. Numeros medidos por `python -m triathlon_coach_llm.compare`.
> O motor deterministico e o oraculo; LLMs sao comparados contra ele e contra o gold.

| Abordagem | Acc vs gold | Kappa vs gold | Recall inseguro | Concord. c/ motor | Latencia media |
|---|---|---|---|---|---|
| engine (deterministico) | 79% | 0.58 | 75% | 100% | 0.0 ms |
| fake_baseline | 83% | 0.67 | 67% | 79% | 0.0 ms |

*Linhas 'nao executado' exigem configuracao local (Ollama em `localhost:11434` ou `ANTHROPIC_API_KEY`). Rode o comando acima na sua maquina para preenche-las.*