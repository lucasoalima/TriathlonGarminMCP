// Camada de aplicação: usa o pacote shared para calcular o dia.
import { sessionLoad, computeLoadSeries, acwr, monotonyStrain, readinessScore, decideDay } from "@copiloto/shared";
import type { Athlete, Activity, DailyWellness, WeeklyPlan, AdjustContext } from "@copiloto/shared";

export function computeToday(params: {
  athlete: Athlete;
  dailyLoads28: number[];        // carga diária dos últimos 28 dias (para ACWR)
  weekLoads: number[];           // carga diária da semana (monotonia)
  ctlPrev: number; atlPrev: number; loadToday: number;
  wellness: DailyWellness;
  plan: WeeklyPlan; dow: number; doneToday: Activity[]; target: number; ctx: AdjustContext;
  overreaching?: boolean;
}) {
  const { athlete, dailyLoads28, weekLoads, ctlPrev, atlPrev, loadToday, wellness, plan, dow, doneToday, target, ctx } = params;
  const [{ ctl, atl, tsb }] = computeLoadSeries([{ date: wellness.date, load: loadToday }], ctlPrev, atlPrev);
  const ac = acwr([...dailyLoads28, loadToday]);
  const { monotony } = monotonyStrain(weekLoads);
  const readiness = readinessScore({ w: wellness, tsb, ctl, acwr: ac, monotony, overreaching: params.overreaching });
  const done = doneToday.map((a) => ({ sport: a.sport, name: a.id, durationMin: a.durationMin }));
  const decision = decideDay(plan, dow, done, readiness.state, target, ctx);
  return { load: { ctl, atl, tsb, acwr: ac, monotony }, readiness, decision };
}
