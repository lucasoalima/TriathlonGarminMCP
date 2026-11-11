/**
 * Teste do transform Health Connect -> CTX (funções puras de health-connect.js),
 * usando o motor real (packages/shared/dist). Roda em Node, sem device.
 *   node tools/test-health-connect.mjs
 */
import { createRequire } from 'node:module';
import * as Engine from '../packages/shared/dist/index.js';
const require = createRequire(import.meta.url);

globalThis.CopilotoEngine = Engine;               // health-connect.js lê o motor daqui
const HC = require('../mobile/www/health-connect.js');

const iso = (d) => new Date(d).toISOString();
const now = new Date();
const dayMs = 864e5;
function atDay(daysAgo, hour, min = 0) { const d = new Date(now.getTime() - daysAgo * dayMs); d.setHours(hour, min, 0, 0); return d; }

// ---- monta um payload cru do Health Connect (10 dias) ----
const exercise = [], hr = [], sleep = [];
const plan = [ // [diasAtras, título, sport, min, avgHr, maxHr]
  [9, 'Corrida E1', 55, 148, 165], [8, 'Bike Z2 60', 62, 140, 172],
  [7, 'Natação piscina', 40, 150, 182], [6, 'Força', 39, 105, 138],
  [5, 'Corrida R', 47, 151, 166], [4, 'Bike HR Z3', 75, 152, 179],
  [3, 'RUN T 4x1 Z4 forte', 40, 156, 184], [2, 'Natação piscina', 45, 149, 188],
  [1, 'Corrida longa 21k', 105, 158, 176], [0, "Cotia PEDAL Z2 1H20", 80, 142, 169],
];
plan.forEach(([d, title, min, avg, max], i) => {
  const start = atDay(d, 18, 0), end = new Date(start.getTime() + min * 60000);
  const exType = /pedal|bike/i.test(title) ? 8 : /run|corrida/i.test(title) ? 56 : /nata/i.test(title) ? 74 : 80;
  exercise.push({ metadata: { id: 'e' + i }, type: 'ExerciseSession', startTime: iso(start), endTime: iso(end), title, exerciseType: exType });
  // série de FC cobrindo a sessão (amostras a cada 5 min, alternando avg/max)
  const samples = [];
  for (let t = +start; t <= +end; t += 5 * 60000) samples.push({ time: iso(t), beatsPerMinute: (samples.length % 3 === 0 ? max : avg) });
  hr.push({ metadata: { id: 'h' + i }, type: 'HeartRateSeries', startTime: iso(start), endTime: iso(end), samples });
});

// sono das últimas 8 noites (última noite curta de propósito)
const sleepPlan = [7.0, 8.5, 7.5, 7.2, 6.8, 7.6, 8.0, 7.9];
sleepPlan.forEach((h, i) => {
  const wake = atDay(i, 6, 30), start = new Date(wake.getTime() - h * 3600000);
  const stages = [
    { startTime: iso(start), endTime: iso(start.getTime() + h * 0.55 * 3600000), stage: 4 }, // light
    { startTime: iso(start.getTime() + h * 0.55 * 3600000), endTime: iso(start.getTime() + h * 0.78 * 3600000), stage: 5 }, // deep
    { startTime: iso(start.getTime() + h * 0.78 * 3600000), endTime: iso(wake), stage: 6 }, // rem
  ];
  sleep.push({ metadata: { id: 's' + i }, type: 'SleepSession', startTime: iso(start), endTime: iso(wake), title: 'Sono', stages });
});

const records = { exercise, hr, sleep, steps: [], spo2: [] };

// ---- roda o transform ----
const agg = HC.aggregate(records, { today: HC._ymd(now) });
const ctx = HC.buildCTXFrom(agg, { today: HC._ymd(now), name: 'Lucas' });

console.log('athlete:', agg.athlete);
console.log('atividades:', agg.activities.length, '| noites de sono:', Object.keys(agg.wellnessByDate).length);
console.log('\nCTX (Health Connect):');
console.log(JSON.stringify(ctx, null, 2));

// ---- asserts básicos ----
const fail = [];
if (ctx.hrv !== null) fail.push('hrv deveria ser null (HC sem HRV)');
if (ctx.source !== 'health-connect') fail.push('source errado');
if (!(ctx.load.acute > 0)) fail.push('carga aguda deveria ser > 0');
if (!(ctx.recovery.pct >= 0 && ctx.recovery.pct <= 100)) fail.push('recovery fora de 0-100');
if (!/\dh\d\d|\dmin/.test(ctx.sleep.val)) fail.push('sleep.val mal formatado: ' + ctx.sleep.val);
if (!ctx.lastWorkout.name) fail.push('lastWorkout vazio');
if (!Array.isArray(ctx.recovery.flags)) fail.push('flags ausentes');
console.log('\n' + (fail.length ? '❌ FALHAS:\n - ' + fail.join('\n - ') : '✅ Todos os asserts passaram'));
process.exit(fail.length ? 1 : 0);
