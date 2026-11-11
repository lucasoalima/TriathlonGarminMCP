"""
Compara abordagens na tarefa do mediator (seguro/inseguro), usando o dataset rotulado.

Mede, por abordagem:
- acuracia e kappa vs. rotulos humanos (gold)
- concordancia com o motor deterministico (oraculo) + kappa
- latencia media

O motor aparece como referencia. Rodamos SEMPRE o baseline offline (FakeBackend);
Ollama/Claude entram automaticamente se disponiveis (servidor local / ANTHROPIC_API_KEY),
senao sao marcados como "nao executado" — nunca inventamos numeros.

Uso:
  python -m triathlon_coach_llm.compare            # todos os backends disponiveis
  python -m triathlon_coach_llm.compare --fake     # forca so o baseline offline
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from triathlon_coach.engine import validate_training_decision  # noqa: E402
import metrics as M  # noqa: E402
from triathlon_coach_llm.backends import FakeBackend, available_backends  # noqa: E402

DATA = ROOT / "eval" / "dataset" / "safety_gate.jsonl"
OUT = ROOT / "eval" / "results"
LABELS = ["unsafe", "safe"]


def _load():
    with open(DATA, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def engine_preds(rows):
    out = []
    for r in rows:
        res = validate_training_decision(
            r["proposed_sessions"], r["day_context"],
            weekly_context=r.get("weekly_context"),
            athlete_profile=r.get("athlete_profile"),
            manual_override_pain=r.get("manual_override_pain", False),
        )
        out.append("safe" if res["is_valid"] else "unsafe")
    return out


def run_backend(backend, rows):
    preds, latencies = [], []
    for r in rows:
        d = backend.decide(r)
        v = d["verdict"] if d["verdict"] in LABELS else "safe"  # fallback conservador
        preds.append(v)
        latencies.append(d.get("latency_ms", 0.0))
    return preds, (sum(latencies) / len(latencies) if latencies else 0.0)


def score(name, preds, gold, eng):
    return {
        "approach": name,
        "accuracy_vs_gold": round(M.accuracy(gold, preds), 4),
        "kappa_vs_gold": round(M.cohen_kappa(gold, preds, LABELS), 4),
        "agreement_vs_engine": round(M.accuracy(eng, preds), 4),
        "kappa_vs_engine": round(M.cohen_kappa(eng, preds, LABELS), 4),
        "unsafe_recall_vs_gold": round(M.binary_prf(gold, preds, "unsafe")["recall"], 4),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fake", action="store_true", help="roda apenas o baseline offline")
    args = ap.parse_args()

    rows = _load()
    gold = ["safe" if r["gold_safe"] else "unsafe" for r in rows]
    eng = engine_preds(rows)

    results = []
    # motor como referencia (ele proprio e o oraculo -> concordancia 100% consigo mesmo)
    results.append({**score("engine (deterministico)", eng, gold, eng), "mean_latency_ms": 0.0, "status": "run"})

    backends = [FakeBackend()] if args.fake else available_backends()
    names_run = {b.name for b in backends}
    for b in backends:
        preds, lat = run_backend(b, rows)
        results.append({**score(b.name, preds, gold, eng), "mean_latency_ms": round(lat, 2), "status": "run"})

    # backends nao executados (honestidade: sem numeros inventados)
    for maybe in ["ollama", "claude"]:
        if maybe not in names_run and not args.fake:
            results.append({"approach": maybe, "status": "nao_executado",
                            "note": "requer servidor local (Ollama) ou ANTHROPIC_API_KEY"})

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "model_comparison.json").write_text(json.dumps({"n": len(rows), "results": results},
                                               indent=2, ensure_ascii=False), encoding="utf-8")
    _write_md(len(rows), results)
    for r in results:
        if r.get("status") == "run":
            print("%-24s acc_vs_gold=%.0f%% kappa_vs_gold=%.2f agree_engine=%.0f%% lat=%.1fms" % (
                r["approach"], r["accuracy_vs_gold"] * 100, r["kappa_vs_gold"],
                r["agreement_vs_engine"] * 100, r["mean_latency_ms"]))
        else:
            print("%-24s NAO EXECUTADO (%s)" % (r["approach"], r.get("note", "")))
    print("Tabela -> eval/results/model_comparison.md")


def _write_md(n, results):
    lines = ["# Comparacao de abordagens — tarefa do mediator (seguro/inseguro)\n",
             f"> Dataset: {n} casos rotulados. Numeros medidos por `python -m triathlon_coach_llm.compare`.",
             "> O motor deterministico e o oraculo; LLMs sao comparados contra ele e contra o gold.\n",
             "| Abordagem | Acc vs gold | Kappa vs gold | Recall inseguro | Concord. c/ motor | Latencia media |",
             "|---|---|---|---|---|---|"]
    for r in results:
        if r.get("status") == "run":
            lines.append("| %s | %.0f%% | %.2f | %.0f%% | %.0f%% | %.1f ms |" % (
                r["approach"], r["accuracy_vs_gold"] * 100, r["kappa_vs_gold"],
                r["unsafe_recall_vs_gold"] * 100, r["agreement_vs_engine"] * 100, r["mean_latency_ms"]))
        else:
            lines.append("| %s | — | — | — | — | *nao executado* |" % r["approach"])
    lines.append("\n*Linhas 'nao executado' exigem configuracao local (Ollama em "
                 "`localhost:11434` ou `ANTHROPIC_API_KEY`). Rode o comando acima na sua maquina para preenche-las.*")
    (OUT / "model_comparison.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
