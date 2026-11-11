import { parsePlan, validatePlan } from "./dist/index.js";
const texto = `Plano semana - Assessoria (triatlo)
Seg: Força 45min (core+pernas) + Natação técnica 1000m
Ter: Corrida 40min Z2 leve
Qua: Bike Z2 1h + Natação 1200m
Qui: Corrida forte 8x400m (rec 1') / à noite Força 30min
Sex: Descanso
Sáb: Bike longo 2h Z2
Dom: Corrida longa 14km Z2`;
const r = await parsePlan(texto);      // sem LLM → heurístico
console.log("fonte:", r.source);
console.log("válido:", validatePlan(r.plan).ok);
console.log("plano:", JSON.stringify(r.plan, null, 1));
console.log("avisos:", r.warnings);
