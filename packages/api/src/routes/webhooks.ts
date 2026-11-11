// POST /webhooks/garmin/activity  |  /webhooks/garmin/wellness  (esqueleto)
// Garmin envia PING → responder 200 em segundos → processar assíncrono (fila).
export const garminWebhooks = {
  activity: async (/* req, res */) => {
    // 1) responder 200 imediatamente
    // 2) enfileirar: buscar callbackURL, gravar Activity (dedupe por garmin_activity_id),
    //    calcular sessionLoad, recomputar estado do dia, disparar push pós-treino.
  },
  wellness: async (/* req, res */) => {
    // idem: gravar sono/HRV/estresse do dia.
  },
};
