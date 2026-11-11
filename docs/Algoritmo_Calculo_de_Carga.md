# Algoritmo de Cálculo de Carga e Prontidão (spec de implementação)

O Garmin **não** entrega TSS/CTL/ATL/readiness na API pública — a Health API dá o cru (sono, HRV, estresse, FC repouso) e a Activity API dá as atividades. Então o **backend calcula** a carga e a prontidão. Este documento define as fórmulas, o pipeline e os limiares, prontos para implementar.

**Princípio:** escolher **uma moeda de carga** e ser consistente entre esportes; acumular em médias móveis exponenciais; derivar forma (TSB), risco (ACWR/monotonia) e um **score de prontidão 0–100**.

---

## Passo 1 — Carga por sessão (`session_load`)

Três níveis, do mais universal ao mais preciso. **Regra:** use o melhor tier disponível por sessão, mas normalize tudo para a mesma escala (~100 = 1 h no limiar).

### Tier A — TRIMP de Banister (universal, precisa de FC)
Funciona para qualquer esporte com FC (corrida, bike, natação com cinta, força).

```
HRR_frac = (HR_avg − HR_rest) / (HR_max − HR_rest)      # fração da reserva de FC (0–1)
Y = 0.64 · e^(1.92 · HRR_frac)     # homens
Y = 0.86 · e^(1.67 · HRR_frac)     # mulheres
TRIMP = duração_min · HRR_frac · Y
```
- `HR_rest`: FC repouso do usuário (Health API). `HR_max`: FCmáx **real** (máximo observado nas atividades, atualizado continuamente; nunca usar a FCmáx de um único dia). ([Banister TRIMP](https://fellrnr.com/wiki/TRIMP), [constantes](https://umit.net/ultimate-trimp-guide-runners/))
- Converter para a escala TSS: `load = TRIMP · fator_cal` (calibrar `fator_cal` para que 1 h no limiar ≈ 100; ponto de partida ~1.0 e ajustar contra os números do próprio Garmin do usuário).

### Tier B — TSS/rTSS/sTSS (mais preciso, precisa de limiar + potência/pace)
Quando há limiar (LTHR/FTP/pace de limiar/CSS) e potência/pace:
```
IF = intensidade_normalizada / limiar        # potência/FTP (bike), NGP/pace_limiar (corrida), pace/CSS (nado)
TSS = IF² · duração_horas · 100
```
- Bike: `IF = NP/FTP`. Corrida (rTSS): `IF = NGP/pace_limiar` (NGP = pace ajustado por inclinação). Nado (sTSS): `IF = pace/CSS`. ([fórmulas Coggan](https://medium.com/critical-powers/formulas-from-training-and-racing-with-a-power-meter-2a295c661b46))

### Tier C — Fallback sem FC (força sem cinta, dado faltando)
```
session_load = duração_min · fator_tipo    # fator_tipo: força 0.6, mobilidade 0.2, etc.
# ou, se houver RPE do usuário: sRPE_load = RPE(1–10) · duração_min   (escala Foster)
```

> **Recomendação MVP:** TRIMP (Tier A) como base universal + upgrade para TSS (Tier B) onde houver limiar. `session_load` diário = soma das sessões do dia.

---

## Passo 2 — CTL e ATL (médias móveis exponenciais)

Atualização **diária** (inclusive dias de descanso, com `load=0`). Time constants padrão: **CTL τ=42 dias** (forma/"fitness"), **ATL τ=7 dias** (fadiga). ([TrainingPeaks/Coggan](https://www.paincave.io/blog/ctl-atl-tsb-explained))

```
k_ctl = 1 − e^(−1/42)     ≈ 0.02347
k_atl = 1 − e^(−1/7)      ≈ 0.13314

CTL_hoje = CTL_ontem · (1 − k_ctl) + load_hoje · k_ctl
ATL_hoje = ATL_ontem · (1 − k_atl) + load_hoje · k_atl
```
- **Seed/backfill:** ao conectar o Garmin, ingerir ~**42 dias** de atividades e rodar a recorrência dia a dia para inicializar CTL/ATL (sem isso, os primeiros dias ficam subestimados). Alternativa de seed: `CTL_0 = ATL_0 = média diária dos últimos 28–42 dias`.

---

## Passo 3 — TSB, ACWR e ramp

```
TSB_hoje = CTL_ontem − ATL_ontem        # "forma": positivo = fresco, muito negativo = fadigado
```

**ACWR (acute:chronic workload ratio)** — sinal de risco de lesão:
```
# versão simples (rolling):
agudo   = soma(load, últimos 7 dias)  / 7
cronico = soma(load, últimos 28 dias) / 28
ACWR = agudo / cronico

# versão EWMA (preferida, Williams et al.): usar ATL(7) / CTL_28
# onde CTL_28 é uma EWMA com τ=28 (ou reusar ATL/uma EWMA de 28d)
```
Faixas (Gabbett): **0.8–1.3 = zona segura**; **> 1.5 = risco alto de lesão**; **< 0.8 = destreino/subcarga**. ([ACWR](https://www.sciencetosport.com/monitoring-training-load/))

**Ramp rate (regra dos ~10%):**
```
ramp = (carga_semana_atual − carga_semana_anterior) / carga_semana_anterior
# ramp > 0.10–0.15 semana a semana = subida agressiva → alerta
```

---

## Passo 4 — Monotonia e Strain (Foster)

Detectam treino "sem variação" (fator de risco independente da carga total):
```
monotonia = média(load_diário na semana) / desvio_padrão(load_diário na semana)
strain    = carga_semanal_total · monotonia
```
Sinais: **monotonia > 2.0** e **strain elevado** → maior risco de doença/lesão. ([Foster monotony/strain](https://www.iamcoach.ai/blog/trimp-training-load-explained))

---

## Passo 5 — Score de prontidão (0–100) + estado

Combina recuperação (HRV, sono) com carga (TSB, ACWR, monotonia). Cada sub-score 0–100, depois média ponderada.

**Sub-scores (bandas implementáveis):**

| Sub-score | Regra |
|---|---|
| **HRV** (peso 0.30) | `x=(HRV_7d − baseline_low)/(baseline_upper − baseline_low)` → `100·clamp(x,0,1)`. Se status = UNBALANCED, **cap em 50**. Queda ≥10 ms vs. baseline → −20. |
| **Sono** (0.25) | usa `sleep_score` (0–100); se ausente, `clamp((horas/8)·100,0,100)`. |
| **TSB/fadiga** (0.20) | `ratio=TSB/CTL`; ratio ≥ 0 → 100; 0 a −0.15 → 85; −0.15 a −0.30 → 65; −0.30 a −0.50 → 45; < −0.50 → 25. |
| **ACWR/carga** (0.15) | 0.8–1.3 → 100; 1.3–1.5 → 70; >1.5 → 35; <0.8 → 80. |
| **Monotonia** (0.10) | <1.5 → 100; 1.5–2.0 → 75; >2.0 → 45. |

```
readiness = Σ(sub_i · peso_i)              # 0–100
overreaching_detectado → readiness = min(readiness, 45)   # trava de segurança
```

**Estado (semáforo):**
```
≥ 75  → VERDE   (segue o plano)
60–74 → VERDE-  (segue, atenção leve)
45–59 → AMARELO (reduz volume/intensidade)
< 45  → VERMELHO (leve ou descanso; reagenda qualidade)
```

**Radar de risco (flags booleanas, exibidas ao usuário):** ACWR > 1.5; TSB/CTL < −0.4; HRV UNBALANCED; monotonia > 2.0; sono < 55; ramp > 0.15. (Cada flag também penaliza o sub-score correspondente acima — a lista é a explicação humana.)

---

## Passo 6 — Pipeline diário (pseudocódigo)

```python
# on Garmin PING (activity webhook)
def on_activity(activity):
    load = session_load(activity)          # Tier A/B/C
    upsert_activity(activity, load)
    recompute_day(activity.user, activity.date)   # dispara reavaliação pós-treino + push

def recompute_day(user, date):
    load_hoje = sum(a.load for a in activities(user, date))
    ctl_prev, atl_prev = load_state(user, date - 1)
    ctl = ctl_prev*(1-K_CTL) + load_hoje*K_CTL
    atl = atl_prev*(1-K_ATL) + load_hoje*K_ATL
    tsb = ctl_prev - atl_prev
    acwr = rolling_acute(user, date)/rolling_chronic(user, date)
    mono, strain = foster(user, week_of(date))
    save_load_state(user, date, ctl, atl, tsb, acwr, mono, strain)

    w  = wellness(user, date)              # sono, HRV, do Health API
    readiness, state, flags = readiness_score(w, tsb, ctl, acwr, mono, overreaching(user))
    decision = decide(plan_today(user, date), activities_today(user, date), state, ctx=None)
    save_readiness(user, date, readiness, state, flags, decision)

# cron matinal (hora do usuário): recompute_day + push(decision)
```

---

## Passo 7 — Exemplo trabalhado (dado real do Lucas)

Treino de corrida: **45 min**, FC média **154**, FCmáx (real, estimada) **188**, FC repouso **68**, homem.
```
HRR_frac = (154 − 68) / (188 − 68) = 86/120 = 0.717
Y = 0.64 · e^(1.92·0.717) = 0.64 · e^1.377 = 0.64 · 3.963 = 2.54
TRIMP = 45 · 0.717 · 2.54 ≈ 82        → session_load ≈ 82
```
Atualização (supondo CTL_ontem=65, ATL_ontem=70):
```
CTL_hoje = 65·0.97653 + 82·0.02347 = 63.47 + 1.93 = 65.4
ATL_hoje = 70·0.86686 + 82·0.13314 = 60.68 + 10.92 = 71.6
TSB_hoje = 65 − 70 = −5   (levemente fatigado)
```
Se, como hoje, ele empilha força + pedal forte + a corrida, `load_hoje` sobe muito → ATL dispara, TSB fica bem negativo e ACWR > 1.5 → **VERMELHO** (exatamente o "overreaching" que o Garmin mostrou).

---

## Passo 8 — Cold start, edge cases e validação
- **Primeiros 28–42 dias:** sem histórico, CTL/ATL são frágeis → fazer **backfill** na conexão; enquanto isso, marcar readiness como "aquecendo" e pesar mais HRV/sono.
- **Sem FC na atividade:** cair para Tier C (duração·fator) ou sRPE (pedir RPE no pós-treino).
- **Atividade manual/duplicada:** deduplicar por `garmin_activity_id`; respeitar flag `Manual`.
- **FCmáx desconhecida:** estimar (ex.: 208 − 0.7·idade) e **substituir** pelo máximo observado assim que aparecer.
- **Calibração:** durante o beta, comparar CTL/ATL/TSB calculados com os números que o app do Garmin mostra para o usuário e **ajustar `fator_cal`/τ** até baterem na ordem de grandeza.

## Parâmetros configuráveis (defaults)
`τ_CTL=42`, `τ_ATL=7`, `janela_ACWR=7/28`, `pesos_readiness={HRV .30, sono .25, TSB .20, ACWR .15, mono .10}`, `limiares_estado={75,60,45}`, `fator_cal=1.0` (ajustar).

### Fontes
[Banister TRIMP](https://fellrnr.com/wiki/TRIMP) · [constantes TRIMP](https://umit.net/ultimate-trimp-guide-runners/) · [CTL/ATL/TSB (Coggan)](https://medium.com/critical-powers/formulas-from-training-and-racing-with-a-power-meter-2a295c661b46) · [PMC/CTL-ATL-TSB](https://www.paincave.io/blog/ctl-atl-tsb-explained) · [ACWR / carga](https://www.sciencetosport.com/monitoring-training-load/) · [TRIMP/TSS/monotonia](https://www.iamcoach.ai/blog/trimp-training-load-explained)
