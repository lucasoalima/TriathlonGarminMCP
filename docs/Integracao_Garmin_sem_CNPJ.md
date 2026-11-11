# Integração Garmin SEM CNPJ — decisão de fonte de dados

**Resposta curta:** sim, dá para começar **sem CNPJ e sem o Garmin Developer Program**. Só existe um trade-off de **profundidade de dados** (principalmente HRV) entre os caminhos.

## Os 3 caminhos (comparados)

| Caminho | Precisa CNPJ? | Dados que chegam | HRV / estresse / Body Battery? | Pode publicar na loja? | Custo |
|---|---|---|---|---|---|
| **Health Connect (Android) / Apple Health** | ❌ Não | passos, **FC, sono (estágios), SpO2, treinos** | ❌ **Não** (Garmin não compartilha) | ✅ Sim | Grátis |
| **Agregador (Terra / Rook / Spike)** | ❌ Não p/ começar | igual à API do Garmin (mais rico) | ✅ Geralmente sim (eles têm acesso à Health API) | ✅ Sim | Free tier ~25–50 usuários, depois pago |
| **Scraping (garth / python-garminconnect)** | ❌ Não | **tudo** que o Garmin Connect mostra (inclui HRV/status) | ✅ Sim | ❌ **Não** (viola ToS — só uso pessoal/fechado) | Grátis |

> Fonte da limitação do Health Connect: [Android Central](https://www.androidcentral.com/wearables/garmin/heres-everything-garmin-will-and-wont-share-with-google-health-connect) — Garmin envia sono/FC/SpO2/treinos, mas **retém HRV, estresse, Body Battery, training load/status e VO2**.

## Impacto no nosso motor
- Nosso score de prontidão usa **HRV (30%)**. Via **Health Connect não temos HRV.**
- Solução: o motor é modular — sem HRV, **recalibramos os pesos** para o que temos:
  - **Sono ~40%**, **carga/TSB ~35%**, **ACWR ~15%**, **monotonia ~10%**.
  - A **carga** a gente **já calcula sozinho** (TRIMP do treino + FC) — isso continua funcionando com Health Connect.
- Ou seja: com Health Connect dá para ter um **produto muito bom** (decisão do dia baseada em carga + sono + risco), só **sem o sinal fino de HRV**. HRV entra depois via agregador ou Garmin direto.

## Sequência recomendada (sem travar em CNPJ)
1. **Agora — dogfood (você + amigos):** continue no Cowork (que é, na prática, o caminho 3 — dado completo, inclusive HRV). Zero CNPJ, uso pessoal/fechado. É o que você já está fazendo.
2. **Beta Android real (sem CNPJ):** **Health Connect** como fonte principal (grátis, oficial, publicável). Motor recalibrado (sono + carga). Se quiser HRV já no beta, plugar um **agregador no free tier** (Terra/Rook/Spike) — também sem CNPJ para começar.
3. **Escala:** aí sim avaliar o **Garmin Developer Program direto** (precisa de empresa/CNPJ) para ter HRV/estresse first-party e tirar a dependência/custo do agregador — **ou** simplesmente ficar no agregador.

## O que muda no plano de ação
- **CNPJ e Garmin Developer Program saem do caminho crítico do beta.** Viram passo de **escala/otimização**, não pré-requisito.
- O S2 do plano (“Garmin real”) passa a ser **“Integração via Health Connect”** — mais rápido e sem burocracia.
- Você ganha tempo: abre o CNPJ com calma (decisão de empresa) enquanto o beta já roda com dado real via Health Connect.

## Recomendação
Para o **beta Android**: **Health Connect** (grátis, sem CNPJ, publicável) + motor recalibrado. Manter um **agregador no radar** para adicionar HRV sem depender de aprovação do Garmin. **Garmin direto** só quando fizer sentido comercial/escala.

Fontes: [Android Central — Garmin × Health Connect](https://www.androidcentral.com/wearables/garmin/heres-everything-garmin-will-and-wont-share-with-google-health-connect) · [Spike API — por que integrar Garmin](https://www.spikeapi.com/blog/why-integrate-garmin-api-directly) · [Terra](https://tryterra.co/) · [Rook](https://www.tryrook.io/)
