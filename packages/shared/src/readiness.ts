// Score de prontidão 0–100 + estado. Funciona COM ou SEM HRV (ex.: Garmin via Health Connect não expõe HRV).
import type { DailyWellness, Readiness, ReadinessState } from "./types";
import { clamp } from "./load";

export interface ReadinessInputs {
  w: DailyWellness;
  tsb: number; ctl: number; acwr: number; monotony: number;
  overreaching?: boolean;
}

function sleepSub(w: DailyWellness): number {
  if (w.sleepScore != null) return clamp(w.sleepScore, 0, 100);
  if (w.sleepHours != null) {
    let s = clamp(w.sleepHours / 8, 0, 1) * 100;
    if (w.sleepDeepMin != null && w.sleepRemMin != null && w.sleepHours > 0) {
      const frac = (w.sleepDeepMin + w.sleepRemMin) / (w.sleepHours * 60); // proxy de qualidade
      s += frac >= 0.35 ? 5 : frac < 0.20 ? -8 : 0;
    }
    return clamp(s, 0, 100);
  }
  return 70;
}
const tsbSub = (tsb: number, ctl: number): number => { const r = ctl > 0 ? tsb / ctl : 0; return r >= 0 ? 100 : r > -0.15 ? 85 : r > -0.30 ? 65 : r > -0.50 ? 45 : 25; };
const acwrSub = (a: number): number => (a >= 0.8 && a <= 1.3) ? 100 : (a > 1.3 && a <= 1.5) ? 70 : a > 1.5 ? 35 : 80;
const monoSub = (m: number): number => m < 1.5 ? 100 : m <= 2.0 ? 75 : 45;

export function readinessScore(inp: ReadinessInputs): Readiness {
  const { w, tsb, ctl, acwr, monotony } = inp;
  const flags: string[] = [];
  const hasHrv = w.hrvStatus != null || w.hrvWeekly != null;

  const ssleep = sleepSub(w);
  if (w.sleepScore != null && w.sleepScore < 55) flags.push("Sono abaixo do ideal");
  else if (w.sleepScore == null && (w.sleepHours ?? 8) < 6) flags.push("Sono curto");
  const stsb = tsbSub(tsb, ctl); if (ctl > 0 && tsb / ctl < -0.4) flags.push("Fadiga acumulada alta");
  const sacwr = acwrSub(acwr); if (acwr > 1.5) flags.push("Carga aguda muito alta (ACWR)");
  const smono = monoSub(monotony); if (monotony > 2.0) flags.push("Treino monótono");

  let score: number;
  if (hasHrv) {
    let hrvS = 100;
    if (w.hrvWeekly != null && w.hrvBaselineLow != null && w.hrvBaselineUpper != null) {
      const x = (w.hrvWeekly - w.hrvBaselineLow) / Math.max(1, w.hrvBaselineUpper - w.hrvBaselineLow);
      hrvS = clamp(x, 0, 1) * 100;
    }
    if (w.hrvStatus === "UNBALANCED") { hrvS = Math.min(hrvS, 50); flags.push("HRV desequilibrado"); }
    score = hrvS * 0.30 + ssleep * 0.25 + stsb * 0.20 + sacwr * 0.15 + smono * 0.10;
  } else {
    // Sem HRV (Health Connect): pesos recalibrados para sono + carga
    score = ssleep * 0.40 + stsb * 0.35 + sacwr * 0.15 + smono * 0.10;
    flags.push("Sem HRV nesta fonte — prontidão por sono + carga");
  }
  if (inp.overreaching) { score = Math.min(score, 45); flags.push("Overreaching"); }
  score = Math.round(clamp(score, 0, 100));
  const state: ReadinessState = score >= 75 ? "green" : score >= 60 ? "green-" : score >= 45 ? "amber" : "red";
  if (!flags.length) flags.push("Sem alertas hoje");
  return { date: w.date, score, state, flags };
}
