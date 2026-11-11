// Motor de carga: TRIMP/TSS por sessão + CTL/ATL/TSB + ACWR + monotonia.
import type { Activity, Athlete, LoadPoint } from "./types";

export const TAU_CTL = 42;
export const TAU_ATL = 7;
export const K_CTL = 1 - Math.exp(-1 / TAU_CTL); // ~0.02347
export const K_ATL = 1 - Math.exp(-1 / TAU_ATL); // ~0.13314

export function clamp(x: number, a: number, b: number): number { return Math.max(a, Math.min(b, x)); }
function avg(a: number[]): number { return a.length ? a.reduce((s, x) => s + x, 0) / a.length : 0; }
function sum(a: number[]): number { return a.reduce((s, x) => s + x, 0); }
function std(a: number[]): number { const m = avg(a); return Math.sqrt(avg(a.map((x) => (x - m) ** 2))); }

/** TRIMP de Banister (universal, precisa de FC). */
export function trimp(a: Athlete, durationMin: number, avgHr: number): number {
  const hrr = clamp((avgHr - a.hrRest) / (a.hrMax - a.hrRest), 0, 1);
  const Y = a.sex === "F" ? 0.86 * Math.exp(1.67 * hrr) : 0.64 * Math.exp(1.92 * hrr);
  return durationMin * hrr * Y;
}

/** TSS a partir do Intensity Factor (potência/pace vs limiar). */
export function tssFromIF(durationMin: number, IF: number): number {
  return IF * IF * (durationMin / 60) * 100;
}

/** Escolhe o melhor tier para a sessão. calFactor calibra TRIMP para a moeda TSS. */
export function sessionLoad(a: Athlete, act: Activity, calFactor = 1.0): number {
  if (act.intensityFactor && act.intensityFactor > 0) return tssFromIF(act.durationMin, act.intensityFactor);
  if (act.avgHr && a.hrMax > a.hrRest) return trimp(a, act.durationMin, act.avgHr) * calFactor;
  const factor = act.sport === "Força" ? 0.6 : act.sport === "Descanso" ? 0 : 0.7; // fallback sem FC
  return act.durationMin * factor;
}

export function ewmaUpdate(prev: number, today: number, k: number): number { return prev * (1 - k) + today * k; }

export interface DailyLoad { date: string; load: number; }

/** Calcula CTL/ATL/TSB a partir de uma série diária de carga (dias de descanso = 0). */
export function computeLoadSeries(series: DailyLoad[], seedCtl = 0, seedAtl = 0): LoadPoint[] {
  let ctl = seedCtl, atl = seedAtl; const out: LoadPoint[] = [];
  for (const d of series) {
    const tsb = ctl - atl;                 // forma usa valores de ontem
    ctl = ewmaUpdate(ctl, d.load, K_CTL);
    atl = ewmaUpdate(atl, d.load, K_ATL);
    out.push({ date: d.date, load: d.load, ctl, atl, tsb });
  }
  return out;
}

/** ACWR rolling (precisa de >=28 dias de carga diária terminando hoje). */
export function acwr(dailyLoads: number[]): number {
  const acute = avg(dailyLoads.slice(-7));
  const chronic = avg(dailyLoads.slice(-28));
  return chronic > 0 ? acute / chronic : 0;
}

export function monotonyStrain(weekLoads: number[]): { monotony: number; strain: number } {
  const m = avg(weekLoads), sd = std(weekLoads);
  const monotony = sd > 0 ? m / sd : (m > 0 ? 2.5 : 0);
  return { monotony, strain: sum(weekLoads) * monotony };
}

