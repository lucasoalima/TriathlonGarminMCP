// GET /today  |  POST /today/context   (esqueleto)
// Busca do DB o estado de carga + wellness do usuário, chama computeToday, retorna a decisão.
// import { computeToday } from "../engine";
export const todayRoutes = {
  get: async (/* req, res */) => { /* TODO: carregar dados do DB e chamar computeToday */ },
  postContext: async (/* req, res */) => { /* TODO: ctx = req.body.contexto → recalcular */ },
};
