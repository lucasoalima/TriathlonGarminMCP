/**
 * garmin-to-ctx.mjs — transforma métricas cruas/curadas do Garmin no CTX que o app consome.
 *
 * Este é o "backend transform" da fiação de dados reais: Garmin (curado) -> CTX -> app.
 * O app (mobile/www/index.html) carrega mobile/www/data/context.json e cai no CTX embutido
 * como fallback. No produto, o servidor (ou a ponte Health Connect) roda esta transformação
 * e publica o context.json por usuário.
 *
 * Entrada (GarminSnapshot): exatamente o shape das ferramentas do Garmin usadas:
 *   - hrv_trend        -> get_hrv_trend
 *   - sleep_summaries  -> get_sleep_summary (noite atual + 2 anteriores)
 *   - training_status  -> get_training_status
 *   - stats            -> get_stats
 *   - activities       -> get_activities
 *
 * Uso:
 *   node tools/garmin-to-ctx.mjs tools/sample-garmin-2026-08-01.json mobile/www/data/context.json
 *   node tools/garmin-to-ctx.mjs   # usa a amostra e escreve o context.json padrão
 */
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

const round = (n) => Math.round(n);
const fmtDur = (sec) => {
  const h = Math.floor(sec / 3600), m = Math.round((sec % 3600) / 60);
  return h > 0 ? `${h}h${String(m).padStart(2, '0')}` : `${m}min`;
};
const sportName = (t) => ({
  cycling: 'pedal', running: 'corrida', lap_swimming: 'natação',
  open_water_swimming: 'natação', strength_training: 'treino de força',
  walking: 'caminhada', hiking: 'trilha',
}[t] || 'treino');
const zoneTag = (name = '') => {
  const m = name.match(/\bZ([1-5])\b/i);
  return m ? ` em Z${m[1]}` : '';
};

export function toCTX(g, { name = 'Lucas' } = {}) {
  // ---- HRV: noite atual vs. baseline semanal ----
  const trend = g.hrv_trend?.trend || [];
  const hrvToday = trend[trend.length - 1] || {};
  const sleeps = g.sleep_summaries || [];
  const sToday = sleeps[0] || {};
  const hrvVal = round(sToday.avg_overnight_hrv ?? hrvToday.last_night_5min_high_hrv_ms ?? 0);
  const hrvBaseline = hrvToday.weekly_avg_hrv_ms || hrvVal || 1;
  const hrvDelta = round(((hrvVal - hrvBaseline) / hrvBaseline) * 100);
  const hrvBalanced = (hrvToday.status || '').toUpperCase() === 'BALANCED';

  // ---- Sono: última noite vs. média das noites disponíveis ----
  const nights = sleeps.map((s) => s.sleep_seconds).filter(Boolean);
  const avgNight = nights.length ? nights.reduce((a, b) => a + b, 0) / nights.length : (sToday.sleep_seconds || 0);
  const sleepDeltaMin = round(((sToday.sleep_seconds || 0) - avgNight) / 60);

  // ---- Carga: acute load + ACWR ----
  const ts = g.training_status || {};
  const acwr = (ts.acwr_status || '').toUpperCase();
  const loadHigh = acwr === 'HIGH' || acwr === 'VERY_HIGH';
  const loadStatus = acwr === 'VERY_HIGH' ? 'muito alta'
    : acwr === 'HIGH' ? 'alta'
    : acwr === 'LOW' ? 'baixa' : 'ok';

  // ---- Recuperação: body battery de pico, rebaixado pelo guardrail de carga ----
  const stats = g.stats || {};
  const recPct = round(stats.body_battery_highest ?? stats.body_battery_current ?? 0);
  const recStatus = loadHigh ? 'baixa' : recPct >= 75 ? 'boa' : recPct >= 55 ? 'média' : 'baixa';

  // ---- Último treino ----
  const acts = g.activities?.activities || g.activities || [];
  const a = acts[0] || {};
  const today = (g.stats?.date) || hrvToday.date;
  const actDay = (a.start_time || '').slice(0, 10);
  const when = actDay === today ? 'hoje' : 'ontem';
  const hard = /interval|z4|z5|tiro|forte|long[ãa]|prova|threshold|limiar/i.test(a.name || '')
    || (a.avg_hr_bpm || 0) >= 160;

  return {
    name,
    asOf: today,
    source: 'garmin',
    hrv: { val: String(hrvVal), unit: 'ms', delta: hrvDelta, balanced: hrvBalanced, baseline: hrvBaseline },
    sleep: { val: fmtDur(sToday.sleep_seconds || 0), deltaMin: sleepDeltaMin, score: sToday.sleep_score ?? null },
    load: { acute: round(ts.acute_load || 0), chronic: round(ts.chronic_load || 0), acwr: ts.load_ratio ?? null, status: loadStatus, high: loadHigh },
    recovery: { pct: recPct, status: recStatus },
    lastWorkout: {
      name: `${sportName(a.type)}${zoneTag(a.name)} de ${fmtDur(a.moving_duration_seconds || a.duration_seconds || 0)}`,
      when, sport: sportName(a.type), hard, broke: false, pr: false,
    },
  };
}

// ---- CLI ----
const [, , inPath = 'tools/sample-garmin-2026-08-01.json', outPath = 'mobile/www/data/context.json'] = process.argv;
const g = JSON.parse(readFileSync(inPath, 'utf8'));
const ctx = toCTX(g);
mkdirSync(dirname(outPath), { recursive: true });
writeFileSync(outPath, JSON.stringify(ctx, null, 2) + '\n');
console.log('CTX gerado a partir de', inPath, '->', outPath);
console.log(JSON.stringify(ctx, null, 2));
