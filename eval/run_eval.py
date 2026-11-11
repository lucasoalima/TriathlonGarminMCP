"""
Avaliacao do motor deterministico contra datasets rotulados independentemente.

- Safety gate: validate_training_decision prediz is_valid (seguro/inseguro);
  comparamos com o rotulo humano (gold_safe). Classe positiva = "inseguro"
  (o que o guardrail PRECISA pegar) -> precisao/recall/F1 + matriz + kappa.
- Classificacao de execucao: classify_completed_activity prediz execution_quality;
  comparamos com gold_quality -> acuracia + macro-F1 + matriz + kappa.

Numeros sao medidos em tempo de execucao (nunca hardcoded). Gera:
  eval/results/eval_results.json  e  eval/results/eval_report.md
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from triathlon_coach.engine import validate_training_decision, classify_completed_activity  # noqa: E402
import metrics as M  # noqa: E402

DATA = ROOT / "eval" / "dataset"
OUT = ROOT / "eval" / "results"


def _load(name):
    with open(DATA / name, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def eval_safety_gate():
    rows = _load("safety_gate.jsonl")
    # rotulos como strings "safe"/"unsafe" (classe positiva = unsafe)
    y_true, y_pred, disagreements = [], [], []
    for r in rows:
        res = validate_training_decision(
            r["proposed_sessions"], r["day_context"],
            weekly_context=r.get("weekly_context"),
            athlete_profile=r.get("athlete_profile"),
            manual_override_pain=r.get("manual_override_pain", False),
        )
        gold = "safe" if r["gold_safe"] else "unsafe"
        pred = "safe" if res["is_valid"] else "unsafe"
        y_true.append(gold)
        y_pred.append(pred)
        if gold != pred:
            disagreements.append({"id": r["id"], "gold": gold, "pred": pred,
                                  "violations": res["violations"], "desc": r["description"]})
    labels = ["unsafe", "safe"]
    prf = M.binary_prf(y_true, y_pred, positive="unsafe")
    return {
        "n": len(rows),
        "accuracy": round(M.accuracy(y_true, y_pred), 4),
        "unsafe_precision": round(prf["precision"], 4),
        "unsafe_recall": round(prf["recall"], 4),
        "unsafe_f1": round(prf["f1"], 4),
        "cohen_kappa": round(M.cohen_kappa(y_true, y_pred, labels), 4),
        "confusion_labels": labels,
        "confusion_matrix": M.confusion_matrix(y_true, y_pred, labels),
        "disagreements": disagreements,
    }


def eval_classification():
    rows = _load("classification.jsonl")
    y_true, y_pred, disagreements = [], [], []
    # Avaliamos o campo `status` (completed/partial/substituted/missed): sinal discriminativo
    # que independe de FC. `execution_quality` depende de dados de frequencia cardiaca e,
    # sem eles, degenera para "acceptable" (documentado como limitacao no MODEL_CARD).
    for r in rows:
        res = classify_completed_activity(r["planned_session"], r["completed_activity"])
        gold = r["gold_status"]
        pred = res.get("status", "unknown")
        y_true.append(gold)
        y_pred.append(pred)
        if gold != pred:
            disagreements.append({"id": r["id"], "gold": gold, "pred": pred, "desc": r["description"]})
    labels = sorted(set(y_true) | set(y_pred))
    macro = M.macro_prf(y_true, y_pred, labels)
    return {
        "n": len(rows),
        "accuracy": round(M.accuracy(y_true, y_pred), 4),
        "macro_precision": round(macro["precision"], 4),
        "macro_recall": round(macro["recall"], 4),
        "macro_f1": round(macro["f1"], 4),
        "cohen_kappa": round(M.cohen_kappa(y_true, y_pred, labels), 4),
        "confusion_labels": labels,
        "confusion_matrix": M.confusion_matrix(y_true, y_pred, labels),
        "disagreements": disagreements,
    }


def _md(sg, cl):
    lines = []
    lines.append("# Resultados da avaliacao\n")
    lines.append("> Numeros medidos por `python eval/run_eval.py`. Rotulos (gold) feitos a mao "
                 "a partir de principios gerais de treino de endurance, independentes do motor.\n")

    lines.append("## 1. Safety gate (`validate_training_decision`)\n")
    lines.append(f"- Casos: **{sg['n']}**")
    lines.append(f"- Acuracia: **{sg['accuracy']:.0%}**")
    lines.append(f"- Deteccao de INSEGURO -> precisao **{sg['unsafe_precision']:.0%}**, "
                 f"recall **{sg['unsafe_recall']:.0%}**, F1 **{sg['unsafe_f1']:.2f}**")
    lines.append(f"- Kappa de Cohen (motor vs humano): **{sg['cohen_kappa']:.2f}**\n")
    lines.append("Matriz de confusao (linha = gold, coluna = motor):\n")
    lines.append("```\n" + M.format_confusion(sg["confusion_matrix"], sg["confusion_labels"]) + "\n```\n")
    if sg["disagreements"]:
        lines.append("Divergencias (onde motor e humano discordam):\n")
        for d in sg["disagreements"]:
            lines.append(f"- `{d['id']}` gold=**{d['gold']}** motor=**{d['pred']}** "
                         f"(violacoes={d['violations']}) — {d['desc']}")
        lines.append("")

    lines.append("## 2. Classificacao de execucao (`classify_completed_activity`)\n")
    lines.append(f"- Casos: **{cl['n']}**")
    lines.append(f"- Acuracia: **{cl['accuracy']:.0%}**")
    lines.append(f"- Macro F1: **{cl['macro_f1']:.2f}** (P **{cl['macro_precision']:.2f}** / "
                 f"R **{cl['macro_recall']:.2f}**)")
    lines.append(f"- Kappa de Cohen: **{cl['cohen_kappa']:.2f}**\n")
    lines.append("Matriz de confusao (linha = gold, coluna = motor):\n")
    lines.append("```\n" + M.format_confusion(cl["confusion_matrix"], cl["confusion_labels"]) + "\n```\n")
    if cl["disagreements"]:
        lines.append("Divergencias:\n")
        for d in cl["disagreements"]:
            lines.append(f"- `{d['id']}` gold=**{d['gold']}** motor=**{d['pred']}** — {d['desc']}")
        lines.append("")
    return "\n".join(lines)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sg = eval_safety_gate()
    cl = eval_classification()
    results = {"safety_gate": sg, "classification": cl}
    (OUT / "eval_results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "eval_report.md").write_text(_md(sg, cl), encoding="utf-8")
    print("Safety gate:   n=%d acc=%.0f%% unsafe_recall=%.0f%% kappa=%.2f" % (
        sg["n"], sg["accuracy"] * 100, sg["unsafe_recall"] * 100, sg["cohen_kappa"]))
    print("Classification: n=%d acc=%.0f%% macroF1=%.2f kappa=%.2f" % (
        cl["n"], cl["accuracy"] * 100, cl["macro_f1"], cl["cohen_kappa"]))
    print("Relatorio -> eval/results/eval_report.md")


if __name__ == "__main__":
    main()
