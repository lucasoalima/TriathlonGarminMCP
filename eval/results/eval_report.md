# Resultados da avaliacao

> Numeros medidos por `python eval/run_eval.py`. Rotulos (gold) feitos a mao a partir de principios gerais de treino de endurance, independentes do motor.

## 1. Safety gate (`validate_training_decision`)

- Casos: **24**
- Acuracia: **79%**
- Deteccao de INSEGURO -> precisao **82%**, recall **75%**, F1 **0.78**
- Kappa de Cohen (motor vs humano): **0.58**

Matriz de confusao (linha = gold, coluna = motor):

```
         unsafe   safe
unsafe        9      3
safe          2     10
```

Divergencias (onde motor e humano discordam):

- `sg06` gold=**safe** motor=**unsafe** (violacoes=['swim_on_forbidden_day']) — Natacao facil 40min num domingo
- `sg08` gold=**unsafe** motor=**safe** (violacoes=[]) — Dois treinos duros no mesmo dia (brick forte + corrida forte)
- `sg13` gold=**unsafe** motor=**safe** (violacoes=[]) — Corrida com dor, mas atleta forcou override manual
- `sg22` gold=**unsafe** motor=**safe** (violacoes=[]) — Terceiro treino forte da semana (2 ja feitos) numa base conservadora
- `sg24` gold=**safe** motor=**unsafe** (violacoes=['swim_on_forbidden_day']) — Natacao regenerativa 30min num domingo

## 2. Classificacao de execucao (`classify_completed_activity`)

- Casos: **16**
- Acuracia: **94%**
- Macro F1: **0.96** (P **0.97** / R **0.95**)
- Kappa de Cohen: **0.91**

Matriz de confusao (linha = gold, coluna = motor):

```
                completed      missed     partial substituted
completed               7           0           0           0
missed                  0           1           0           0
partial                 1           0           4           0
substituted             0           0           0           3
```

Divergencias:

- `cl13` gold=**partial** motor=**completed** — Corrida 50min planejada, feita 36min (72%)
