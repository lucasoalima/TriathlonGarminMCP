"use strict";
var CopilotoEngine = (() => {
  var __defProp = Object.defineProperty;
  var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
  var __getOwnPropNames = Object.getOwnPropertyNames;
  var __hasOwnProp = Object.prototype.hasOwnProperty;
  var __export = (target, all) => {
    for (var name in all)
      __defProp(target, name, { get: all[name], enumerable: true });
  };
  var __copyProps = (to, from, except, desc) => {
    if (from && typeof from === "object" || typeof from === "function") {
      for (let key of __getOwnPropNames(from))
        if (!__hasOwnProp.call(to, key) && key !== except)
          __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
    }
    return to;
  };
  var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

  // packages/shared/dist/index.js
  var index_exports = {};
  __export(index_exports, {
    CAP_AGGREGATOR: () => CAP_AGGREGATOR,
    CAP_GARMIN_DIRECT: () => CAP_GARMIN_DIRECT,
    CAP_HEALTH_CONNECT: () => CAP_HEALTH_CONNECT,
    HEALTH_CONNECT_MAP: () => HEALTH_CONNECT_MAP,
    K_ATL: () => K_ATL,
    K_CTL: () => K_CTL,
    MockDataSource: () => MockDataSource,
    TAU_ATL: () => TAU_ATL,
    TAU_CTL: () => TAU_CTL,
    acwr: () => acwr,
    clamp: () => clamp,
    computeLoadSeries: () => computeLoadSeries,
    computeStates: () => computeStates,
    decideDay: () => decideDay,
    ewmaUpdate: () => ewmaUpdate,
    monotonyStrain: () => monotonyStrain,
    parsePlan: () => parsePlan,
    parsePlanText: () => parsePlanText,
    readinessScore: () => readinessScore,
    sessionLoad: () => sessionLoad,
    trimp: () => trimp,
    tssFromIF: () => tssFromIF,
    validatePlan: () => validatePlan
  });

  // packages/shared/dist/load.js
  var TAU_CTL = 42;
  var TAU_ATL = 7;
  var K_CTL = 1 - Math.exp(-1 / TAU_CTL);
  var K_ATL = 1 - Math.exp(-1 / TAU_ATL);
  function clamp(x, a, b) {
    return Math.max(a, Math.min(b, x));
  }
  function avg(a) {
    return a.length ? a.reduce((s, x) => s + x, 0) / a.length : 0;
  }
  function sum(a) {
    return a.reduce((s, x) => s + x, 0);
  }
  function std(a) {
    const m = avg(a);
    return Math.sqrt(avg(a.map((x) => (x - m) ** 2)));
  }
  function trimp(a, durationMin, avgHr) {
    const hrr = clamp((avgHr - a.hrRest) / (a.hrMax - a.hrRest), 0, 1);
    const Y = a.sex === "F" ? 0.86 * Math.exp(1.67 * hrr) : 0.64 * Math.exp(1.92 * hrr);
    return durationMin * hrr * Y;
  }
  function tssFromIF(durationMin, IF) {
    return IF * IF * (durationMin / 60) * 100;
  }
  function sessionLoad(a, act, calFactor = 1) {
    if (act.intensityFactor && act.intensityFactor > 0)
      return tssFromIF(act.durationMin, act.intensityFactor);
    if (act.avgHr && a.hrMax > a.hrRest)
      return trimp(a, act.durationMin, act.avgHr) * calFactor;
    const factor = act.sport === "For\xE7a" ? 0.6 : act.sport === "Descanso" ? 0 : 0.7;
    return act.durationMin * factor;
  }
  function ewmaUpdate(prev, today, k) {
    return prev * (1 - k) + today * k;
  }
  function computeLoadSeries(series, seedCtl = 0, seedAtl = 0) {
    let ctl = seedCtl, atl = seedAtl;
    const out = [];
    for (const d of series) {
      const tsb = ctl - atl;
      ctl = ewmaUpdate(ctl, d.load, K_CTL);
      atl = ewmaUpdate(atl, d.load, K_ATL);
      out.push({ date: d.date, load: d.load, ctl, atl, tsb });
    }
    return out;
  }
  function acwr(dailyLoads) {
    const acute = avg(dailyLoads.slice(-7));
    const chronic = avg(dailyLoads.slice(-28));
    return chronic > 0 ? acute / chronic : 0;
  }
  function monotonyStrain(weekLoads) {
    const m = avg(weekLoads), sd = std(weekLoads);
    const monotony = sd > 0 ? m / sd : m > 0 ? 2.5 : 0;
    return { monotony, strain: sum(weekLoads) * monotony };
  }

  // packages/shared/dist/readiness.js
  function sleepSub(w) {
    if (w.sleepScore != null)
      return clamp(w.sleepScore, 0, 100);
    if (w.sleepHours != null) {
      let s = clamp(w.sleepHours / 8, 0, 1) * 100;
      if (w.sleepDeepMin != null && w.sleepRemMin != null && w.sleepHours > 0) {
        const frac = (w.sleepDeepMin + w.sleepRemMin) / (w.sleepHours * 60);
        s += frac >= 0.35 ? 5 : frac < 0.2 ? -8 : 0;
      }
      return clamp(s, 0, 100);
    }
    return 70;
  }
  var tsbSub = (tsb, ctl) => {
    const r = ctl > 0 ? tsb / ctl : 0;
    return r >= 0 ? 100 : r > -0.15 ? 85 : r > -0.3 ? 65 : r > -0.5 ? 45 : 25;
  };
  var acwrSub = (a) => a >= 0.8 && a <= 1.3 ? 100 : a > 1.3 && a <= 1.5 ? 70 : a > 1.5 ? 35 : 80;
  var monoSub = (m) => m < 1.5 ? 100 : m <= 2 ? 75 : 45;
  function readinessScore(inp) {
    const { w, tsb, ctl, acwr: acwr2, monotony } = inp;
    const flags = [];
    const hasHrv = w.hrvStatus != null || w.hrvWeekly != null;
    const ssleep = sleepSub(w);
    if (w.sleepScore != null && w.sleepScore < 55)
      flags.push("Sono abaixo do ideal");
    else if (w.sleepScore == null && (w.sleepHours ?? 8) < 6)
      flags.push("Sono curto");
    const stsb = tsbSub(tsb, ctl);
    if (ctl > 0 && tsb / ctl < -0.4)
      flags.push("Fadiga acumulada alta");
    const sacwr = acwrSub(acwr2);
    if (acwr2 > 1.5)
      flags.push("Carga aguda muito alta (ACWR)");
    const smono = monoSub(monotony);
    if (monotony > 2)
      flags.push("Treino mon\xF3tono");
    let score;
    if (hasHrv) {
      let hrvS = 100;
      if (w.hrvWeekly != null && w.hrvBaselineLow != null && w.hrvBaselineUpper != null) {
        const x = (w.hrvWeekly - w.hrvBaselineLow) / Math.max(1, w.hrvBaselineUpper - w.hrvBaselineLow);
        hrvS = clamp(x, 0, 1) * 100;
      }
      if (w.hrvStatus === "UNBALANCED") {
        hrvS = Math.min(hrvS, 50);
        flags.push("HRV desequilibrado");
      }
      score = hrvS * 0.3 + ssleep * 0.25 + stsb * 0.2 + sacwr * 0.15 + smono * 0.1;
    } else {
      score = ssleep * 0.4 + stsb * 0.35 + sacwr * 0.15 + smono * 0.1;
      flags.push("Sem HRV nesta fonte \u2014 prontid\xE3o por sono + carga");
    }
    if (inp.overreaching) {
      score = Math.min(score, 45);
      flags.push("Overreaching");
    }
    score = Math.round(clamp(score, 0, 100));
    const state = score >= 75 ? "green" : score >= 60 ? "green-" : score >= 45 ? "amber" : "red";
    if (!flags.length)
      flags.push("Sem alertas hoje");
    return { date: w.date, score, state, flags };
  }

  // packages/shared/dist/decision.js
  function decideDay(plan, dow, done, state, target, ctx = null) {
    const today = plan[dow] || [];
    const rest = today.length === 1 && today[0].sport === "Descanso";
    const doneSports = done.map((d) => d.sport);
    const remaining = today.filter((s) => s.sport !== "Descanso" && !doneSports.includes(s.sport));
    const dc = done.length;
    let headline;
    if (ctx === "dor")
      headline = "Dor \xE9 sinal de parar \u2014 hoje sem impacto. Descanso ou mobilidade leve; se durar 3\u20134 dias, procure fisio/m\xE9dico.";
    else if (dc >= Math.max(2, target))
      headline = `Voc\xEA j\xE1 fez ${dc} treinos hoje. Dia cumprido \u2014 foco em recuperar.`;
    else if (dc >= 1)
      headline = dc >= target ? "Voc\xEA j\xE1 treinou hoje e bateu suas sess\xF5es \u2014 sem treino extra por conta pr\xF3pria." : `Voc\xEA j\xE1 treinou hoje. ${state === "green" ? "Se houver 2\xAA sess\xE3o prevista, pode seguir." : "Se houver 2\xAA sess\xE3o, fa\xE7a-a mais leve; sen\xE3o, recupere."}`;
    else if (rest)
      headline = "Hoje \xE9 dia leve/descanso. Aproveite para recuperar.";
    else
      headline = state === "red" ? "Hoje o corpo pede cautela \u2014 leve (Z1\u2013Z2) ou descanso." : state === "amber" ? "D\xE1 para treinar com o p\xE9 no freio (reduza volume/intensidade)." : "Prontid\xE3o boa: pode seguir sua sess\xE3o, come\xE7ando leve.";
    const sessions = today.map((s) => {
      if (doneSports.includes(s.sport))
        return { planned: { ...s }, status: "done" };
      let planned = { ...s };
      if (ctx === "30min" && remaining[0] === s)
        planned.durationMin = 30;
      if (state === "red")
        planned = { ...planned, zone: "Z1\u2013Z2", durationMin: Math.min(30, planned.durationMin ?? 30) };
      else if (state === "amber" && planned.durationMin)
        planned.durationMin = Math.round(planned.durationMin * 0.7);
      const status = ctx || state !== "green" ? "modulated" : "suggested";
      return { planned, status };
    });
    const weekNote = ctx === "pulou" ? "Preservo os treinos-chave (longo + qualidade) e absorvo a falta nos f\xE1ceis; sem dobrar amanh\xE3." : void 0;
    return { headline, sessions, weekNote };
  }

  // packages/shared/dist/datasource.js
  var CAP_HEALTH_CONNECT = { hrv: false, sleepScore: false, stress: false, bodyBattery: false };
  var CAP_AGGREGATOR = { hrv: true, sleepScore: false, stress: true, bodyBattery: true };
  var CAP_GARMIN_DIRECT = { hrv: true, sleepScore: false, stress: true, bodyBattery: true };
  var HEALTH_CONNECT_MAP = {
    activities: "ExerciseSessionRecord (+ HeartRateRecord para FC m\xE9dia/m\xE1x)",
    sleep: "SleepSessionRecord (dura\xE7\xE3o + est\xE1gios deep/rem/light)",
    heartRate: "HeartRateRecord",
    spo2: "OxygenSaturationRecord",
    steps: "StepsRecord",
    hrv: "AUSENTE para Garmin \u2014 n\xE3o sincroniza; hrvStatus/hrvWeekly ficam undefined"
  };
  var MockDataSource = class {
    name = "mock-health-connect";
    capabilities = CAP_HEALTH_CONNECT;
    async getActivities(from, to) {
      const out = [];
      let id = 0;
      const mk = (date, sport, min, avg2, max) => ({ id: "m" + id++, sport, date, durationMin: min, avgHr: avg2, maxHr: max });
      const start = /* @__PURE__ */ new Date(from + "T00:00:00Z"), end = /* @__PURE__ */ new Date(to + "T00:00:00Z");
      for (let d = new Date(start); d <= end; d = new Date(d.getTime() + 864e5)) {
        const date = d.toISOString().slice(0, 10), dow = d.getUTCDay();
        const hard = Math.round((end.getTime() - d.getTime()) / 864e5) <= 5;
        if (dow === 5)
          continue;
        if (dow === 1) {
          out.push(mk(date, "For\xE7a", 39, 101, 138));
          out.push(mk(date, "Nata\xE7\xE3o", 30, 128, 150));
        } else if (dow === 3) {
          out.push(mk(date, "Bike", hard ? 75 : 60, 143, 178));
          if (hard)
            out.push(mk(date, "For\xE7a", 30, 100, 135));
        } else if (dow === 6) {
          out.push(mk(date, "Bike", 120, 140, 170));
        } else if (dow === 0) {
          out.push(mk(date, "Corrida", 75, 145, 165));
        } else {
          out.push(mk(date, "Corrida", hard ? 55 : 45, hard ? 154 : 140, hard ? 168 : 156));
        }
      }
      return out;
    }
    async getWellness(date) {
      return { date, sleepHours: 6.5, sleepDeepMin: 52, sleepRemMin: 6 };
    }
  };

  // packages/shared/dist/planparser.js
  var DOW_MAP = {
    dom: 0,
    domingo: 0,
    seg: 1,
    segunda: 1,
    ter: 2,
    terca: 2,
    "ter\xE7a": 2,
    qua: 3,
    quarta: 3,
    qui: 4,
    quinta: 4,
    sex: 5,
    sexta: 5,
    sab: 6,
    "s\xE1b": 6,
    sabado: 6,
    "s\xE1bado": 6
  };
  var DAY_LABEL = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "S\xE1b"];
  function detectSport(s) {
    const t = s.toLowerCase();
    if (/(corr|\brun\b|trote|rodage|maratona|\d+\s*k\b)/.test(t))
      return "Corrida";
    if (/(bike|pedal|ciclis|bicicle|rolo|cycl)/.test(t))
      return "Bike";
    if (/(nata|nado|swim|piscina|crawl)/.test(t))
      return "Nata\xE7\xE3o";
    if (/(for[çc]a|muscula|academia|\bcore\b|strength|\bgym\b)/.test(t))
      return "For\xE7a";
    if (/(descanso|folga|\brest\b|\boff\b)/.test(t))
      return "Descanso";
    return "Outro";
  }
  function parseDuration(s) {
    let min = 0;
    const h = s.match(/(\d+(?:[.,]\d+)?)\s*h\b/i);
    if (h)
      min += Math.round(parseFloat(h[1].replace(",", ".")) * 60);
    const mm = s.match(/(\d+)\s*(?:min|minutos)\b/i);
    if (mm)
      min += parseInt(mm[1], 10);
    for (const a of s.matchAll(/(\d+)\s*'/g)) {
      const idx = a.index ?? 0;
      const before = s.slice(Math.max(0, idx - 8), idx).toLowerCase();
      const val = parseInt(a[1], 10);
      if (val >= 5 && !/(rec|rest|desc|pausa)/.test(before))
        min += val;
    }
    return min > 0 ? min : null;
  }
  function detectZone(s) {
    const t = s.toLowerCase();
    const quality = /(forte|tiros|intervalad|limiar|tempo|\d+\s*x\s*\d+)/.test(t);
    const z = t.match(/z\s*([1-5])/);
    if (z)
      return { zone: "Z" + z[1], quality };
    if (/(limiar|tempo|forte)/.test(t))
      return { zone: "Z3\u2013limiar", quality: true };
    if (/(leve|f[aá]cil|regenerativ|\bbase\b)/.test(t))
      return { zone: "Z2", quality };
    return { zone: void 0, quality };
  }
  function splitSessions(body) {
    const out = [];
    let buf = "";
    let depth = 0;
    for (const ch of body) {
      if (ch === "(")
        depth++;
      else if (ch === ")")
        depth = Math.max(0, depth - 1);
      if (depth === 0 && (ch === "+" || ch === "/" || ch === ";")) {
        if (buf.trim())
          out.push(buf.trim());
        buf = "";
        continue;
      }
      buf += ch;
    }
    if (buf.trim())
      out.push(buf.trim());
    return out;
  }
  function parsePlanText(text) {
    const plan = {};
    const warnings = [];
    for (const raw of text.split(/\r?\n/)) {
      const line = raw.trim();
      if (!line)
        continue;
      const dm = line.match(/^\s*([A-Za-zçáéíóúâãêô]+)\.?\s*[:\-–]\s*(.+)$/);
      if (!dm) {
        if (!/plano|semana|assessoria|bloco/i.test(line))
          warnings.push("linha ignorada: " + line);
        continue;
      }
      const dow = DOW_MAP[dm[1].toLowerCase()];
      if (dow === void 0) {
        warnings.push("dia n\xE3o reconhecido: " + dm[1]);
        continue;
      }
      const sessions = splitSessions(dm[2]).map((c) => {
        const sport = detectSport(c);
        const { zone, quality } = detectZone(c);
        const durationMin = parseDuration(c);
        const sess = { sport, type: c };
        if (zone)
          sess.zone = zone;
        if (durationMin != null)
          sess.durationMin = durationMin;
        if (quality)
          sess.quality = true;
        if (durationMin == null && sport !== "Descanso")
          warnings.push(`sem dura\xE7\xE3o expl\xEDcita em "${c}" (${DAY_LABEL[dow]}) \u2014 estimar do hist\xF3rico/pace`);
        return sess;
      });
      plan[dow] = (plan[dow] || []).concat(sessions);
    }
    return { plan, warnings };
  }
  var LLM_SYS = 'Voc\xEA \xE9 um parser de planos de treino de assessorias. Responda SOMENTE com JSON: {"dias":[{"dia":"Seg","sessoes":[{"esporte":"Corrida|Bike|Nata\xE7\xE3o|For\xE7a|Descanso|Outro","zona":"","duracao_min":numero_ou_null,"tipo":""}]}]}. N\xE3o invente treinos que n\xE3o est\xE3o no texto.';
  function normSport(s) {
    const t = (s || "").toLowerCase();
    if (t.startsWith("corr"))
      return "Corrida";
    if (t.startsWith("bik"))
      return "Bike";
    if (t.startsWith("nat"))
      return "Nata\xE7\xE3o";
    if (t.startsWith("for"))
      return "For\xE7a";
    if (t.startsWith("desc"))
      return "Descanso";
    return "Outro";
  }
  function fromDiasJson(parsed) {
    const map = { dom: 0, seg: 1, ter: 2, qua: 3, qui: 4, sex: 5, "s\xE1b": 6, sab: 6 };
    const plan = {};
    for (const d of parsed?.dias || []) {
      const dow = map[(d.dia || "").toLowerCase()];
      if (dow === void 0)
        continue;
      plan[dow] = (d.sessoes || []).map((s) => {
        const sess = { sport: normSport(s.esporte) };
        if (s.zona)
          sess.zone = s.zona;
        if (typeof s.duracao_min === "number")
          sess.durationMin = s.duracao_min;
        if (s.tipo)
          sess.type = s.tipo;
        if (/forte|limiar|tempo|tiros/i.test((s.tipo || "") + (s.zona || "")))
          sess.quality = true;
        return sess;
      });
    }
    return plan;
  }
  async function parsePlan(text, llm) {
    if (llm) {
      try {
        const raw = await llm.complete(LLM_SYS, text);
        const j = raw.slice(raw.indexOf("{"), raw.lastIndexOf("}") + 1);
        const plan = fromDiasJson(JSON.parse(j));
        if (validatePlan(plan).ok && Object.keys(plan).length)
          return { plan, warnings: [], source: "llm" };
      } catch {
      }
    }
    return { ...parsePlanText(text), source: "heuristic" };
  }
  function validatePlan(plan) {
    const errors = [];
    const sports = ["Corrida", "Bike", "Nata\xE7\xE3o", "For\xE7a", "Descanso", "Outro"];
    for (const k of Object.keys(plan)) {
      const dow = Number(k);
      if (!(dow >= 0 && dow <= 6))
        errors.push("dow inv\xE1lido: " + k);
      for (const s of plan[dow]) {
        if (!sports.includes(s.sport))
          errors.push("esporte inv\xE1lido: " + s.sport);
        if (s.durationMin != null && (s.durationMin < 0 || s.durationMin > 600))
          errors.push("dura\xE7\xE3o suspeita: " + s.durationMin);
      }
    }
    return { ok: errors.length === 0, errors };
  }

  // packages/shared/dist/loadstate.js
  var round1 = (n) => Math.round(n * 10) / 10;
  function computeStates(activities, athlete, fromISO, toISO) {
    const byDay = /* @__PURE__ */ new Map();
    for (const a of activities)
      byDay.set(a.date, (byDay.get(a.date) || 0) + sessionLoad(athlete, a));
    const days = [];
    for (let d = /* @__PURE__ */ new Date(fromISO + "T00:00:00Z"), end = /* @__PURE__ */ new Date(toISO + "T00:00:00Z"); d <= end; d = new Date(d.getTime() + 864e5))
      days.push(d.toISOString().slice(0, 10));
    const series = days.map((date) => ({ date, load: byDay.get(date) || 0 }));
    const pts = computeLoadSeries(series, 0, 0);
    const daily = series.map((s) => s.load);
    return pts.map((p, i) => {
      const ac = acwr(daily.slice(0, i + 1));
      const { monotony, strain } = monotonyStrain(daily.slice(Math.max(0, i - 6), i + 1));
      return { date: p.date, loadToday: round1(p.load), ctl: round1(p.ctl), atl: round1(p.atl), tsb: round1(p.tsb), acwr: Math.round(ac * 100) / 100, monotony: Math.round(monotony * 100) / 100, strain: round1(strain) };
    });
  }
  return __toCommonJS(index_exports);
})();
