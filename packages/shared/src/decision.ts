// Motor de decisão: planejado × executado × prontidão → decisão do dia (+ contextos "E se").
import type { WeeklyPlan, PlannedSession, Sport, AdjustContext, ReadinessState } from "./types";

export interface DoneSession { sport: Sport; name?: string; durationMin?: number; }
export interface DecisionSession { planned: PlannedSession; status: "done" | "suggested" | "modulated"; }
export interface DayDecision { headline: string; sessions: DecisionSession[]; weekNote?: string; }

export function decideDay(
  plan: WeeklyPlan, dow: number, done: DoneSession[], state: ReadinessState, target: number, ctx: AdjustContext = null
): DayDecision {
  const today = plan[dow] || [];
  const rest = today.length === 1 && today[0].sport === "Descanso";
  const doneSports = done.map((d) => d.sport);
  const remaining = today.filter((s) => s.sport !== "Descanso" && !doneSports.includes(s.sport));
  const dc = done.length;

  let headline: string;
  if (ctx === "dor") headline = "Dor é sinal de parar — hoje sem impacto. Descanso ou mobilidade leve; se durar 3–4 dias, procure fisio/médico.";
  else if (dc >= Math.max(2, target)) headline = `Você já fez ${dc} treinos hoje. Dia cumprido — foco em recuperar.`;
  else if (dc >= 1) headline = dc >= target
    ? "Você já treinou hoje e bateu suas sessões — sem treino extra por conta própria."
    : `Você já treinou hoje. ${state === "green" ? "Se houver 2ª sessão prevista, pode seguir." : "Se houver 2ª sessão, faça-a mais leve; senão, recupere."}`;
  else if (rest) headline = "Hoje é dia leve/descanso. Aproveite para recuperar.";
  else headline = state === "red" ? "Hoje o corpo pede cautela — leve (Z1–Z2) ou descanso."
    : state === "amber" ? "Dá para treinar com o pé no freio (reduza volume/intensidade)."
    : "Prontidão boa: pode seguir sua sessão, começando leve.";

  const sessions: DecisionSession[] = today.map((s) => {
    if (doneSports.includes(s.sport)) return { planned: { ...s }, status: "done" };
    let planned: PlannedSession = { ...s };
    if (ctx === "30min" && remaining[0] === s) planned.durationMin = 30;
    if (state === "red") planned = { ...planned, zone: "Z1–Z2", durationMin: Math.min(30, planned.durationMin ?? 30) };
    else if (state === "amber" && planned.durationMin) planned.durationMin = Math.round(planned.durationMin * 0.7);
    const status: DecisionSession["status"] = (ctx || state !== "green") ? "modulated" : "suggested";
    return { planned, status };
  });

  const weekNote = ctx === "pulou"
    ? "Preservo os treinos-chave (longo + qualidade) e absorvo a falta nos fáceis; sem dobrar amanhã."
    : undefined;
  return { headline, sessions, weekNote };
}
