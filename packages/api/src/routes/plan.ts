// POST /plan/import (LLM parser) | POST /plan | GET /plan | POST /plan/generate (esqueleto)
export const planRoutes = {
  import: async (/* req */) => { /* TODO: chamar LLM (server) → JSON do plano p/ revisão */ },
  save: async (/* req */) => { /* TODO: salvar WeeklyPlan no DB */ },
  get: async (/* req */) => { /* TODO */ },
  generate: async (/* req */) => { /* TODO: plano de base a partir do perfil */ },
};
