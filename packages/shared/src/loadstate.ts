// Deriva LoadState diário (CTL/ATL/TSB/ACWR/monotonia) a partir das atividades ingeridas.
import type { Activity, Athlete } from "./types";
import { sessionLoad, computeLoadSeries, acwr, monotonyStrain } from "./load";

export interface LoadStateRow { date: string; loadToday: number; ctl: number; atl: number; tsb: number; acwr: number; monotony: number; strain: number; }
const round1 = (n: number) => Math.round(n * 10) / 10;

export function computeStates(activities: Activity[], athlete: Athlete, fromISO: string, toISO: string): LoadStateRow[] {
  const byDay = new Map<string, number>();
  for (const a of activities) byDay.set(a.date, (byDay.get(a.date) || 0) + sessionLoad(athlete, a));
  const days: string[] = [];
  for (let d = new Date(fromISO + "T00:00:00Z"), end = new Date(toISO + "T00:00:00Z"); d <= end; d = new Date(d.getTime() + 864e5))
    days.push(d.toISOString().slice(0, 10));
  const series = days.map((date) => ({ date, load: byDay.get(date) || 0 }));
  const pts = computeLoadSeries(series, 0, 0);
  const daily = series.map((s) => s.load);
  return pts.map((p, i) => {
    const ac = acwr(daily.slice(0, i + 1));
    const { monotony, strain } = monotonyStrain(daily.slice(Math.max(0, i - 6), i + 1));
    return { date: p.date, loadToday: round1(p.load), ctl: round1(p.ctl), atl: round1(p.atl), tsb: round1(p.tsb), acwr: Math.round(ac * 100) / 100, monotony: Math.round(monotony * 100) / 100, strain: round1(strain) };
  });
}
