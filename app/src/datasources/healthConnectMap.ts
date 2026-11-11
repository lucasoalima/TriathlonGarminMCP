// Mapeamento PURO: registros do Health Connect -> tipos do motor (@copiloto/shared).
// Sem dependência do plugin (testável isoladamente). A leitura no device fica em healthConnect.ts.
import type { Activity, DailyWellness, Sport } from "@copiloto/shared";

export interface HCExerciseSession { startTime: string; endTime: string; exerciseType: string; title?: string; metadata?: { id?: string }; }
export interface HCHeartRateSample { time: string; beatsPerMinute: number; }
export interface HCSleepStage { stage: string; startTime: string; endTime: string; } // "deep" | "rem" | "light" | "awake"
export interface HCSleepSession { startTime: string; endTime: string; stages?: HCSleepStage[]; }

const minutesBetween = (a: string, b: string) => Math.max(0, Math.round((new Date(b).getTime() - new Date(a).getTime()) / 60000));

/** ExerciseType do Health Connect -> nosso Sport. (Garmin escreve tipos como RUNNING, BIKING, SWIMMING_*, STRENGTH_TRAINING.) */
export function mapExerciseType(t: string): Sport {
  const s = (t || "").toUpperCase();
  if (s.includes("RUN") || s.includes("WALK")) return "Corrida";
  if (s.includes("BIK") || s.includes("CYCL")) return "Bike";
  if (s.includes("SWIM")) return "Natação";
  if (s.includes("STRENGTH") || s.includes("WEIGHT")) return "Força";
  return "Outro";
}

/** Combina sessões de exercício com as amostras de FC da janela -> Activity[]. */
export function activitiesFromHC(sessions: HCExerciseSession[], hr: HCHeartRateSample[]): Activity[] {
  return sessions.map((se, i) => {
    const start = new Date(se.startTime).getTime(), end = new Date(se.endTime).getTime();
    const inWin = hr.filter((h) => { const t = new Date(h.time).getTime(); return t >= start && t <= end; }).map((h) => h.beatsPerMinute);
    const avgHr = inWin.length ? Math.round(inWin.reduce((s, x) => s + x, 0) / inWin.length) : undefined;
    const maxHr = inWin.length ? Math.max(...inWin) : undefined;
    const act: Activity = {
      id: se.metadata?.id || `hc-${se.startTime}-${i}`,
      sport: mapExerciseType(se.exerciseType),
      date: se.startTime.slice(0, 10),
      durationMin: minutesBetween(se.startTime, se.endTime),
    };
    if (avgHr != null) act.avgHr = avgHr;
    if (maxHr != null) act.maxHr = maxHr;
    return act;
  });
}

/** Sessão de sono do Health Connect -> DailyWellness (sem HRV; Garmin não expõe HRV ao HC). */
export function wellnessFromHC(date: string, sleep?: HCSleepSession): DailyWellness {
  const w: DailyWellness = { date };
  if (sleep) {
    w.sleepHours = minutesBetween(sleep.startTime, sleep.endTime) / 60;
    const byStage = (name: string) => (sleep.stages || []).filter((s) => s.stage.toLowerCase().includes(name)).reduce((sum, s) => sum + minutesBetween(s.startTime, s.endTime), 0);
    const deep = byStage("deep"), rem = byStage("rem");
    if (deep > 0) w.sleepDeepMin = deep;
    if (rem > 0) w.sleepRemMin = rem;
  }
  return w; // hrv/sleepScore ficam undefined (Health Connect não traz)
}
