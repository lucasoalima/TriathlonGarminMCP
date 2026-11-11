// Parser de plano de treino: heurístico (offline, fallback) + wrapper LLM opcional + validação.
import type { WeeklyPlan, PlannedSession, Sport } from "./types";

export interface LlmClient { complete(system: string, user: string): Promise<string>; }

const DOW_MAP: Record<string, number> = {
  dom:0, domingo:0, seg:1, segunda:1, ter:2, terca:2, "terça":2, qua:3, quarta:3,
  qui:4, quinta:4, sex:5, sexta:5, sab:6, "sáb":6, sabado:6, "sábado":6,
};
const DAY_LABEL = ["Dom","Seg","Ter","Qua","Qui","Sex","Sáb"];

function detectSport(s: string): Sport {
  const t = s.toLowerCase();
  if (/(corr|\brun\b|trote|rodage|maratona|\d+\s*k\b)/.test(t)) return "Corrida";
  if (/(bike|pedal|ciclis|bicicle|rolo|cycl)/.test(t)) return "Bike";
  if (/(nata|nado|swim|piscina|crawl)/.test(t)) return "Natação";
  if (/(for[çc]a|muscula|academia|\bcore\b|strength|\bgym\b)/.test(t)) return "Força";
  if (/(descanso|folga|\brest\b|\boff\b)/.test(t)) return "Descanso";
  return "Outro";
}
// Duração em min: aceita Xh, X min/minutos, e X' (apóstrofo) — mas ignora tempos de recuperação ("rec 1'").
function parseDuration(s: string): number | null {
  let min = 0;
  const h = s.match(/(\d+(?:[.,]\d+)?)\s*h\b/i); if (h) min += Math.round(parseFloat(h[1].replace(",", ".")) * 60);
  const mm = s.match(/(\d+)\s*(?:min|minutos)\b/i); if (mm) min += parseInt(mm[1], 10);
  for (const a of s.matchAll(/(\d+)\s*'/g)) {
    const idx = a.index ?? 0; const before = s.slice(Math.max(0, idx - 8), idx).toLowerCase();
    const val = parseInt(a[1], 10);
    if (val >= 5 && !/(rec|rest|desc|pausa)/.test(before)) min += val; // "40'" conta; "rec 1'" não
  }
  return min > 0 ? min : null;
}
function detectZone(s: string): { zone?: string; quality: boolean } {
  const t = s.toLowerCase();
  const quality = /(forte|tiros|intervalad|limiar|tempo|\d+\s*x\s*\d+)/.test(t);
  const z = t.match(/z\s*([1-5])/);
  if (z) return { zone: "Z" + z[1], quality };
  if (/(limiar|tempo|forte)/.test(t)) return { zone: "Z3–limiar", quality: true };
  if (/(leve|f[aá]cil|regenerativ|\bbase\b)/.test(t)) return { zone: "Z2", quality };
  return { zone: undefined, quality };
}
// separa sessões por + / ; respeitando parênteses (não quebra "(core+pernas)")
function splitSessions(body: string): string[] {
  const out: string[] = []; let buf = ""; let depth = 0;
  for (const ch of body) {
    if (ch === "(") depth++; else if (ch === ")") depth = Math.max(0, depth - 1);
    if (depth === 0 && (ch === "+" || ch === "/" || ch === ";")) { if (buf.trim()) out.push(buf.trim()); buf = ""; continue; }
    buf += ch;
  }
  if (buf.trim()) out.push(buf.trim());
  return out;
}

export function parsePlanText(text: string): { plan: WeeklyPlan; warnings: string[] } {
  const plan: WeeklyPlan = {}; const warnings: string[] = [];
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim(); if (!line) continue;
    const dm = line.match(/^\s*([A-Za-zçáéíóúâãêô]+)\.?\s*[:\-–]\s*(.+)$/);
    if (!dm) { if (!/plano|semana|assessoria|bloco/i.test(line)) warnings.push("linha ignorada: " + line); continue; }
    const dow = DOW_MAP[dm[1].toLowerCase()];
    if (dow === undefined) { warnings.push("dia não reconhecido: " + dm[1]); continue; }
    const sessions: PlannedSession[] = splitSessions(dm[2]).map((c) => {
      const sport = detectSport(c);
      const { zone, quality } = detectZone(c);
      const durationMin = parseDuration(c);
      const sess: PlannedSession = { sport, type: c };
      if (zone) sess.zone = zone;
      if (durationMin != null) sess.durationMin = durationMin;
      if (quality) sess.quality = true;
      if (durationMin == null && sport !== "Descanso") warnings.push(`sem duração explícita em "${c}" (${DAY_LABEL[dow]}) — estimar do histórico/pace`);
      return sess;
    });
    plan[dow] = (plan[dow] || []).concat(sessions);
  }
  return { plan, warnings };
}

export interface ParseResult { plan: WeeklyPlan; warnings: string[]; source: "llm" | "heuristic"; }
const LLM_SYS = 'Você é um parser de planos de treino de assessorias. Responda SOMENTE com JSON: {"dias":[{"dia":"Seg","sessoes":[{"esporte":"Corrida|Bike|Natação|Força|Descanso|Outro","zona":"","duracao_min":numero_ou_null,"tipo":""}]}]}. Não invente treinos que não estão no texto.';
function normSport(s: string): Sport { const t=(s||"").toLowerCase(); if(t.startsWith("corr"))return"Corrida"; if(t.startsWith("bik"))return"Bike"; if(t.startsWith("nat"))return"Natação"; if(t.startsWith("for"))return"Força"; if(t.startsWith("desc"))return"Descanso"; return "Outro"; }
function fromDiasJson(parsed: any): WeeklyPlan {
  const map: Record<string, number> = { dom:0, seg:1, ter:2, qua:3, qui:4, sex:5, "sáb":6, sab:6 };
  const plan: WeeklyPlan = {};
  for (const d of (parsed?.dias || [])) {
    const dow = map[(d.dia || "").toLowerCase()]; if (dow === undefined) continue;
    plan[dow] = (d.sessoes || []).map((s: any): PlannedSession => {
      const sess: PlannedSession = { sport: normSport(s.esporte) };
      if (s.zona) sess.zone = s.zona;
      if (typeof s.duracao_min === "number") sess.durationMin = s.duracao_min;
      if (s.tipo) sess.type = s.tipo;
      if (/forte|limiar|tempo|tiros/i.test((s.tipo || "") + (s.zona || ""))) sess.quality = true;
      return sess;
    });
  }
  return plan;
}
export async function parsePlan(text: string, llm?: LlmClient): Promise<ParseResult> {
  if (llm) {
    try {
      const raw = await llm.complete(LLM_SYS, text);
      const j = raw.slice(raw.indexOf("{"), raw.lastIndexOf("}") + 1);
      const plan = fromDiasJson(JSON.parse(j));
      if (validatePlan(plan).ok && Object.keys(plan).length) return { plan, warnings: [], source: "llm" };
    } catch { /* fallback */ }
  }
  return { ...parsePlanText(text), source: "heuristic" };
}
export function validatePlan(plan: WeeklyPlan): { ok: boolean; errors: string[] } {
  const errors: string[] = []; const sports = ["Corrida","Bike","Natação","Força","Descanso","Outro"];
  for (const k of Object.keys(plan)) {
    const dow = Number(k); if (!(dow >= 0 && dow <= 6)) errors.push("dow inválido: " + k);
    for (const s of plan[dow as unknown as number]) {
      if (!sports.includes(s.sport)) errors.push("esporte inválido: " + s.sport);
      if (s.durationMin != null && (s.durationMin < 0 || s.durationMin > 600)) errors.push("duração suspeita: " + s.durationMin);
    }
  }
  return { ok: errors.length === 0, errors };
}
