"""Testes das métricas de avaliação (valores conhecidos → resultados conhecidos)."""
import metrics as M


def test_accuracy():
    assert M.accuracy(["a", "b", "c"], ["a", "x", "c"]) == 2 / 3
    assert M.accuracy([], []) == 0.0


def test_binary_prf_perfect():
    y = ["unsafe", "safe", "unsafe", "safe"]
    r = M.binary_prf(y, y, positive="unsafe")
    assert r["precision"] == 1.0 and r["recall"] == 1.0 and r["f1"] == 1.0


def test_binary_prf_partial():
    gold = ["unsafe", "unsafe", "safe", "safe"]
    pred = ["unsafe", "safe", "safe", "unsafe"]  # 1 TP, 1 FN, 1 FP, 1 TN
    r = M.binary_prf(gold, pred, positive="unsafe")
    assert r["tp"] == 1 and r["fp"] == 1 and r["fn"] == 1
    assert r["precision"] == 0.5 and r["recall"] == 0.5


def test_confusion_matrix():
    labels = ["x", "y"]
    m = M.confusion_matrix(["x", "x", "y"], ["x", "y", "y"], labels)
    assert m == [[1, 1], [0, 1]]


def test_cohen_kappa_bounds():
    labels = ["a", "b"]
    assert M.cohen_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"], labels) == 1.0
    # concordância igual ao acaso -> kappa ~ 0
    k = M.cohen_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"], labels)
    assert -1.0 <= k <= 1.0


def test_macro_prf_keys():
    out = M.macro_prf(["a", "b"], ["a", "b"], ["a", "b"])
    assert set(out) == {"precision", "recall", "f1"}
    assert out["f1"] == 1.0
