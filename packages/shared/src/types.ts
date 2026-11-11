// Tipos compartilhados do Copiloto do Corpo (framework-agnostic).
export type Sport = "Corrida" | "Bike" | "Natação" | "Força" | "Descanso" | "Outro";
export type Sex = "M" | "F";

export interface Athlete {
  sex: Sex;
  hrRest: number;   // FC repouso (Health API)
  hrMax: number;    // FCmáx real (máximo observado; atualiza continuamente)
  weightKg?: number;
}

export interface Activity {
  id: string;
  sport: Sport;
  date: string;          // YYYY-MM-DD
  durationMin: number;
  avgHr?: number;
  maxHr?: number;
  intensityFactor?: number; // IF (potência/pace vs limiar) se disponível → usa TSS
  manual?: boolean;
}

export interface DailyWellness {
  date: string;
  sleepScore?: number;   // 0–100
  sleepHours?: number;
  sleepDeepMin?: number;   // estágios (Health Connect)
  sleepRemMin?: number;
  hrvWeekly?: number;    // média 7d
  hrvStatus?: "BALANCED" | "UNBALANCED";
  hrvBaselineLow?: number;
  hrvBaselineUpper?: number;
}

export interface LoadPoint {
  date: string; load: number; ctl: number; atl: number; tsb: number;
}

export type ReadinessState = "green" | "green-" | "amber" | "red";
export interface Readiness { date: string; score: number; state: ReadinessState; flags: string[]; }

export interface PlannedSession { sport: Sport; type?: string; zone?: string; durationMin?: number; quality?: boolean; }
export type WeeklyPlan = Record<number, PlannedSession[]>; // 0=Dom .. 6=Sáb
export type AdjustContext = "dormiu" | "30min" | "pulou" | "dor" | null;
