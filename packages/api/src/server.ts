// Esqueleto do servidor (trocar por Fastify/NestJS conforme escolha).
// Rotas do escopo: /auth, /consent, /connections, /profile, /plan, /today, /coach, /zones, /nutrition, /schedule, /webhooks/garmin/*
import { todayRoutes } from "./routes/today";
import { garminWebhooks } from "./routes/webhooks";
import { planRoutes } from "./routes/plan";

export function buildRoutes(app: any) {
  app.get("/today", todayRoutes.get);
  app.post("/today/context", todayRoutes.postContext);
  app.post("/plan/import", planRoutes.import);
  app.post("/plan", planRoutes.save);
  app.get("/plan", planRoutes.get);
  app.post("/webhooks/garmin/activity", garminWebhooks.activity);
  app.post("/webhooks/garmin/wellness", garminWebhooks.wellness);
  // TODO: auth, consent, connections (OAuth Garmin), profile, coach/ask, zones, nutrition, schedule
}
console.log("Copiloto API — esqueleto. Implementar auth, DB, integração Garmin e IA server-side.");
