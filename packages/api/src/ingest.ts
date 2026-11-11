// Serviço de ingestão: fonte -> repositório -> recalcula LoadState.
// Chamado no webhook (pós-treino) e no backfill inicial (42 dias).
import { computeStates, sessionLoad } from "@copiloto/shared";
import type { DataSource, Athlete } from "@copiloto/shared";
import type { ActivityRepo } from "./activityRepo";

export async function ingest(userId: string, ds: DataSource, athlete: Athlete, repo: ActivityRepo, fromISO: string, toISO: string) {
  const acts = await ds.getActivities(fromISO, toISO);
  await repo.saveActivities(userId, acts.map((a) => ({ ...a, load: sessionLoad(athlete, a) })));
  const w = await ds.getWellness(toISO); if (w) await repo.saveWellness(userId, w);
  const states = computeStates(acts, athlete, fromISO, toISO);
  await repo.saveLoadStates(userId, states);
  return { activities: acts.length, days: states.length, latest: states[states.length - 1] };
}
