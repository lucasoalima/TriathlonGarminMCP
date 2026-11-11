import asyncio
import json

from triathlon_coach.checkin import (
    get_daily_checkin_schema,
    normalize_subjective_checkin,
    checkin_required_before,
)


def test_pain_unknown_when_omitted():
    c = normalize_subjective_checkin({"fatigue_0_10": 5})
    assert c["pain"]["status"] == "unknown"
    assert c["pain"]["has_pain"] is None
    assert "pain" in c["missing_required_fields"]
    assert c["checkin_complete"] is False


def test_pain_not_defaulted_to_false():
    c = normalize_subjective_checkin({})
    assert c["pain"]["has_pain"] is not None or c["pain"]["status"] == "unknown"
    assert c["pain"]["status"] != "no"


def test_pain_explicit_no():
    c = normalize_subjective_checkin({
        "pain": {"has_pain": False},
        "fatigue_0_10": 4,
        "available_minutes": 60,
        "schedule_constraints": "nenhuma",
    })
    assert c["pain"]["status"] == "no"
    assert c["checkin_complete"] is True


def test_optional_defaults_motivation_stress():
    c = normalize_subjective_checkin({
        "pain": {"has_pain": False},
        "fatigue_0_10": 4,
        "available_minutes": 45,
        "schedule_constraints": "ok",
    })
    assert c["motivation_0_10"] == 5
    assert c["stress_0_10"] == 5
    assert c["sleep_quality_subjective_0_10"] is None


def test_available_minutes_not_invented():
    c = normalize_subjective_checkin({"pain": {"has_pain": False}, "fatigue_0_10": 3})
    assert c["available_minutes"] is None
    assert "available_minutes" in c["missing_required_fields"]


def test_checkin_required_before_run_when_pain_unknown():
    c = normalize_subjective_checkin({"fatigue_0_10": 5, "available_minutes": 60, "schedule_constraints": "x"})
    assert checkin_required_before(c, ["run"]) == ["pain"]


def test_schema_has_prompt():
    schema = get_daily_checkin_schema()
    assert schema["schema_type"] == "daily_subjective_checkin"
    assert "prompt_pt" in schema
    assert "claude_prompt_short_pt" in schema
    assert "pain" in schema["required_fields"]
    assert "fields" in schema
    assert schema["fields"]["pain"]["missing_behavior"] == "unknown"


def test_schema_json_serializable():
    schema = get_daily_checkin_schema()
    text = json.dumps(schema)
    assert "daily_subjective_checkin" in text
    assert json.loads(text)["schema_type"] == "daily_subjective_checkin"


def test_schema_not_coroutine():
    result = get_daily_checkin_schema()
    assert not asyncio.iscoroutine(result)
    assert isinstance(result, dict)
