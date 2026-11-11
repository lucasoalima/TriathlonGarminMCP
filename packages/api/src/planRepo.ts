// Repositório de plano — abstrai a persistência (in-memory p/ dev, Prisma p/ produção).
import type { WeeklyPlan } from "@copiloto/shared";

export interface PlanRepo {
  savePlan(userId: string, plan: WeeklyPlan): Promise<void>;
  getActivePlan(userId: string): Promise<WeeklyPlan | null>;
}

export class InMemoryPlanRepo implements PlanRepo {
  private store = new Map<string, WeeklyPlan>();
  async savePlan(userId: string, plan: WeeklyPlan) { this.store.set(userId, plan); }
  async getActivePlan(userId: string) { return this.store.get(userId) ?? null; }
}

// Produção: mapeia WeeklyPlan <-> Plan/PlannedSession (Prisma). Stub — completar com o client.
export class PrismaPlanRepo implements PlanRepo {
  constructor(private prisma: any) {}
  async savePlan(userId: string, plan: WeeklyPlan) {
    // TODO: desativar plano anterior e criar Plan + PlannedSession[]:
    // await this.prisma.plan.updateMany({ where:{userId,active:true}, data:{active:false} });
    // const sessions = Object.entries(plan).flatMap(([dow,arr]) => arr.map((s,ordem)=>({ dow:Number(dow), ordem, sport:toEnum(s.sport), type:s.type, zone:s.zone, durationMin:s.durationMin, quality:!!s.quality })));
    // await this.prisma.plan.create({ data:{ userId, origin:"IMPORTADO", active:true, sessions:{ create: sessions } } });
  }
  async getActivePlan(userId: string): Promise<WeeklyPlan | null> {
    // TODO: const p = await this.prisma.plan.findFirst({ where:{userId,active:true}, include:{sessions:true} });
    // if(!p) return null; const wk:WeeklyPlan={}; for(const s of p.sessions){ (wk[s.dow] ??= []).push({sport:fromEnum(s.sport),type:s.type,zone:s.zone,durationMin:s.durationMin,quality:s.quality}); } return wk;
    return null;
  }
}
