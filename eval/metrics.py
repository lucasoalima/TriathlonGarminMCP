"""
Métricas de avaliação em Python puro (sem numpy/sklearn) — para manter o projeto
reprodutível e sem dependências pesadas, e para deixar o cálculo explícito/auditável.

Cobre: acurácia, precisão/recall/F1 (binário e macro), matriz de confusão e
coeficiente kappa de Cohen (concordância corrigida pelo acaso).
"""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple


def accuracy(y_true: Sequence, y_pred: Sequence) -> float:
    if not y_true:
        return 0.0
    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    return correct / len(y_true)


def confusion_matrix(y_true: Sequence, y_pred: Sequence, labels: List) -> List[List[int]]:
    idx = {lab: i for i, lab in enumerate(labels)}
    m = [[0 for _ in labels] for _ in labels]
    for t, p in zip(y_true, y_pred):
        if t in idx and p in idx:
            m[idx[t]][idx[p]] += 1
    return m


def binary_prf(y_true: Sequence, y_pred: Sequence, positive) -> Dict[str, float]:
    tp = sum(1 for t, p in zip(y_true, y_pred) if p == positive and t == positive)
    fp = sum(1 for t, p in zip(y_true, y_pred) if p == positive and t != positive)
    fn = sum(1 for t, p in zip(y_true, y_pred) if p != positive and t == positive)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def macro_prf(y_true: Sequence, y_pred: Sequence, labels: List) -> Dict[str, float]:
    per = [binary_prf(y_true, y_pred, lab) for lab in labels]
    n = len(labels) or 1
    return {
        "precision": sum(d["precision"] for d in per) / n,
        "recall": sum(d["recall"] for d in per) / n,
        "f1": sum(d["f1"] for d in per) / n,
    }


def cohen_kappa(y_a: Sequence, y_b: Sequence, labels: List) -> float:
    """Concordância entre dois avaliadores corrigida pelo acaso. 1=perfeita, 0=acaso."""
    n = len(y_a)
    if n == 0:
        return 0.0
    po = accuracy(y_a, y_b)  # concordância observada
    count_a = {lab: 0 for lab in labels}
    count_b = {lab: 0 for lab in labels}
    for a, b in zip(y_a, y_b):
        count_a[a] = count_a.get(a, 0) + 1
        count_b[b] = count_b.get(b, 0) + 1
    pe = sum((count_a[lab] / n) * (count_b[lab] / n) for lab in labels)  # concordância esperada
    return (po - pe) / (1 - pe) if (1 - pe) != 0 else 1.0


def format_confusion(matrix: List[List[int]], labels: List) -> str:
    w = max([len(str(l)) for l in labels] + [5])
    head = " " * (w + 3) + " ".join(str(l).rjust(w) for l in labels)
    rows = [head]
    for i, lab in enumerate(labels):
        row = str(lab).ljust(w + 2) + " " + " ".join(str(v).rjust(w) for v in matrix[i])
        rows.append(row)
    return "\n".join(rows)
