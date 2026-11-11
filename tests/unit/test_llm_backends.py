"""Testes offline do baseline (FakeBackend) e do parser de veredito — sem rede/chaves."""
from triathlon_coach_llm.backends import FakeBackend
from triathlon_coach_llm.mediator_task import parse_verdict


def _case(sessions, **ctx):
    base = {"readiness_level": "normal", "sleep_hours": 7.5, "pain_status": "no",
            "previous_day_hard": False, "day": "tuesday"}
    base.update(ctx)
    return {"proposed_sessions": sessions, "day_context": base}


def test_fake_backend_available_offline():
    assert FakeBackend().available() is True


def test_fake_flags_hard_on_low_readiness():
    b = FakeBackend()
    case = _case([{"sport": "run", "intensity": "hard"}], readiness_level="low")
    assert b.decide(case)["verdict"] == "unsafe"


def test_fake_flags_run_with_pain():
    b = FakeBackend()
    case = _case([{"sport": "run", "intensity": "easy"}], pain_status="yes")
    assert b.decide(case)["verdict"] == "unsafe"


def test_fake_allows_easy_on_good_day():
    b = FakeBackend()
    case = _case([{"sport": "bike", "intensity": "easy"}])
    assert b.decide(case)["verdict"] == "safe"


def test_fake_is_deterministic():
    b = FakeBackend()
    case = _case([{"sport": "run", "intensity": "hard"}], sleep_hours=5.0)
    assert b.decide(case)["verdict"] == b.decide(case)["verdict"] == "unsafe"


def test_parse_verdict_json_and_text():
    assert parse_verdict('{"verdict": "unsafe", "reason": "x"}') == "unsafe"
    assert parse_verdict('{"verdict":"safe"}') == "safe"
    assert parse_verdict("I think this is UNSAFE because...") == "unsafe"
    assert parse_verdict("looks safe to me") == "safe"
    assert parse_verdict("") == "unknown"
