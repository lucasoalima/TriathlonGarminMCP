# Handoff: Pulse Loop — App premium (Chat / Insights / Plano)

## Overview
Redesign premium do app **Pulse Loop** (`AI FOR ENDURANCE`) — um copiloto de performance para atletas de endurance
onde **o chat é o produto**. O app não é um dashboard: a IA entrega **uma decisão por dia**, e os números aparecem
apenas como rodapé silencioso da decisão.

Três abas: **Chat** (home), **Insights** (descobertas/padrões), **Plano** (missão da semana + próximos passos).
A identidade visual gira em torno do **orb** — o símbolo do loop, único elemento animado da interface, que muda de
cor e de ritmo conforme o estado do corpo do atleta.

Decisões de design deste redesign (importantes de preservar):
- **Sem tab bar inferior e sem botão flutuante verde.** A navegação é textual, no topo (Chat · Insights · Plano).
  O rodapé pertence ao composer. Isso é o que separa o produto de um app fitness.
- **A decisão da IA vem em serifa grande** (`Instrument Serif`), sem bolha de chat — como um texto editorial.
  As mensagens do usuário, sim, são bolhas.
- **Um único acento de cor por tela**, derivado do estado do corpo, propagado por CSS custom properties.
- **Nenhum gráfico, gauge, anel de atividade ou barra grossa.** Progresso = filete de 1px.

## About the Design Files
Os arquivos deste pacote são **referências de design feitas em HTML** — protótipos que mostram aparência e
comportamento pretendidos, **não código de produção para copiar**. A tarefa é **recriar estes designs no ambiente
já existente do codebase** (React Native, SwiftUI, Flutter, React web etc.), usando os padrões, tokens e bibliotecas
que o projeto já adota. Se ainda não existe ambiente, escolha o framework mais adequado ao produto (para um app
mobile de consumo, React Native ou SwiftUI) e implemente lá.

O protótipo usa um "device frame" de iPhone (`ios-frame.jsx`) apenas para apresentação — **não faz parte do produto**.
A tela real começa dentro dele: 402 × 874 pt, área útil com margem lateral de 22.

## Fidelity
**High-fidelity (hifi).** Cores, tipografia, espaçamentos, raios, blurs, animações e copy são finais e devem ser
reproduzidos fielmente. Onde o codebase já tem componentes equivalentes (botão, chip, input), use os do codebase e
ajuste os tokens para os valores abaixo.

## Screens / Views

### Estrutura comum (shell)
- Fundo: **#000000** puro (OLED). Superfícies são `rgba(255,255,255,.02–.06)`; bordas `rgba(255,255,255,.07)`.
- **Glow ambiente**: um círculo de 540 × 430, `top:-200`, centralizado, `radial-gradient(circle, var(--st-glow) 0%, transparent 66%)`,
  `filter: blur(48px)`, `opacity:.62`, animação de halo. É a única "iluminação" da tela.
- **Header** (altura 40, padding-top 56 por causa da status bar): à esquerda o **orb 26 × 26** + wordmark `LOOP`
  (Hanken Grotesk 400, 11px, `letter-spacing:.36em`, `rgba(255,255,255,.8)`); à direita um ícone de ajustes
  (3 traços de 1.5px: larguras 15/10/14, gap 3.5, `rgba(255,255,255,.38)`).
- **Abas**: linha de texto com gap 26, `margin-top:18`, `padding-bottom:11`.
  Ativa = 500/14px `#F2F4F3` + filete de 1.5px na base com `background: var(--st)` e `box-shadow: 0 0 12px var(--st-glow)`.
  Inativa = 400/14px `rgba(255,255,255,.32)`. Abaixo, hairline de 1px `rgba(255,255,255,.07)`.
- **Área de conteúdo**: rolagem vertical, scrollbar oculta, padding lateral 22.
- **Composer** (fixo no rodapé, padding `10px 22px 40px`, com gradiente de fade para #000 por cima do conteúdo):
  pill `border-radius:26`, `background: rgba(255,255,255,.05)`, borda `rgba(255,255,255,.08)`, `backdrop-filter: blur(30px)`,
  input 14.5px placeholder "Pergunte qualquer coisa…" (`rgba(255,255,255,.26)`), e botão circular 36 × 36 com
  `background: var(--st)`, seta para cima (stroke 1.8, `#04120A`), `box-shadow: 0 4px 18px var(--st-glow)`.

### 1. Chat (home)
**Propósito:** o usuário pergunta como o corpo está e recebe a decisão do dia.

Ordem vertical (a ordem importa):
1. **Orb 52 × 52** (tocável — cicla os estados) + saudação **"Bom dia, {nome}."** em Instrument Serif 400/36px,
   `line-height:1.06`, `letter-spacing:-.01em`, `#F4F6F5`; subtítulo "Como você está se sentindo hoje?"
   Hanken Grotesk 300/15px `rgba(255,255,255,.42)`. Gap horizontal 16.
2. **Chip de estado** (pill `999`, padding `7px 12px 7px 10px`, `background: var(--st-tint)`, borda `var(--st-line)`):
   ponto 6px `var(--st)` com glow + label em JetBrains Mono 400/10px, `letter-spacing:.14em`, `color: var(--st)`.
   Ex.: `EQUILIBRADO · CORPO EM HARMONIA`, `RECUPERAÇÃO BAIXA · 68%`.
3. **Mensagem do usuário** (direita, max-width 80%): `border-radius: 20 20 6 20`, `background: rgba(255,255,255,.06)`,
   borda `rgba(255,255,255,.07)`, blur 20, texto 400/15px `rgba(255,255,255,.92)`; timestamp abaixo à direita em
   JetBrains Mono 300/9.5px `rgba(255,255,255,.24)`. Copy: "Posso fazer um treino intenso hoje?" · 09:36.
4. **Resposta da IA** (sem bolha, largura total): título Instrument Serif 400/27px `#F4F6F5` — "Hoje, não." —
   e corpo Hanken Grotesk 300/15px `line-height:1.6` `rgba(255,255,255,.58)`:
   "Sua recuperação ainda não está ideal — e eu prefiro te devolver a semana inteira do que um treino forte hoje."
5. **Motivos** (3 linhas, gap 16): ponto 6px colorido por domínio (carga `#9C6CFF`, HRV `#63D471`, sono `#5DA8FF`) +
   título 500/14px `rgba(255,255,255,.9)` + sub 300/12.5px `rgba(255,255,255,.38)`:
   - Carga recente elevada / Acúmulo dos últimos dias
   - HRV abaixo do seu ideal / Seu sistema nervoso precisa de mais tempo
   - Sono abaixo da média / Qualidade do sono impactou sua recuperação
6. **Métricas** (grid 4 colunas, entre dois hairlines, padding `18px 0 20px`): label JetBrains Mono 300/9px
   `letter-spacing:.12em` `rgba(255,255,255,.3)`; valor 400/17px `rgba(255,255,255,.88)` (unidade 10px em .35);
   delta JetBrains Mono 300/9.5px.
   `HRV 62ms / −12%` · `SONO 6h32 / −48min` · `CARGA 780 / alta` · `RECUP. 68% / baixa` (este valor usa `var(--st)`).
7. **Card de sugestão** (`border-radius:24`, `background: linear-gradient(180deg, rgba(255,255,255,.055), rgba(255,255,255,.02))`,
   borda `rgba(255,255,255,.075)`, blur 30, padding 20): kicker `SUGESTÃO PARA HOJE` (mono 9.5px, .16em) com ponto 5px;
   título Instrument Serif 21px "Treino regenerativo"; sub 300/13.5px "Bike Z2 · 60–75 min · movimento que acelera a
   recuperação, não a consome."; dois botões (gap 9, altura ~44, radius 14): **Aceitar** (`background: var(--st)`,
   texto `#04120A` 500/13.5px, `box-shadow: 0 6px 22px var(--st-glow)`) e **Outra opção** (ghost, `rgba(255,255,255,.05)`).
   Depois de aceitar, os botões são substituídos por uma faixa `var(--st-tint)` + `var(--st-line)` com
   `NO PLANO DE HOJE · 07:30` em mono 10px `var(--st)`.
8. **Recibo de contexto**: `LEITURA: HRV 7D · SONO 3N · CARGA 14D` (mono 300/9.5px, `rgba(255,255,255,.22)`).
9. **Chips de sugestão** (acima do composer, rolagem horizontal, gap 8): "E amanhã?", "Por que meu HRV caiu?",
   "Como melhorar meu sono?" — pill 999, `rgba(255,255,255,.045)`, borda `rgba(255,255,255,.08)`, 400/12.5px.
   Tocar envia a pergunta como mensagem do usuário.

### 2. Insights
**Propósito:** mostrar descobertas, nunca gráficos.
- Kicker `PADRÕES · ÚLTIMAS 6 SEMANAS` (mono 9.5px, .16em, `rgba(255,255,255,.32)`).
- Título Instrument Serif 400/33px: "A IA encontrou três coisas sobre você."
- Três blocos separados por hairlines (padding 24 vertical), cada um: ponto 5px + kicker de domínio/confiança
  (mono 300/9.5px .14em), afirmação Instrument Serif 400/20px `#EFF2F0`, evidência 300/13px `rgba(255,255,255,.4)`:
  1. `SONO · CONFIANÇA ALTA` — "Seu sono influencia diretamente sua performance." / "Quando você dorme mais de 7h, sua consistência aumenta 23%." + botão ghost "Conversar sobre isso" (radius 12, padding 9×14) que leva ao Chat com a pergunta já enviada.
  2. `RECUPERAÇÃO · CONFIANÇA ALTA` — "Treinos regenerativos fazem grande diferença para você." / "Sua recuperação melhora 32% quando inclui pelo menos um por semana."
  3. `RITMO · CONFIANÇA MÉDIA` — "Você performa melhor quando treina pela manhã." / "Seu corpo responde melhor a estímulos entre 06h e 10h."
- Rodapé: ponto roxo pulsando + `2 HIPÓTESES AINDA EM OBSERVAÇÃO`.

### 3. Plano
**Propósito:** mostrar a missão da semana e o próximo passo — nunca um calendário.
- Linha superior: `PLANO ATUAL` (esquerda) e `SEMANA 3 DE 4` (direita), mono 9.5px.
- Título Instrument Serif 400/33px: "Construção de base, sem custo de recuperação."
- Sub 300/14.5px: "Manter consistência, aumentar volume em Z2 e melhorar eficiência."
- Progresso: "4 de 6 sessões concluídas" (400/12.5px) + `NO RITMO` (mono 9.5px) e **filete de 1px** com 66% em
  `var(--st)` + `box-shadow: 0 0 8px var(--st-glow)` sobre trilha `rgba(255,255,255,.1)`. **Nunca uma barra grossa.**
- Kicker `PRÓXIMOS PASSOS`, depois o card de hoje (mesmo estilo do card de sugestão): kicker `HOJE · 07:30`,
  título "Bike Z2 · 60–75 min", sub "Zona 2 firme, cadência alta, sem picos. Termine achando que podia mais."
- Duas linhas simples entre hairlines: `AMANHÃ` / "Corrida leve" / 40–50 min · `QUINTA` / "Força" / 30–40 min.
- Botão ghost full-width "Ajustar o plano com a IA" → vai ao Chat com a pergunta enviada.

## Interactions & Behavior
- **Trocar aba**: instantâneo, sem transição de página; o glow ambiente permanece.
- **Enviar mensagem** (Enter ou botão): adiciona a bolha do usuário, o estado do orb vira **Analisando (roxo)** e
  aparece o indicador "LENDO SEU CONTEXTO" (3 pontos 5px com `pl-dot` 1.1s, delays 0/.18/.36s). Após **1900 ms**,
  o indicador sai, o estado volta para **Equilibrado** e a resposta da IA entra.
- **Entrada de mensagem**: `pl-in` — 0.5s `cubic-bezier(.2,.7,.3,1)`, de `opacity:0/translateY(8px)` a `opacity:1/translateY(0)`.
- **Auto-scroll** para o fim da lista a cada nova mensagem (`behavior:'smooth'`).
- **Tocar no orb** cicla os 6 estados (no produto real, o estado vem dos dados; o toque deve abrir o detalhe do estado).
- **Chips e CTAs de Insights/Plano** enviam perguntas pré-definidas com respostas específicas (ver State Management).
- **Aceitar sugestão** troca os botões pela confirmação com horário.
- Nenhuma outra animação na tela: **só o orb, o glow e as entradas de mensagem se movem.**

### Estados do orb (o coração da identidade)
| Estado | Cor | Movimento | Copy |
|---|---|---|---|
| Equilibrado | `#63D471` | deriva 12s (`scale` 1→1.03 + `rotate` ±4°) | Seu corpo em harmonia. |
| Atenção | `#FFBA2A` | pulso 3.6s (`scale` 1→1.05 + brightness 1→1.25) | Sinais pedem atenção. |
| Recuperação baixa | `#EF4A3A` | quase parado 11s (`scale` 1→1.012, brightness .9→1) | Hora de priorizar descanso. |
| Foco / Deep Work | `#5DA8FF` | giro 30s linear | Concentração máxima. |
| Analisando | `#9C6CFF` | órbita 2.6s linear (rotate 360° + `scale` 1.04) | IA processando padrões. |
| Relaxamento | `#22D3EE` | respiro 8s (`scale` .94→1.08→1.01) | Momento de desacelerar. |

Halos correspondentes: `pl-halo` 8s (op .5→.9, scale 1→1.16), `pl-halo-slow` 8–10s (.36→.78, .96→1.22),
`pl-halo-min` 11s (.3→.44, 1→1.05).

Cada estado define quatro valores derivados da sua cor, aplicados como CSS custom properties no container:
`--st` (cor pura), `--st-glow` (alpha ~.28–.34), `--st-tint` (alpha .07–.08), `--st-line` (alpha .2–.24),
mais `--st-motion` e `--st-halo` (as animações). **Em código nativo, o equivalente é um objeto de tema por estado.**

## State Management
- `tab: 'chat' | 'insights' | 'plano'`
- `bodyState: 0..5` (índice dos estados acima; na vida real derivado de HRV/sono/carga)
- `messages: [{ id, role: 'user' | 'ai', text, head?, time?, hasCard? }]` — `head` é a frase-decisão em serifa;
  `hasCard` liga o bloco motivos + métricas + sugestão.
- `draft: string` (input), `thinking: boolean`, `accepted: boolean`
- Respostas mockadas por pergunta: `tomorrow`, `hrv`, `sleep`, `plan`, `generic` (textos completos em
  `PULSE LOOP — App.dc.html`, constante `REPLIES`). No produto, isso vira a chamada ao serviço de IA — mantenha o
  padrão **decisão curta em uma frase + justificativa em 1–2 frases + evidências**.
- Dados exibidos (HRV, sono, carga, recuperação, plano) devem vir do backend; no protótipo são fixos.

## Design Tokens
**Cores de estado / marca**
`#63D471` verde (equilibrado, acento padrão) · `#22D3EE` teal (relaxamento) · `#5DA8FF` azul (foco, sono) ·
`#9C6CFF` roxo (analisando, carga) · `#FFBA2A` âmbar (atenção, ritmo) · `#EF4A3A` vermelho (recuperação baixa)

**Neutros**
Fundo `#000000` · superfícies `#1A1C1F`, `#2A2D31` · texto primário `#F2F4F3` / `#F4F6F5` ·
secundário `rgba(255,255,255,.58)` · terciário `rgba(255,255,255,.42)` · sutil `rgba(255,255,255,.32)` ·
mínimo `rgba(255,255,255,.24)` · bordas `rgba(255,255,255,.07–.08)` · texto mono `#889098`

**Tipografia**
- `Instrument Serif` 400 — a voz da IA (decisões e títulos): 36 / 33 / 27 / 21 / 20, `letter-spacing:-.01em`, `line-height` 1.06–1.35
- `Hanken Grotesk` 300/400/500/600 — interface (substituto web de **Aeonik**; no app use Aeonik se licenciado): 16 / 15 / 14.5 / 13.5 / 12.5 / 12 / 11
- `JetBrains Mono` 300/400 — dados, kickers e labels: 10 / 9.5 / 9, `letter-spacing` .08–.16em, sempre em caixa alta
- Wordmark `LOOP`: 11px, `letter-spacing:.36em`. Wordmark institucional `PULSE LOOP`: 300/30px, `.38em`; descritor `AI FOR ENDURANCE` mono 10px `.34em` em `#63D471`.

**Espaçamento** — margem lateral 22 · ritmo base 6 (6/8/10/12/16/18/22/26/32/46)
**Raios** — 14 (botões) · 16 (chips de lista) · 24 (cards) · 20/6 (bolha) · 999 (pills)
**Blur** — 20 (bolha) · 30 (vidro: cards, composer) · 48 (glow ambiente) · 5–10 (halos do orb)
**Sombras** — `0 6px 22px var(--st-glow)` (CTA) · `0 4px 18px var(--st-glow)` (botão enviar) · `0 0 8–12px var(--st)` (pontos e filetes)
**Motion** — entradas .5s `cubic-bezier(.2,.7,.3,1)`; transições de cor .3s ease; ciclos do orb 2.6–30s conforme o estado

## Assets
- `assets/mark.png` — o símbolo **Pulse Loop** (loop tri-lobado com gradiente verde→teal→azul→roxo e glow),
  extraído do brand board enviado pelo cliente. **Peça o vetor original (SVG/AI) ao designer antes de implementar** —
  em produção o orb deve ser vetor ou, idealmente, um shader/Lottie para animar com qualidade.
- `assets/orb-equilibrado.png`, `orb-atencao.png`, `orb-baixa.png`, `orb-foco.png`, `orb-analisando.png`,
  `orb-relaxamento.png` — o orb em cada estado, também extraídos do brand board.
- Todos os PNGs têm fundo preto e são compostos com `mix-blend-mode: screen` sobre o fundo #000.
  Em produção, prefira PNG/SVG com **transparência real** ou o mesmo loop colorizado via tint.
- `uploads/*.png` — os brand boards originais (Pulse Loop / Orb) com conceito, valores, paleta, ícone do app e tipografia.
- Ícones: o protótipo usa **pontos coloridos e traços geométricos** em vez de ícones ilustrativos — proposital.
  Se o codebase tiver um set de ícones de linha (peso 1.5px), use-o com moderação, apenas onde o brand board indica.

## Files
- `PULSE LOOP — App.dc.html` — **o design principal**: app completo (Chat/Insights/Plano) interativo,
  painel de estados do orb, paleta e tokens. Comece por aqui.
- `SINAL — App Premium.dc.html` — iteração anterior (mesma estrutura, marca provisória "SINAL"). Referência histórica.
- `ios-frame.jsx` — moldura de iPhone usada só na apresentação. **Não implementar.**
- `assets/` — símbolo e orbs por estado.
- `uploads/` — brand boards do cliente.

Abra os `.dc.html` em um navegador para ver os designs funcionando (troque os estados no painel à direita,
navegue pelas abas, envie mensagens).
