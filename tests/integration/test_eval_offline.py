"""
O harness de avaliacao e a comparacao de modelos rodam ponta-a-ponta OFFLINE
(apenas motor + baseline). Nao checamos numeros exatos (nao hardcode) — apenas
que executa e produz metricas em faixas sanas.
"""
import run_eval
from triathlon_coach_llm.backends import FakeBackend, available_backends


def test_safety_gate_eval_runs():
    r = run_eval.eval_safety_gate()
    assert r["n"] >= 20
    assert 0.0 <= r["accuracy"] <= 1.0
    assert 0.0 <= r["unsafe_recall"] <= 1.0
    assert -1.0 <= r["cohen_kappa"] <= 1.0
    assert len(r["confusion_matrix"]) == 2


def test_classification_eval_runs():
    r = run_eval.eval_classification()
    assert r["n"] >= 12
    assert 0.0 <= r["accuracy"] <= 1.0
    assert set(["completed", "partial", "substituted", "missed"]) & set(r["confusion_labels"])


def test_fake_backend_always_available_for_ci():
    # garante que a comparacao sempre tem pelo menos 1 backend para rodar em CI
    assert FakeBackend() is not None
    names = {b.name for b in available_backends()}
    assert "fake_baseline" in names
