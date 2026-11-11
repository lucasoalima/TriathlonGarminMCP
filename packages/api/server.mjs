import http from "node:http";
import { sessionLoad, computeStates, readinessScore, decideDay, MockDataSource, parsePlan, validatePlan } from "../shared/dist/index.js";

const athlete = { sex: "M", hrRest: 68, hrMax: 188 };
const EXAMPLE_PLAN = {1:[{sport:"Força",zone:"—",durationMin:45},{sport:"Natação",zone:"Z2",durationMin:30}],2:[{sport:"Corrida",zone:"Z2",durationMin:45}],3:[{sport:"Bike",zone:"Z2",durationMin:75},{sport:"Natação",zone:"Z2",durationMin:30}],4:[{sport:"Corrida",zone:"Z3–limiar",durationMin:45,quality:true},{sport:"Força",zone:"—",durationMin:30}],5:[{sport:"Descanso",zone:"—",durationMin:20}],6:[{sport:"Bike",zone:"Z2",durationMin:120}],0:[{sport:"Corrida",zone:"Z2",durationMin:75}]};
const iso = (d) => d.toISOString().slice(0,10);
const USER = "demo"; const plans = new Map(); const CTXS = ["dormiu","30min","pulou","dor"];
const readBody = (req) => new Promise((r)=>{ let b=""; req.on("data",c=>b+=c); req.on("end",()=>r(b)); });
function applyCtx(state, ctx){ if(ctx==="dor")return"red"; if(ctx==="dormiu")return state==="green"?"amber":state==="green-"?"amber":"red"; return state; }

async function computeToday(ctx=null, doneOverride=null) {
  const ds = new MockDataSource();
  const today = new Date();
  const from = iso(new Date(today.getTime() - 41*864e5)), to = iso(today);
  const acts = await ds.getActivities(from, to);                 // ingestão
  const states = computeStates(acts, athlete, from, to);         // recomputa carga
  const last = states[states.length - 1];
  const todayActs = acts.filter(a => a.date === to);
  const w = await ds.getWellness(to);
  const over = last.acwr > 1.5 || (last.ctl > 0 && last.tsb/last.ctl < -0.5);
  const readiness = readinessScore({ w, tsb: last.tsb, ctl: last.ctl, acwr: last.acwr, monotony: last.monotony, overreaching: over });
  const state = applyCtx(readiness.state, ctx);
  const plan = plans.get(USER) || EXAMPLE_PLAN;
  const done = doneOverride ?? todayActs.map(a => ({ sport:a.sport, name:a.id, durationMin:a.durationMin }));
  const decision = decideDay(plan, today.getDay(), done, state, 2, ctx);
  return { date: to, plano_fonte: plans.has(USER)?"importado":"exemplo", contexto: ctx,
    ingestao: { atividades: acts.length, dias: states.length },
    prontidao_base: readiness.state, prontidao_ajustada: state, readiness,
    load: last, treinos_hoje: done, decisao: decision };
}

const J = { "content-type":"application/json; charset=utf-8", "access-control-allow-origin":"*" };
const server = http.createServer(async (req,res)=>{
  try {
    if (req.method==="POST" && (req.url||"").startsWith("/plan/import")) {
      const raw = await readBody(req); let text = raw; try { const j=JSON.parse(raw); if(j&&typeof j.text==="string") text=j.text; } catch {}
      const r = await parsePlan(text); const v = validatePlan(r.plan); if (v.ok) plans.set(USER, r.plan);
      res.writeHead(v.ok?200:400, J); res.end(JSON.stringify({ok:v.ok,source:r.source,warnings:r.warnings,errors:v.errors,plan:r.plan},null,2)); return;
    }
    if (req.method==="POST" && (req.url||"").startsWith("/today/context")) {
      const raw = await readBody(req); let b={}; try{ b=JSON.parse(raw||"{}"); }catch{}
      if (!CTXS.includes(b.contexto)) { res.writeHead(400,J); res.end(JSON.stringify({error:"contexto inválido",validos:CTXS})); return; }
      const data = await computeToday(b.contexto, b.simVazio?[]:null); res.writeHead(200,J); res.end(JSON.stringify(data,null,2)); return;
    }
    if ((req.url||"").startsWith("/today")) { const d=await computeToday(null); res.writeHead(200,J); res.end(JSON.stringify(d,null,2)); return; }
    res.writeHead(200,{"content-type":"text/plain; charset=utf-8"}); res.end("Copiloto demo. GET /today | POST /plan/import | POST /today/context");
  } catch(e){ res.writeHead(500); res.end(String(e&&e.stack||e)); }
});
server.listen(process.env.PORT||8787, ()=>console.log("Copiloto demo em http://localhost:"+(process.env.PORT||8787)));
