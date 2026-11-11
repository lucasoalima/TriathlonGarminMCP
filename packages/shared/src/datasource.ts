// Abstração de fonte de dados: o motor não sabe de onde vem (Health Connect, agregador, mock).
import type { Activity, DailyWellness } from "./types";

export interface SourceCapabilities { hrv: boolean; sleepScore: boolean; stress: boolean; bodyBattery: boolean; }

export interface DataSource {
  readonly name: string;
  readonly capabilities: SourceCapabilities;
  getActivities(from: string, to: string): Promise<Activity[]>;
  getWellness(date: string): Promise<DailyWellness | null>;
}

// Capacidades por fonte (o que cada uma entrega)
export const CAP_HEALTH_CONNECT: SourceCapabilities = { hrv: false, sleepScore: false, stress: false, bodyBattery: false };
export const CAP_AGGREGATOR: SourceCapabilities   = { hrv: true,  sleepScore: false, stress: true,  bodyBattery: true };
export const CAP_GARMIN_DIRECT: SourceCapabilities = { hrv: true,  sleepScore: false, stress: true,  bodyBattery: true };

// Mapeamento Health Connect (Garmin via HC) — o que ler no dispositivo (Capacitor/nativo):
export const HEALTH_CONNECT_MAP = {
  activities: "ExerciseSessionRecord (+ HeartRateRecord para FC média/máx)",
  sleep: "SleepSessionRecord (duração + estágios deep/rem/light)",
  heartRate: "HeartRateRecord",
  spo2: "OxygenSaturationRecord",
  steps: "StepsRecord",
  hrv: "AUSENTE para Garmin — não sincroniza; hrvStatus/hrvWeekly ficam undefined",
} as const;

// Fonte simulada (dev/testes) — imita Health Connect (sem HRV).
export class MockDataSource implements DataSource {
  readonly name = "mock-health-connect";
  readonly capabilities = CAP_HEALTH_CONNECT;
  async getActivities(from: string, to: string): Promise<Activity[]> {
    const out: Activity[] = []; let id = 0;
    const mk = (date: string, sport: Activity["sport"], min: number, avg: number, max: number): Activity => ({ id: "m" + id++, sport, date, durationMin: min, avgHr: avg, maxHr: max });
    const start = new Date(from + "T00:00:00Z"), end = new Date(to + "T00:00:00Z");
    for (let d = new Date(start); d <= end; d = new Date(d.getTime() + 864e5)) {
      const date = d.toISOString().slice(0, 10), dow = d.getUTCDay();
      const hard = Math.round((end.getTime() - d.getTime()) / 864e5) <= 5; // última semana mais pesada
      if (dow === 5) continue;                                   // sexta = descanso
      if (dow === 1) { out.push(mk(date, "Força", 39, 101, 138)); out.push(mk(date, "Natação", 30, 128, 150)); }
      else if (dow === 3) { out.push(mk(date, "Bike", hard ? 75 : 60, 143, 178)); if (hard) out.push(mk(date, "Força", 30, 100, 135)); }
      else if (dow === 6) { out.push(mk(date, "Bike", 120, 140, 170)); }
      else if (dow === 0) { out.push(mk(date, "Corrida", 75, 145, 165)); }
      else { out.push(mk(date, "Corrida", hard ? 55 : 45, hard ? 154 : 140, hard ? 168 : 156)); }
    }
    return out;
  }
  async getWellness(date: string): Promise<DailyWellness> {
    return { date, sleepHours: 6.5, sleepDeepMin: 52, sleepRemMin: 6 };
  }
}
