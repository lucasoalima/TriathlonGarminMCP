import pytest

from triathlon_coach.engine import (
    adjust_today_workout,
    classify_completed_activity,
    classify_unplanned_activity,
    plan_training_block,
    validate_training_decision,
    weekly_coach_review,
)


def _planned_day(primary_intensity="easy", primary_type="endurance", duration=45):
    return {
        "day": "monday",
        "date": "2026-06-15",
        "primary": {
            "suggested": {
                "sport": "run",
                "type": primary_type,
                "intensity": primary_intensity,
                "duration_minutes": duration,
            },
        },
        "secondary": {"enabled": False, "options": []},
        "complement": {
            "category": "strength",
            "required": True,
            "suggested": {"duration_minutes": 30},
        },
    }


def _brief(readiness=70, sleep_hours=7.5, hrv_status="balanced", tsb=0, recovery_h=12):
    return {
        "morning_readiness": {"readiness_score": readiness, "recovery_time_hours": recovery_h},
        "sleep": {"sleep_hours": sleep_hours},
        "hrv": {"status": hrv_status},
        "training_load": {"tsb": tsb},
    }


# --- adjust_today_workout ---


def test_adjust_low_readiness_removes_secondary():
    result = adjust_today_workout(_planned_day(), daily_training_brief=_brief(readiness=40))
    assert "secondary" in {a["target"] for a in result["recommended_adjustments"]}
    assert "hard_intervals" in result["blocked_actions"]
    assert "low_readiness" in result["risk_flags"]


def test_adjust_poor_sleep_blocks_hard():
    result = adjust_today_workout(_planned_day(), daily_training_brief=_brief(sleep_hours=5.5))
    assert "poor_sleep" in result["risk_flags"]
    assert "hard_intervals" in result["blocked_actions"]
    assert "double_session" in result["blocked_actions"]


def test_adjust_pain_blocks_running():
    checkin = {
        "pain": {"has_pain": True, "severity_0_10": 3},
        "fatigue_0_10": 4,
        "available_minutes": 60,
        "schedule_constraints": "nenhuma",
    }
    result = adjust_today_workout(_planned_day(), subjective_checkin=checkin)
    assert "pain_reported" in result["risk_flags"]
    assert "running" in result["blocked_actions"]


def test_adjust_pain_unknown_requires_confirmation():
    checkin = {
        "fatigue_0_10": 4,
        "available_minutes": 60,
        "schedule_constraints": "nenhuma",
    }
    result = adjust_today_workout(_planned_day(), subjective_checkin=checkin)
    assert "pain_unknown" in result["risk_flags"] or "checkin_incomplete" in result["risk_flags"]
    assert "pain" in result.get("requires_user_confirmation_before", []) or "pain" in (
        result.get("checkin_status", {}).get("missing_required_fields") or []
    )


def test_adjust_incomplete_checkin_flags():
    result = adjust_today_workout(_planned_day(), subjective_checkin={})
    assert result["checkin_status"]["checkin_complete"] is False
    assert "checkin_incomplete" in result["risk_flags"]


def test_adjust_severe_pain_stop():
    checkin = {
        "pain": {"has_pain": True, "severity_0_10": 7},
        "fatigue_0_10": 4,
        "available_minutes": 60,
        "schedule_constraints": "nenhuma",
    }
    result = adjust_today_workout(_planned_day(), subjective_checkin=checkin)
    assert result["recommendation_level"] == "stop"
    assert result["decision"] == "rest"


def test_adjust_primary_long_blocks_secondary():
    day = _planned_day(primary_type="long", duration=70)
    result = adjust_today_workout(day)
    assert "primary_session_is_long_or_hard" in result["risk_flags"]
    assert any(a["target"] == "secondary" for a in result["recommended_adjustments"])


def test_adjust_high_fatigue_recommends_reduce():
    result = adjust_today_workout(_planned_day(), subjective_checkin={"fatigue_0_10": 8})
    assert result["decision"] in {"reduce", "modify", "rest"}
    assert "high_fatigue" in result["risk_flags"]
    assert any(a["action"] == "replace_strength_with_mobility" for a in result["recommended_adjustments"])


def test_adjust_previous_hard_blocks_hard_today():
    result = adjust_today_workout(
        _planned_day(),
        recent_context={"previous_day_had_hard_session": True},
    )
    assert "hard_intervals" in result["blocked_actions"]
    assert "previous_session_was_hard" in result["risk_flags"]


def test_adjust_available_minutes_suggests_shorten():
    result = adjust_today_workout(
        _planned_day(duration=60),
        subjective_checkin={"available_minutes": 35},
    )
    assert any(a["action"] == "shorten" for a in result["recommended_adjustments"])
    assert "time_constraint" in result["reason_codes"]


def test_adjust_has_claude_mediator_hint():
    result = adjust_today_workout(_planned_day())
    assert "claude_mediator_hint" in result
    assert "decision_style" in result["claude_mediator_hint"]


# --- validate_training_decision ---


def test_validate_blocks_hard_with_low_readiness():
    sessions = [{"sport": "run", "type": "interval", "intensity": "hard", "priority": "primary"}]
    ctx = {"readiness_level": "low", "sleep_hours": 7, "pain_reported": False}
    result = validate_training_decision(sessions, ctx)
    assert result["validation_level"] == "blocked"
    assert "hard_session_with_low_readiness" in result["violations"]
    assert result["safe_to_schedule"] is False


def test_validate_blocks_secondary_with_low_readiness():
    sessions = [
        {"sport": "run", "type": "endurance", "intensity": "easy", "priority": "primary"},
        {"sport": "bike", "type": "recovery", "intensity": "easy", "priority": "secondary"},
    ]
    ctx = {"readiness_level": "low"}
    result = validate_training_decision(sessions, ctx)
    assert "secondary_not_allowed_with_low_readiness" in result["violations"]


def test_validate_blocks_swim_on_sunday():
    sessions = [{"sport": "swim", "type": "endurance", "intensity": "easy", "priority": "primary"}]
    ctx = {"day": "sunday", "readiness_level": "normal"}
    result = validate_training_decision(sessions, ctx)
    assert "swim_on_forbidden_day" in result["violations"]


def test_validate_blocks_consecutive_hard_days():
    sessions = [{"sport": "bike", "type": "interval", "intensity": "hard", "priority": "primary"}]
    ctx = {"previous_day_hard": True, "readiness_level": "normal"}
    result = validate_training_decision(sessions, ctx)
    assert "hard_on_consecutive_days" in result["violations"]


def test_validate_blocks_run_with_pain():
    sessions = [{"sport": "run", "type": "endurance", "intensity": "easy", "priority": "primary"}]
    ctx = {"pain_reported": True, "readiness_level": "normal"}
    result = validate_training_decision(sessions, ctx)
    assert "running_with_pain_reported" in result["violations"]


def test_validate_warns_excess_hard_sessions():
    sessions = [{"sport": "bike", "type": "interval", "intensity": "hard", "priority": "primary"}]
    ctx = {"readiness_level": "normal"}
    weekly = {"hard_sessions_so_far": 1}
    result = validate_training_decision(sessions, ctx, weekly_context=weekly)
    assert "hard_sessions_exceed_weekly_target" in result["warnings"]
    assert result["validation_level"] == "warning"


def test_validate_warns_pain_unknown_before_run():
    sessions = [{"sport": "run", "type": "endurance", "intensity": "easy", "priority": "primary"}]
    ctx = {"readiness_level": "normal", "pain_status": "unknown"}
    result = validate_training_decision(sessions, ctx)
    assert "pain_status_unknown_confirm_before_running" in result["warnings"]
    assert result["validation_level"] in {"warning", "pass"}


def test_validate_passes_easy_session():
    sessions = [
        {"sport": "bike", "type": "endurance", "intensity": "easy", "priority": "primary"},
    ]
    ctx = {"readiness_level": "normal", "sleep_hours": 7.5, "pain_reported": False}
    result = validate_training_decision(sessions, ctx)
    assert result["validation_level"] == "pass"
    assert result["safe_to_create_workouts"] is True


# --- classify_completed_activity ---


def test_classify_bike_easy_z3_z4_dominant_user_example():
    planned = {
        "sport": "bike",
        "type": "endurance",
        "duration_minutes": 60,
        "intensity": "easy",
        "target": {"mode": "hr_zone", "zone": "Z2"},
    }
    completed = {
        "sport": "bike",
        "duration_minutes": 66,
        "avg_hr_zone": "Z3",
        "max_hr_zone": "Z4",
        "hr_zone_distribution": {"Z1": 5, "Z2": 25, "Z3": 55, "Z4": 15, "Z5": 0},
    }
    result = classify_completed_activity(planned, completed)
    assert result["status"] == "completed"
    assert result["execution_quality"] == "too_hard"
    assert result["duration_match"] == "matched"
    assert result["intensity_match"] == "higher_than_planned"
    assert result["sport_match"] == "matched"
    assert "intensity_too_high_for_easy_day" in result["risk_flags"]
    assert "z3_z4_dominant_on_easy_session" in result["risk_flags"]
    assert "monitor_fatigue" in result["impact_on_next_plan"]
    assert "avoid_hard_session_next_day" in result["impact_on_next_plan"]
    assert "easy/Z2" in result["coach_interpretation"] or "harder than prescribed" in result["coach_interpretation"]


def test_classify_completed_good_z1_z2_distribution():
    planned = {
        "sport": "bike",
        "type": "endurance",
        "duration_minutes": 60,
        "intensity": "easy",
        "target": {"mode": "hr_zone", "zone": "Z2"},
    }
    completed = {
        "sport": "bike",
        "duration_minutes": 62,
        "avg_hr_zone": "Z2",
        "hr_zone_distribution": {"Z1": 20, "Z2": 65, "Z3": 10, "Z4": 5, "Z5": 0},
    }
    result = classify_completed_activity(planned, completed)
    assert result["status"] == "completed"
    assert result["execution_quality"] == "good"
    assert result["intensity_match"] == "matched"


def test_classify_completed_good():
    planned = {
        "sport": "bike",
        "type": "endurance",
        "duration_minutes": 60,
        "intensity": "easy",
        "target": {"mode": "hr_zone", "zone": "Z2"},
    }
    completed = {
        "sport": "bike",
        "duration_minutes": 62,
        "avg_hr_zone": "Z2",
    }
    result = classify_completed_activity(planned, completed)
    assert result["status"] == "completed"
    assert result["execution_quality"] == "good"


def test_classify_completed_too_hard_avg_zone_only():
    planned = {
        "sport": "bike",
        "type": "endurance",
        "duration_minutes": 60,
        "intensity": "easy",
        "target": {"mode": "hr_zone", "zone": "Z2"},
    }
    completed = {
        "sport": "bike",
        "duration_minutes": 60,
        "avg_hr_zone": "Z4",
        "max_hr_zone": "Z4",
    }
    result = classify_completed_activity(planned, completed)
    assert result["status"] == "completed"
    assert result["execution_quality"] == "too_hard"
    assert result["intensity_match"] == "higher_than_planned"
    assert "intensity_too_high_for_easy_day" in result["risk_flags"]


def test_classify_run_easy_too_hard_more_conservative():
    planned = {
        "sport": "run",
        "type": "endurance",
        "duration_minutes": 40,
        "intensity": "easy",
        "target": {"mode": "hr_zone", "zone": "Z2"},
    }
    completed = {
        "sport": "run",
        "duration_minutes": 40,
        "avg_hr_zone": "Z3",
        "hr_zone_distribution": {"Z1": 10, "Z2": 30, "Z3": 40, "Z4": 20, "Z5": 0},
    }
    result = classify_completed_activity(planned, completed)
    assert result["execution_quality"] == "too_hard"
    assert "run_executed_harder_than_planned" in result["risk_flags"]


def test_classify_no_hr_zones_intensity_unknown():
    planned = {"sport": "bike", "type": "endurance", "duration_minutes": 60, "intensity": "easy"}
    completed = {"sport": "bike", "duration_minutes": 60}
    result = classify_completed_activity(planned, completed)
    assert result["intensity_match"] == "unknown"
    assert result["status"] == "completed"


def test_classify_too_long():
    planned = {"sport": "bike", "type": "long", "duration_minutes": 90, "intensity": "easy"}
    completed = {"sport": "bike", "duration_minutes": 115, "avg_hr_zone": "Z2"}
    result = classify_completed_activity(planned, completed)
    assert result["duration_match"] in {"long", "very_long"}
    assert result["execution_quality"] == "too_long"
    assert "duration_above_planned" in result["risk_flags"] or "duration_exceeded_planned" in result["risk_flags"]


def test_classify_recovery_too_hard():
    planned = {
        "sport": "run",
        "type": "recovery",
        "duration_minutes": 30,
        "intensity": "recovery",
        "target": {"mode": "hr_zone", "zone": "Z1"},
    }
    completed = {
        "sport": "run",
        "duration_minutes": 30,
        "hr_zone_distribution": {"Z1": 20, "Z2": 30, "Z3": 40, "Z4": 10, "Z5": 0},
    }
    result = classify_completed_activity(planned, completed)
    assert result["execution_quality"] in {"too_hard", "risky"}
    assert "recovery_session_too_hard" in result["risk_flags"]


def test_classify_strength_skips_hr():
    planned = {"sport": "strength", "type": "general_strength", "duration_minutes": 30, "intensity": "moderate"}
    completed = {"sport": "strength", "duration_minutes": 32, "avg_hr_zone": "Z4"}
    result = classify_completed_activity(planned, completed)
    assert result["intensity_match"] == "unknown"
    assert "intensity_too_high_for_easy_day" not in result["risk_flags"]


def test_classify_partial_acceptable():
    planned = {"sport": "run", "type": "endurance", "duration_minutes": 40, "intensity": "easy"}
    completed = {"sport": "run", "duration_minutes": 25}
    result = classify_completed_activity(planned, completed)
    assert result["status"] == "partial"
    assert result["duration_match"] == "short"
    assert result["execution_quality"] == "acceptable"


def test_classify_substituted_sport():
    planned = {"sport": "run", "type": "endurance", "duration_minutes": 40, "intensity": "easy"}
    completed = {"sport": "bike", "duration_minutes": 40}
    result = classify_completed_activity(planned, completed)
    assert result["status"] == "substituted"
    assert result["sport_match"] == "substituted"


def test_classify_unplanned():
    result = classify_unplanned_activity({"sport": "run", "duration_minutes": 30})
    assert result["status"] == "unplanned"


def test_classify_unknown_insufficient_data():
    result = classify_completed_activity(
        {"sport": "run", "duration_minutes": 40},
        {},
    )
    assert result["execution_quality"] == "unknown"
    assert "insufficient_data" in result["risk_flags"]


# --- weekly_coach_review ---


def test_weekly_review_no_increase_low_compliance():
    result = weekly_coach_review(
        "2026-06-09",
        "2026-06-15",
        compliance_data={"summary": {"scheduled": 8, "completed": 5, "compliance_rate": 0.62}},
        auto_fetch=False,
    )
    assert result["next_week_recommendation"]["load_change"] != "small_increase"
    assert "compliance_below_target" in result["risk_flags"]


def test_weekly_review_pain_suggests_reduce():
    result = weekly_coach_review(
        "2026-06-09",
        "2026-06-15",
        compliance_data={"summary": {"scheduled": 6, "completed": 5, "compliance_rate": 0.83}},
        pain_reported_this_week=True,
        auto_fetch=False,
    )
    assert result["load_decision"] == "reduce"
    assert "pain_reported" in result["risk_flags"]


def test_weekly_review_too_hard_easy_sessions():
    result = weekly_coach_review(
        "2026-06-09",
        "2026-06-15",
        compliance_data={"summary": {"scheduled": 6, "completed": 6, "compliance_rate": 0.9}},
        execution_classifications=[
            {"execution_quality": "too_hard"},
            {"execution_quality": "too_hard"},
        ],
        auto_fetch=False,
    )
    assert "easy_sessions_executed_too_hard" in result["risk_flags"]
    assert result["load_decision"] == "reduce"


def test_weekly_review_good_week_maintain_or_increase():
    result = weekly_coach_review(
        "2026-06-09",
        "2026-06-15",
        compliance_data={"summary": {"scheduled": 6, "completed": 6, "compliance_rate": 0.9}},
        activities_summary={"sport_distribution": {"run": 90, "bike": 120, "swim": 60, "strength": 30}},
        wellness_summary={"sleep_stable": True, "hrv_not_suppressed": True},
        execution_classifications=[
            {"execution_quality": "good"},
            {"execution_quality": "good"},
            {"execution_quality": "acceptable"},
        ],
        auto_fetch=False,
    )
    assert result["overall_status"] in {"progress", "maintain"}
    assert result["claude_mediator_hint"]["questions_to_ask_user"]


def test_weekly_review_sport_distribution():
    result = weekly_coach_review(
        "2026-06-09",
        "2026-06-15",
        activities_summary={
            "sport_distribution": {"run": 120, "bike": 150, "swim": 60},
            "total_training_minutes": 330,
        },
        auto_fetch=False,
    )
    assert result["summary_metrics"]["sport_distribution"]["bike"] == 150


# --- plan_training_block skeleton ---


def test_weekly_review_fetch_tolerates_invalid_scheduled(monkeypatch):
    from unittest.mock import Mock
    import pytest as _pytest; _pytest.importorskip("garmin_mcp.coach_weekly_data")
    from garmin_mcp import coach_weekly_data

    mock_client = Mock()
    mock_client.query_garmin_graphql = Mock(return_value={"data": {"workoutScheduleSummariesScalar": Mock()}})
    mock_client.connectapi = Mock(return_value=[])
    mock_client.get_sleep_data = Mock(return_value={})
    mock_client.get_hrv_data = Mock(return_value={})
    mock_client.get_morning_training_readiness = Mock(return_value={})
    mock_client.get_training_status = Mock(return_value={})
    coach_weekly_data.configure(mock_client)

    result = coach_weekly_data.fetch_weekly_garmin_context("2026-06-09", "2026-06-15")
    assert isinstance(result.get("scheduled_workout_count"), int)
    assert "scheduled_workouts_unavailable_or_invalid" in result.get("data_gaps", [])


def test_weekly_review_auto_mode_with_fetch(monkeypatch):
    import pytest as _pytest; _pytest.importorskip("garmin_mcp.coach_weekly_data")
    from garmin_mcp import coach_weekly_data

    coach_weekly_data.configure(object())

    def fake_fetch(ws, we):
        return {
            "compliance_data": {
                "summary": {"scheduled": 6, "completed": 5, "partial": 1, "missed": 0, "compliance_rate": 0.83},
            },
            "activities_summary": {
                "sport_distribution": {"run": 90, "bike": 120, "swim": 60},
                "total_training_minutes": 270,
                "swim_sessions": 2,
                "activity_count": 6,
            },
            "wellness_summary": {"sleep_stable": True, "hrv_not_suppressed": True},
            "execution_classifications": [{"execution_quality": "good"}],
            "data_gaps": [],
        }

    monkeypatch.setattr(coach_weekly_data, "fetch_weekly_garmin_context", fake_fetch)
    result = weekly_coach_review("2026-06-09", "2026-06-15", auto_fetch=True)
    assert result["data_mode"] == "auto"
    assert result["summary_metrics"]["compliance_rate"] == 0.83
    assert result["summary_metrics"]["sport_distribution"]["bike"] == 120


def test_weekly_review_hybrid_manual_overrides(monkeypatch):
    import pytest as _pytest; _pytest.importorskip("garmin_mcp.coach_weekly_data")
    from garmin_mcp import coach_weekly_data

    coach_weekly_data.configure(object())

    monkeypatch.setattr(
        coach_weekly_data,
        "fetch_weekly_garmin_context",
        lambda ws, we: {
            "compliance_data": {"summary": {"scheduled": 4, "completed": 2, "compliance_rate": 0.5}},
            "activities_summary": {"sport_distribution": {"run": 30}},
            "wellness_summary": {},
            "data_gaps": [],
        },
    )
    manual = {"sport_distribution": {"bike": 200}, "total_training_minutes": 200}
    result = weekly_coach_review(
        "2026-06-09",
        "2026-06-15",
        activities_summary=manual,
        auto_fetch=True,
    )
    assert result["data_mode"] == "hybrid"
    assert result["summary_metrics"]["sport_distribution"]["bike"] == 200


def test_plan_training_block_skeleton():
    block = plan_training_block("2026-06-15", weeks=4)
    assert block["block_type"] == "base_foundation"
    assert block["target"] == "ironman_70_3"
    assert len(block["week_outline"]) == 4
