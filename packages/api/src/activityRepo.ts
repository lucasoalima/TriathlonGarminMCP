// Repositório de atividades/wellness/estado de carga (in-memory p/ dev, Prisma p/ produção).
import type { Activity, LoadStateRow, DailyWellness } from "@copiloto/shared";

export interface ActivityRepo {
  saveActivities(userId: string, activities: (Activity & { load?: number })[]): Promise<void>;
  getActivities(userId: string, from: string, to: string): Promise<Activity[]>;
  saveWellness(userId: string, w: DailyWellness): Promise<void>;
  getWellness(userId: string, date: string): Promise<DailyWellness | null>;
  saveLoadStates(userId: string, states: LoadStateRow[]): Promise<void>;
  getLoadState(userId: string, date: string): Promise<LoadStateRow | null>;
}

export class InMemoryActivityRepo implements ActivityRepo {
  private acts = new Map<string, Map<string, Activity & { load?: number }>>();
  private wel = new Map<string, Map<string, DailyWellness>>();
  private st = new Map<string, Map<string, LoadStateRow>>();
  private bag<T>(m: Map<string, Map<string, T>>, u: string) { let x = m.get(u); if (!x) { x = new Map(); m.set(u, x); } return x; }
  async saveActivities(u: string, a: (Activity & { load?: number })[]) { const b = this.bag(this.acts, u); for (const x of a) b.set(x.id, x); }
  async getActivities(u: string, from: string, to: string) { return [...this.bag(this.acts, u).values()].filter((a) => a.date >= from && a.date <= to); }
  async saveWellness(u: string, w: DailyWellness) { this.bag(this.wel, u).set(w.date, w); }
  async getWellness(u: string, date: string) { return this.bag(this.wel, u).get(date) ?? null; }
  async saveLoadStates(u: string, s: LoadStateRow[]) { const b = this.bag(this.st, u); for (const x of s) b.set(x.date, x); }
  async getLoadState(u: string, date: string) { return this.bag(this.st, u).get(date) ?? null; }
}

// Produção — completar com o client Prisma (upserts idempotentes por chave única).
export class PrismaActivityRepo implements ActivityRepo {
  constructor(private prisma: any) {}
  async saveActivities(userId: string, a: (Activity & { load?: number })[]) { /* TODO upsert por (userId, externalId) */ }
  async getActivities(userId: string, from: string, to: string): Promise<Activity[]> { return []; }
  async saveWellness(userId: string, w: DailyWellness) { /* TODO upsert por (userId, date) */ }
  async getWellness(userId: string, date: string) { return null; }
  async saveLoadStates(userId: string, s: LoadStateRow[]) { /* TODO upsert por (userId, date) */ }
  async getLoadState(userId: string, date: string) { return null; }
}
