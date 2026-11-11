import json

import pytest

from triathlon_coach.mediator_audit import (
    audit_coach_mediator_session,
    normalize_session_trace,
    normalize_session_type,
    normalize_strictness,
)
from triathlon_coach.planning import build_triathlon_week_template


def _daily_base_trace(**overrides):
    trace = {
        "user_checkin": {
            "provided": True,
            "pain": {"has_pain": False, "pain_confirmed_by_user": True},
            "fatigue_0_10": 5,
            "available_minutes": 60,
            "schedule_constraints": "none",
        },
        "tool_sequence": [
            "get_daily_checkin_schema",
            "get_daily_training_brief",
            "plan_triathlon_week",
            "adjust_today_workout",
            "validate_training_decision",
            "create_easy_bike_workout",
        ],
        "planned_day": {"day": "monday", "date": "2026-06-16"},
        "daily_training_brief_summary": {
            "readiness_level": "normal",
            "sleep_hours": 7.0,
            "hrv_status": "balanced",
        },
        "adjust_today_workout_result": {
            "decision": "modify",
            "blocked_actions": ["hard_intervals", "double_session"],
            "risk_flags": [],
            "requires_user_confirmation_before": [],
        },
        "claude_proposed_sessions": [
            {
                "sport": "bike",
                "type": "endurance",
                "duration_minutes": 45,
                "intensity": "easy",
                "priority": "primary",
            },
        ],
        "validate_training_decision_result": {
            "is_valid": True,
            "validation_level": "pass",
            "safe_to_create_workouts": True,
            "safe_to_schedule": True,
        },
        "created_workouts": [
            {"tool": "create_easy_bike_workout", "sport": "bike", "duration_minutes": 45},
        ],
        "scheduled_workouts": [],
        "final_response_summary": {
            "mentioned_uncertainty": False,
            "explained_reasoning": True,
            "claimed_unavailable_data": False,
            "invented_metrics": False,
        },
    }
    trace.update(overrides)
    return trace


def test_daily_flow_correct_passes():
    result = audit_coach_mediator_session(
        "daily_workout_decision",
        _daily_base_trace(),
        strictness="normal",
    )
    assert result["overall_status"] == "pass"
    assert result["protocol_score"] >= 85
    assert result["safety_score"] >= 85
    assert not any(v["severity"] == "critical" for v in result["violations"])


def test_missing_adjust_today_workout():
    trace = _daily_base_trace()
    trace["tool_sequence"] = [t for t in trace["tool_sequence"] if t != "adjust_today_workout"]
    result = audit_coach_mediator_session("daily_workout_decision", trace)
    assert "adjust_today_workout" in result["missing_steps"]
    assert result["protocol_score"] <= 85
    assert result["overall_status"] in {"warning", "failed"}


def test_schedule_without_validate_fails():
    trace = _daily_base_trace()
    trace["tool_sequence"] = [
        "get_daily_training_brief",
        "adjust_today_workout",
        "create_easy_bike_workout",
        "schedule_workout",
    ]
    trace["scheduled_workouts"] = [{"tool": "schedule_workout", "date": "2026-06-16"}]
    result = audit_coach_mediator_session("daily_workout_decision", trace)
    assert result["overall_status"] == "failed"
    assert any(v["code"] == "scheduled_without_validation" for v in result["violations"])
    assert result["recommended_next_prompt"] is not None


def test_blocked_validation_but_scheduled():
    trace = _daily_base_trace()
    trace["tool_sequence"].append("schedule_workout")
    trace["scheduled_workouts"] = [{"tool": "schedule_workout", "date": "2026-06-16"}]
    trace["validate_training_decision_result"] = {
        "is_valid": False,
        "validation_level": "blocked",
        "safe_to_create_workouts": False,
        "safe_to_schedule": False,
    }
    result = audit_coach_mediator_session("daily_workout_decision", trace)
    assert result["overall_status"] == "failed"
    assert any(v["code"] == "scheduled_despite_blocked_validation" for v in result["violations"])
    assert "Do not schedule because validation was blocked." in result["required_repair_actions"]


def test_invented_pain_false():
    trace = _daily_base_trace()
    trace["user_checkin"] = {
        "provided": False,
        "pain": {"has_pain": False},
        "fatigue_0_10": 5,
    }
    result = audit_coach_mediator_session("daily_workout_decision", trace)
    assert any(v["code"] == "invented_pain_false" for v in result["violations"])
    assert result["data_integrity_score"] <= 75


def test_pain_unknown_run_strict_fails():
    trace = _daily_base_trace()
    trace["user_checkin"] = {
        "provided": True,
        "pain": {"has_pain": "unknown"},
        "fatigue_0_10": 5,
        "available_minutes": 60,
        "schedule_constraints": "none",
    }
    trace["adjust_today_workout_result"]["requires_user_confirmation_before"] = ["pain"]
    trace["claude_proposed_sessions"] = [
        {"sport": "run", "type": "endurance", "intensity": "easy", "priority": "primary"},
    ]
    result = audit_coach_mediator_session("daily_workout_decision", trace, strictness="strict")
    assert any(v["code"] == "pain_unknown_no_confirmation" for v in result["violations"])


def test_pain_unknown_run_normal_warning():
    trace = _daily_base_trace()
    trace["user_checkin"]["pain"] = {"has_pain": "unknown"}
    trace["adjust_today_workout_result"]["requires_user_confirmation_before"] = ["pain"]
    trace["claude_proposed_sessions"] = [
        {"sport": "run", "type": "endurance", "intensity": "easy", "priority": "primary"},
    ]
    result = audit_coach_mediator_session("daily_workout_decision", trace, strictness="normal")
    assert result["overall_status"] in {"warning", "failed"}
    assert any(
        v["code"] == "pain_unknown_no_confirmation" for v in result["warnings"] + result["violations"]
    )


def test_pain_yes_run_fails():
    trace = _daily_base_trace()
    trace["user_checkin"]["pain"] = {"has_pain": True}
    trace["claude_proposed_sessions"] = [
        {"sport": "run", "type": "endurance", "intensity": "easy", "priority": "primary"},
    ]
    result = audit_coach_mediator_session("daily_workout_decision", trace)
    assert result["overall_status"] == "failed"
    assert any(v["code"] == "running_with_pain" for v in result["violations"])


def test_blocked_action_used():
    trace = _daily_base_trace()
    trace["adjust_today_workout_result"]["blocked_actions"] = ["hard_intervals"]
    trace["claude_proposed_sessions"] = [
        {"sport": "run", "type": "interval", "intensity": "hard", "priority": "primary"},
    ]
    result = audit_coach_mediator_session("daily_workout_decision", trace)
    assert result["overall_status"] == "failed"
    assert "hard_intervals" in result["blocked_action_violations"]


def test_secondary_treated_as_required():
    trace = _daily_base_trace()
    trace["claude_proposed_sessions"].append(
        {"sport": "run", "type": "endurance", "intensity": "easy", "priority": "secondary", "required": True},
    )
    result = audit_coach_mediator_session("daily_workout_decision", trace, strictness="strict")
    assert any(v["code"] == "secondary_treated_as_required" for v in result["violations"])


def test_sunday_swim_fails():
    trace = _daily_base_trace()
    trace["planned_day"] = {"day": "sunday", "date": "2026-06-22"}
    trace["claude_proposed_sessions"] = [
        {"sport": "swim", "type": "endurance", "intensity": "easy", "priority": "primary"},
    ]
    result = audit_coach_mediator_session("daily_workout_decision", trace)
    assert any(v["code"] == "swim_on_sunday" for v in result["violations"])


def test_hard_with_low_readiness_fails():
    trace = _daily_base_trace()
    trace["daily_training_brief_summary"]["readiness_level"] = "low"
    trace["claude_proposed_sessions"] = [
        {"sport": "run", "type": "interval", "intensity": "hard", "priority": "primary"},
    ]
    result = audit_coach_mediator_session("daily_workout_decision", trace)
    assert any(v["code"] == "hard_with_low_readiness" for v in result["violations"])


def test_weekly_review_without_audit_when_available():
    trace = {
        "schedule_audit_available": True,
        "tool_sequence": ["weekly_coach_review"],
        "weekly_coach_review_result": {"overall_status": "maintain", "load_decision": "maintain"},
    }
    result = audit_coach_mediator_session("weekly_review", trace)
    assert "audit_week_schedule" in result["missing_steps"]
    assert result["overall_status"] in {"warning", "failed"}


def test_planning_only_pass():
    plan = build_triathlon_week_template("2026-06-16")
    trace = {
        "tool_sequence": ["plan_triathlon_week"],
        "plan_triathlon_week_result": plan,
    }
    result = audit_coach_mediator_session("planning_only", trace)
    assert result["overall_status"] == "pass"
    assert not any(v["code"] == "weight_loss_in_plan" for v in result["violations"])


def test_planning_only_weight_loss_fails():
    plan = build_triathlon_week_template("2026-06-16")
    plan["goal"] = {"focus": "weight_loss"}
    trace = {"tool_sequence": ["plan_triathlon_week"], "plan_triathlon_week_result": plan}
    result = audit_coach_mediator_session("planning_only", trace)
    assert any(v["code"] == "weight_loss_in_plan" for v in result["violations"])


def test_insufficient_data():
    result = audit_coach_mediator_session("daily_workout_decision", {})
    assert result["overall_status"] == "insufficient_data"


def test_scores_drop_with_violations():
    good = audit_coach_mediator_session("daily_workout_decision", _daily_base_trace())
    bad = audit_coach_mediator_session(
        "daily_workout_decision",
        _daily_base_trace(
            claude_proposed_sessions=[
                {"sport": "run", "type": "interval", "intensity": "hard", "priority": "primary"},
            ],
            adjust_today_workout_result={
                "decision": "modify",
                "blocked_actions": ["hard_intervals"],
                "risk_flags": [],
                "requires_user_confirmation_before": [],
            },
        ),
    )
    assert bad["safety_score"] < good["safety_score"]
    assert bad["protocol_score"] <= good["protocol_score"]


def test_required_repair_actions_returned():
    trace = _daily_base_trace()
    trace["tool_sequence"] = ["adjust_today_workout", "schedule_workout"]
    trace["scheduled_workouts"] = [{"tool": "schedule_workout", "date": "2026-06-16"}]
    result = audit_coach_mediator_session("daily_workout_decision", trace)
    assert len(result["required_repair_actions"]) >= 1


def test_recommended_next_prompt_on_critical_failure():
    trace = _daily_base_trace()
    trace["tool_sequence"] = ["create_easy_bike_workout", "schedule_workout"]
    trace["scheduled_workouts"] = [{"tool": "schedule_workout", "date": "2026-06-16"}]
    result = audit_coach_mediator_session("daily_workout_decision", trace)
    assert result["overall_status"] == "failed"
    assert result["recommended_next_prompt"] is not None
    assert "validate_training_decision" in result["recommended_next_prompt"]


def test_alias_dry_run_daily_adjustment():
    result = audit_coach_mediator_session("dry_run_daily_adjustment", _daily_base_trace())
    assert result["session_type"] == "daily_workout_decision"
    assert result.get("session_type_normalized_from") == "dry_run_daily_adjustment"
    assert any(w["code"] == "session_type_alias_used" for w in result["warnings"])


def test_alias_daily():
    result = audit_coach_mediator_session("daily", _daily_base_trace())
    assert result["session_type"] == "daily_workout_decision"


def test_alias_weekly():
    trace = {
        "schedule_audit_available": True,
        "tool_sequence": ["weekly_coach_review"],
        "weekly_coach_review_result": {"overall_status": "maintain"},
    }
    result = audit_coach_mediator_session("weekly", trace)
    assert result["session_type"] == "weekly_review"


def test_unknown_session_type_helpful_error():
    result = audit_coach_mediator_session("foo", {})
    assert result["overall_status"] == "insufficient_data"
    assert "valid_session_types" in result
    assert "accepted_aliases" in result
    assert result["accepted_aliases"]["daily"] == "daily_workout_decision"
    assert any(v["code"] == "unknown_session_type" for v in result["violations"])
    assert result["recommended_next_prompt"] is not None


def test_invalid_strictness_defaults_to_normal():
    result = audit_coach_mediator_session(
        "daily_workout_decision",
        _daily_base_trace(),
        strictness="ultra",
    )
    assert result["strictness"] == "normal"
    assert any(w["code"] == "invalid_strictness_defaulted_to_normal" for w in result["warnings"])


def test_mediator_audit_output_json_serializable():
    result = audit_coach_mediator_session("daily_workout_decision", _daily_base_trace())
    json.dumps(result)


def test_real_dry_run_trace_pass_or_warning():
    trace = {
        "user_checkin": {
            "provided": True,
            "pain": {
                "has_pain": "yes",
                "location": "pé esquerdo",
                "severity_0_10": None,
            },
            "fatigue_0_10": None,
            "available_minutes": 60,
            "schedule_constraints": None,
        },
        "tool_sequence": [
            "get_daily_training_brief",
            "plan_triathlon_week",
            "adjust_today_workout",
            "validate_training_decision",
        ],
        "adjust_today_workout_result": {
            "blocked_actions": [
                "running",
                "hard_intervals",
                "double_session",
                "heavy_leg_strength",
            ],
            "allowed_actions": [
                "technique_swim",
                "easy_bike",
                "mobility",
                "core",
                "prehab",
            ],
        },
        "claude_proposed_sessions": [
            {
                "sport": "swim",
                "type": "technique",
                "duration_minutes": 30,
                "intensity": "easy",
                "priority": "primary",
            },
            {
                "sport": "core",
                "type": "core",
                "duration_minutes": 10,
                "intensity": "easy",
                "priority": "complement",
            },
        ],
        "validate_training_decision_result": {
            "is_valid": True,
            "validation_level": "pass",
            "safe_to_schedule": True,
        },
        "created_workouts": [],
        "scheduled_workouts": [],
        "final_response_summary": {
            "mentioned_uncertainty": True,
            "explained_reasoning": True,
            "invented_metrics": False,
        },
    }
    result = audit_coach_mediator_session("dry_run_daily_adjustment", trace)
    assert result["session_type"] == "daily_workout_decision"
    assert result["overall_status"] in {"pass", "warning", "failed"}
    assert not any(v["code"] == "unknown_session_type" for v in result["violations"])


def test_normalize_session_type_canonical():
    canonical, meta = normalize_session_type("daily_workout_decision")
    assert canonical == "daily_workout_decision"
    assert meta["warnings"] == []


def test_normalize_strictness_alias():
    strict, warnings = normalize_strictness("low")
    assert strict == "lenient"
    assert warnings == []


def test_daily_dry_run_with_complete_checkin_empty_brief_and_full_tool_sequence_does_not_false_warn():
    trace = {
        "dry_run": True,
        "user_checkin": {
            "provided": True,
            "pain": {
                "has_pain": "yes",
                "location": "pé esquerdo",
                "severity_0_10": None,
            },
            "fatigue_0_10": 1,
            "available_minutes": 60,
            "schedule_constraints": "sem restrições",
        },
        "tool_sequence": [
            "get_daily_checkin_schema",
            "get_daily_training_brief",
            "plan_triathlon_week",
            "adjust_today_workout",
            "validate_training_decision",
        ],
        "daily_training_brief_summary": {
            "readiness_level": None,
            "sleep_hours": None,
            "hrv_status": None,
        },
        "planned_day": {
            "primary": {"sport": "swim", "type": "technique"},
            "complement": {"sport": "core", "type": "core"},
        },
        "adjust_today_workout_result": {
            "decision": "modify",
            "blocked_actions": [
                "running",
                "hard_intervals",
                "long_run",
                "double_session",
                "heavy_leg_strength",
            ],
            "allowed_actions": [
                "keep_technique_swim",
                "do_core",
                "do_mobility",
                "do_easy_bike",
                "do_prehab",
            ],
            "requires_user_confirmation_before": [],
        },
        "claude_proposed_sessions": [
            {
                "sport": "swim",
                "type": "technique",
                "duration_minutes": 30,
                "intensity": "easy",
                "priority": "primary",
            },
            {
                "sport": "core",
                "type": "core",
                "duration_minutes": 10,
                "intensity": "easy",
                "priority": "complement",
            },
        ],
        "validate_training_decision_result": {
            "is_valid": True,
            "validation_level": "pass",
            "risk_score": 0,
            "safe_to_create_workouts": True,
            "safe_to_schedule": True,
        },
        "created_workouts": [],
        "scheduled_workouts": [],
        "final_response_summary": {
            "mentioned_uncertainty": True,
            "explained_reasoning": True,
            "invented_metrics": False,
        },
    }
    result = audit_coach_mediator_session("daily_workout_decision", trace)

    assert result["overall_status"] in {"pass", "warning"}
    assert result["protocol_score"] >= 95
    assert result["safety_score"] == 100
    assert result["data_integrity_score"] == 100
    assert not any(w["code"] == "checkin_missing" for w in result["warnings"])
    assert not any(w["code"] == "daily_brief_missing" for w in result["warnings"])
    assert "plan_triathlon_week" not in result["missing_steps"]
    assert "get_daily_training_brief" not in result["missing_steps"]
    assert "subjective_checkin" not in result["missing_steps"]
    gap_codes = {g["code"] for g in result["data_gaps"]}
    assert "daily_brief_empty" in gap_codes
    assert "dry_run_respected_no_create_or_schedule" in result["positive_signals"]


def test_normalize_session_trace_accepts_aliases():
    trace = normalize_session_trace({
        "tools_called": [
            "get_daily_training_brief(2026-06-16)",
            "plan_triathlon_week",
        ],
        "subjective_checkin": {
            "pain": {"has_pain": "yes"},
            "fatigue_0_10": 2,
            "available_minutes": 45,
            "schedule_constraints": "none",
        },
        "brief_summary": {"readiness_level": None},
        "adjust_result": {"decision": "modify"},
        "validation_result": {"validation_level": "pass"},
        "mode": "dry_run",
    })
    assert trace["tool_sequence"][0].startswith("get_daily_training_brief")
    assert trace["user_checkin"]["provided"] is True
    assert trace["daily_training_brief_summary"]["readiness_level"] is None
    assert trace["adjust_today_workout_result"]["decision"] == "modify"
    assert trace["dry_run"] is True
