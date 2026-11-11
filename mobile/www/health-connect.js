/* ============================================================================
 * health-connect.js — HealthConnectDataSource (Garmin via Health Connect no Android)
 *
 * Lê os dados do app de saúde do Android (Health Connect) pelo plugin
 * @kiwi-health/capacitor-health-connect e monta o CTX que o app consome.
 * Health Connect NÃO expõe HRV do Garmin → prontidão é calculada por sono + carga
 * (motor `shared`, pesos recalibrados). Ver docs/Integracao_Garmin_sem_CNPJ.md.
 *
 * Estrutura: funções PURAS (aggregate / buildCTXFrom) testáveis em Node, e funções
 * de I/O (available / ensurePermissions / read / buildContext) que falam com o plugin.
 * ==========================================================================*/
(function (global) {
  'use strict';

  var READ_TYPES = ['ExerciseSession', 'HeartRateSeries', 'SleepSession', 'Steps', 'OxygenSaturation'];

  // Estágios de sono do Health Connect (SleepSessionRecord.STAGE_TYPE_*)
  var STAGE = { AWAKE: 1, SLEEPING: 2, OUT_OF_BED: 3, LIGHT: 4, DEEP: 5, REM: 6, AWAKE_IN_BED: 7 };
  var ASLEEP = { 2: 1, 4: 1, 5: 1, 6: 1 };

  // ---- helpers puros ----
  function ymd(d) { // data local YYYY-MM-DD
    var y = d.getFullYear(), m = String(d.getMonth() + 1).padStart(2, '0'), day = String(d.getDate()).padStart(2, '0');
    return y + '-' + m + '-' + day;
  }
  function fmtDur(sec) {
    var h = Math.floor(sec / 3600), m = Math.round((sec % 3600) / 60);
    return h > 0 ? h + 'h' + String(m).padStart(2, '0') : m + 'min';
  }
  function round(n) { return Math.round(n); }

  // exerciseType do Health Connect -> Sport do motor (best-effort; o título costuma ser mais fiável)
  var EX_TYPE = { 8: 'Bike', 9: 'Bike', 56: 'Corrida', 57: 'Corrida', 79: 'Outro', 73: 'Natação', 74: 'Natação', 80: 'Força', 81: 'Força' };
  function sportOf(title, exerciseType) {
    var t = (title || '').toLowerCase();
    if (/pedal|bike|cicl|cycl/.test(t)) return 'Bike';
    if (/corrida|run|trote|corre/.test(t)) return 'Corrida';
    if (/nata|swim|piscina/.test(t)) return 'Natação';
    if (/for[çc]a|strength|muscula|weight/.test(t)) return 'Força';
    return EX_TYPE[exerciseType] || 'Outro';
  }
  var SPORT_LABEL = { Bike: 'pedal', Corrida: 'corrida', Natação: 'natação', Força: 'treino de força', Descanso: 'descanso', Outro: 'treino' };
  function zoneTag(title) { var m = (title || '').match(/\bZ([1-5])\b/i); return m ? ' em Z' + m[1] : ''; }

  /**
   * aggregate(records, {today}) — PURA. Transforma registros crus do Health Connect
   * em { activities[], wellnessByDate{}, athlete } no formato do motor `shared`.
   * records: { exercise:[], hr:[], sleep:[], steps:[], spo2:[] }
   */
  function aggregate(records, opts) {
    opts = opts || {};
    var ex = records.exercise || [], hr = records.hr || [], sleep = records.sleep || [];

    // 1) todas as amostras de FC (para casar com sessões e estimar hrRest/hrMax)
    var samples = [];
    hr.forEach(function (r) { (r.samples || []).forEach(function (s) { samples.push({ t: +new Date(s.time), bpm: s.beatsPerMinute }); }); });
    samples.sort(function (a, b) { return a.t - b.t; });
    var bpms = samples.map(function (s) { return s.bpm; }).filter(function (x) { return x > 0; });
    var hrMax = bpms.length ? Math.max.apply(null, bpms) : 190;
    var hrRest = bpms.length ? Math.min.apply(null, bpms) : 60;
    var athlete = { sex: opts.sex || 'M', hrRest: hrRest, hrMax: Math.max(hrMax, hrRest + 40) };

    function hrInRange(t0, t1) {
      var vals = [];
      for (var i = 0; i < samples.length; i++) { if (samples[i].t >= t0 && samples[i].t <= t1) vals.push(samples[i].bpm); else if (samples[i].t > t1) break; }
      if (!vals.length) return { avg: undefined, max: undefined };
      return { avg: Math.round(vals.reduce(function (a, b) { return a + b; }, 0) / vals.length), max: Math.max.apply(null, vals) };
    }

    // 2) atividades
    var activities = ex.map(function (r, i) {
      var start = new Date(r.startTime), end = new Date(r.endTime);
      var durMin = Math.max(1, Math.round((end - start) / 60000));
      var sport = sportOf(r.title, r.exerciseType);
      var h = hrInRange(+start, +end);
      return {
        id: (r.metadata && r.metadata.id) || ('hc' + i),
        sport: sport, date: ymd(start), durationMin: durMin,
        avgHr: h.avg, maxHr: h.max,
        _title: r.title || '', _start: +start, _end: +end,
      };
    }).sort(function (a, b) { return a._start - b._start; });

    // 3) sono por dia de despertar (endTime)
    var wellnessByDate = {};
    sleep.forEach(function (r) {
      var end = new Date(r.endTime), date = ymd(end);
      var stages = r.stages || [];
      var asleepSec = 0, deepSec = 0, remSec = 0;
      if (stages.length) {
        stages.forEach(function (s) {
          var dur = (new Date(s.endTime) - new Date(s.startTime)) / 1000;
          if (ASLEEP[s.stage]) asleepSec += dur;
          if (s.stage === STAGE.DEEP) deepSec += dur;
          if (s.stage === STAGE.REM) remSec += dur;
        });
      } else {
        asleepSec = (new Date(r.endTime) - new Date(r.startTime)) / 1000; // sem estágios: usa duração
      }
      var prev = wellnessByDate[date];
      var cur = { date: date, sleepHours: asleepSec / 3600, sleepDeepMin: Math.round(deepSec / 60), sleepRemMin: Math.round(remSec / 60), _sec: asleepSec };
      if (!prev || cur._sec > prev._sec) wellnessByDate[date] = cur; // maior sessão do dia
    });

    return { activities: activities, wellnessByDate: wellnessByDate, athlete: athlete };
  }

  /**
   * buildCTXFrom(agg, {today, engine, name}) — PURA. Usa o motor `shared` (CopilotoEngine)
   * para calcular carga/prontidão e devolve o CTX no formato do app.
   */
  function buildCTXFrom(agg, opts) {
    opts = opts || {};
    var engine = opts.engine || global.CopilotoEngine;
    if (!engine) throw new Error('CopilotoEngine (engine.js) não carregado');
    var today = opts.today || ymd(new Date());
    var acts = agg.activities, wByDate = agg.wellnessByDate, athlete = agg.athlete;

    // janela do cálculo: 42 dias até hoje
    var from = ymd(new Date(new Date(today + 'T00:00:00') - 41 * 864e5));
    var rows = engine.computeStates(acts, athlete, from, today);
    var todayRow = rows[rows.length - 1] || { atl: 0, ctl: 0, tsb: 0, acwr: 0, monotony: 0 };

    var w = wByDate[today] || { date: today };
    var readiness = engine.readinessScore({
      w: w, tsb: todayRow.tsb, ctl: todayRow.ctl, acwr: todayRow.acwr,
      monotony: todayRow.monotony, overreaching: todayRow.acwr > 1.5,
    });

    // ---- carga ----
    var ac = todayRow.acwr || 0;
    var loadHigh = ac > 1.3;
    var loadStatus = ac > 1.5 ? 'muito alta' : ac > 1.3 ? 'alta' : (ac > 0 && ac < 0.8) ? 'baixa' : 'ok';

    // ---- sono: última noite vs. média das noites recentes ----
    var nights = [];
    for (var i = Math.max(0, rows.length - 8); i < rows.length; i++) { var ww = wByDate[rows[i].date]; if (ww && ww.sleepHours > 0) nights.push(ww.sleepHours); }
    var avgNight = nights.length ? nights.reduce(function (a, b) { return a + b; }, 0) / nights.length : (w.sleepHours || 0);
    var sleepDeltaMin = w.sleepHours ? round((w.sleepHours - avgNight) * 60) : 0;

    // ---- recuperação: score de prontidão do motor ----
    var recStatus = readiness.state === 'green' ? 'boa' : readiness.state === 'green-' ? 'média' : readiness.state === 'amber' ? 'atenção' : 'baixa';

    // ---- último treino ----
    var last = acts[acts.length - 1] || null;
    var lastWorkout;
    if (last) {
      var when = last.date === today ? 'hoje'
        : last.date === ymd(new Date(new Date(today + 'T00:00:00') - 864e5)) ? 'ontem' : 'em ' + last.date;
      var hard = /interval|z4|z5|tiro|forte|long[ãa]|prova|threshold|limiar/i.test(last._title) || (last.maxHr || 0) >= 178 || (last.avgHr || 0) >= 160;
      lastWorkout = { name: (SPORT_LABEL[last.sport] || 'treino') + zoneTag(last._title) + ' de ' + fmtDur((last._end - last._start) / 1000), when: when, sport: SPORT_LABEL[last.sport] || 'treino', hard: hard, broke: false, pr: false };
    } else {
      lastWorkout = { name: 'sem treino recente', when: '', sport: '', hard: false, broke: false, pr: false };
    }

    return {
      name: opts.name || 'Lucas', asOf: today, source: 'health-connect',
      hrv: null, // Health Connect não traz HRV do Garmin
      sleep: { val: fmtDur((w.sleepHours || 0) * 3600), deltaMin: sleepDeltaMin, score: null },
      load: { acute: round(todayRow.atl), chronic: round(todayRow.ctl), acwr: Math.round((ac) * 10) / 10, status: loadStatus, high: loadHigh },
      recovery: { pct: readiness.score, status: recStatus, state: readiness.state, flags: readiness.flags },
      lastWorkout: lastWorkout,
    };
  }

  // ======================= I/O (plugin Capacitor) =======================
  function plugin() {
    var Cap = global.Capacitor;
    if (!Cap || !Cap.registerPlugin) throw new Error('Capacitor indisponível (não é ambiente nativo)');
    return Cap.registerPlugin('HealthConnect');
  }
  function isNative() { var Cap = global.Capacitor; return !!(Cap && Cap.isNativePlatform && Cap.isNativePlatform()); }

  function available() {
    return plugin().checkAvailability().then(function (r) { return r.availability; });
  }
  function ensurePermissions() {
    var hc = plugin(), req = { read: READ_TYPES, write: [] };
    return hc.checkHealthPermissions(req).then(function (r) {
      if (r.hasAllPermissions) return true;
      return hc.requestHealthPermissions(req).then(function (r2) { return r2.hasAllPermissions; });
    });
  }
  function readType(type, from, to) {
    return plugin().readRecords({ type: type, timeRangeFilter: { type: 'between', startTime: from, endTime: to }, ascendingOrder: true, pageSize: 5000 })
      .then(function (r) { return r.records || []; })
      .catch(function () { return []; }); // permissão parcial não deve derrubar tudo
  }
  function readWindow(days) {
    var to = new Date(), from = new Date(to.getTime() - (days || 42) * 864e5);
    var hr_from = new Date(to.getTime() - 14 * 864e5); // FC detalhada só nas 2 últimas semanas (volume)
    return Promise.all([
      readType('ExerciseSession', from, to),
      readType('HeartRateSeries', hr_from, to),
      readType('SleepSession', from, to),
      readType('Steps', from, to),
      readType('OxygenSaturation', from, to),
    ]).then(function (res) { return { exercise: res[0], hr: res[1], sleep: res[2], steps: res[3], spo2: res[4] }; });
  }

  /** buildContext({days,name}) — fluxo completo no device: disponibilidade → permissões → leitura → CTX. */
  function buildContext(opts) {
    opts = opts || {};
    if (!isNative()) return Promise.reject(new Error('Fora de ambiente nativo'));
    return available().then(function (av) {
      if (av !== 'Available') { var e = new Error('Health Connect: ' + av); e.availability = av; throw e; }
      return ensurePermissions();
    }).then(function (granted) {
      if (!granted) throw new Error('Permissões do Health Connect não concedidas');
      return readWindow(opts.days || 42);
    }).then(function (records) {
      var agg = aggregate(records, { today: ymd(new Date()) });
      return buildCTXFrom(agg, { today: ymd(new Date()), name: opts.name });
    });
  }

  var HC = {
    READ_TYPES: READ_TYPES, isNative: isNative, available: available, ensurePermissions: ensurePermissions,
    readWindow: readWindow, aggregate: aggregate, buildCTXFrom: buildCTXFrom, buildContext: buildContext,
    openSettings: function () { return plugin().openHealthConnectSetting(); }, _ymd: ymd,
  };
  global.CopilotoHC = HC;
  if (typeof module !== 'undefined' && module.exports) module.exports = HC;
})(typeof window !== 'undefined' ? window : globalThis);
