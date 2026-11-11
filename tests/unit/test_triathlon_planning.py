import pytest

from triathlon_coach.planning import build_triathlon_week_template


def _day(plan, name):
    return next(d for d in plan["days"] if d["day"] == name)


def _complement_categories_in_week(plan):
    cats = {"strength": 0, "core": 0, "prehab": 0, "mobility": 0}
    for day in plan["days"]:
        comp = day.get("complement")
        if not comp:
            continue
        cat = comp.get("category")
        if cat in cats and comp.get("required", True):
            cats[cat] += 1
    return cats


def _days_with_complement_option_category(plan, category):
    count = 0
    for day in plan["days"]:
        comp = day.get("complement")
        if not comp:
            continue
        if any(o.get("category") == category for o in comp.get("options", [])):
            count += 1
    return count


def test_returns_seven_days():
    plan = build_triathlon_week_template("2026-06-15")
    assert len(plan["days"]) == 7
    assert plan["week_start"] == "2026-06-15"
    assert plan["week_end"] == "2026-06-21"


def test_garmin_upload_false():
    plan = build_triathlon_week_template("2026-06-15")
    assert plan["garmin_upload"] is False
    assert plan["sends_to_garmin"] is False


def test_goal_ironman_70_3_performance_focus():
    plan = build_triathlon_week_template("2026-06-15")
    assert plan["goal"]["long_term_goal"] == "ironman_70_3"
    focuses = plan["goal"]["current_focus"]
    assert "performance" in focuses
    assert "aerobic_base" in focuses
    assert "durability" in focuses
    assert "weight_loss" not in focuses
    assert "fat_loss" not in focuses


def test_no_weight_loss_in_plan():
    plan = build_triathlon_week_template("2026-06-15")
    blob = str(plan).lower()
    assert "weight_loss" not in blob
    assert "fat_loss" not in blob


def test_top_level_coaching_structure():
    plan = build_triathlon_week_template("2026-06-15")
    assert plan["plan_type"] == "triathlon_week_template"
    assert "weekly_guardrails" in plan
    assert "adjustment_rules" in plan
    assert "key_sessions" in plan
    assert "coach_flow_hint" in plan
    assert "swim_policy" in plan
    assert "secondary_policy" in plan
    assert plan["secondary_policy"]["default"] == "optional"


def test_coach_engine_contract_and_policies():
    plan = build_triathlon_week_template("2026-06-15")
    contract = plan["coach_engine_contract"]
    assert contract["mcp_role"] == "technical_rules_engine"
    assert contract["requires_adjust_today_workout_before_materializing_daily_workout"] is True
    assert contract["requires_validate_training_decision_before_schedule"] is True
    assert "performance_policy" in plan
    assert "progression_policy" in plan
    assert "discipline_guardrails" in plan
    assert "fueling_policy" in plan
    assert plan["performance_policy"]["priority"] == "sustainable_performance_development"


def test_sunday_no_swim():
    plan = build_triathlon_week_template("2026-06-15")
    sunday = _day(plan, "sunday")
    assert sunday.get("recovery") is not None
    assert sunday["recovery"]["no_swim"] is True
    for opt in sunday["recovery"]["options"]:
        assert opt["sport"] != "swim"


def test_friday_not_forced_rest():
    friday = _day(build_triathlon_week_template("2026-06-15"), "friday")
    assert friday.get("primary") is not None
    assert friday["primary"]["required"] is True
    sports = {o["sport"] for o in friday["primary"]["options"]}
    assert sports == {"run", "bike"}
    assert "rest" not in sports


def test_tuesday_thursday_swim_primary():
    plan = build_triathlon_week_template("2026-06-15")
    for name in ("tuesday", "thursday"):
        day = _day(plan, name)
        assert day["primary"]["suggested"]["sport"] == "swim"


def test_saturday_long_and_optional_swim_secondary():
    saturday = _day(build_triathlon_week_template("2026-06-15"), "saturday")
    primary_types = {o["type"] for o in saturday["primary"]["options"]}
    assert primary_types == {"long"}
    secondary_sports = {o["sport"] for o in saturday["secondary"]["options"]}
    assert "swim" in secondary_sports
    assert "run" in secondary_sports
    assert "bike" in secondary_sports
    assert saturday["secondary"]["enabled"] is False


def test_two_strength_sessions_default():
    plan = build_triathlon_week_template("2026-06-15")
    cats = _complement_categories_in_week(plan)
    assert cats["strength"] == 2


def test_core_prehab_mobility_present():
    plan = build_triathlon_week_template("2026-06-15")
    cats = _complement_categories_in_week(plan)
    assert cats["core"] >= 1
    assert cats["prehab"] >= 1
    assert cats["mobility"] >= 1
    assert _days_with_complement_option_category(plan, "core") >= 2
    assert _days_with_complement_option_category(plan, "prehab") >= 2
    assert _days_with_complement_option_category(plan, "mobility") >= 2


def test_secondary_optional_policy():
    plan = build_triathlon_week_template("2026-06-15")
    monday = _day(plan, "monday")
    assert monday["secondary"]["enabled"] is False
    assert monday["secondary"]["policy"] == "optional_only_if_readiness_is_good"
    assert plan["summary"]["secondary_enabled_by_default"] is False


def test_day_blocks_primary_secondary_complement():
    monday = _day(build_triathlon_week_template("2026-06-15"), "monday")
    assert "primary" in monday
    assert "secondary" in monday
    assert "complement" in monday
    assert monday["complement"]["category"] == "strength"
    assert monday["complement"]["required"] is True


def test_wednesday_conservative_not_hard():
    wednesday = _day(build_triathlon_week_template("2026-06-15"), "wednesday")
    for opt in wednesday["primary"]["options"]:
        assert opt["intensity"] == "easy_to_moderate"
        assert opt["intensity"] != "hard"


def test_key_sessions_present():
    plan = build_triathlon_week_template("2026-06-15")
    reasons = {ks["reason"] for ks in plan["key_sessions"]}
    assert "main_endurance_session" in reasons
    assert "technique_and_aerobic_swim_development" in reasons
    assert "main_midweek_aerobic_stimulus" in reasons


def test_guardrails_conservative():
    plan = build_triathlon_week_template("2026-06-15")
    g = plan["weekly_guardrails"]
    assert g["do_not_auto_add_volume"] is True
    assert g["max_long_sessions"] == 1
    assert g["strength_sessions_target"] == 2
    assert g["secondary_sessions_are_optional"] is True


def test_swim_policy():
    plan = build_triathlon_week_template("2026-06-15")
    assert plan["swim_policy"]["forbidden_days"] == ["sunday"]
    assert "tuesday" in plan["swim_policy"]["preferred_days"]
    assert "saturday" in plan["swim_policy"]["optional_days"]
    assert plan["swim_policy"]["do_not_invent_css"] is True


def test_sunday_recovery_default():
    sunday = _day(build_triathlon_week_template("2026-06-15"), "sunday")
    assert sunday["recovery"]["suggested"]["sport"] == "rest"


def test_sunday_recovery_run_preference():
    plan = build_triathlon_week_template(
        "2026-06-15",
        preferences={"sunday_default": "recovery_run"},
    )
    sunday = _day(plan, "sunday")
    assert sunday["recovery"]["suggested_id"] == "recovery_run"


def test_week_start_any_day_maps_correct_weekday():
    plan = build_triathlon_week_template("2026-06-16")
    tuesday = _day(plan, "tuesday")
    assert tuesday["primary"]["suggested"]["sport"] == "swim"


def test_invalid_week_start_raises():
    with pytest.raises(ValueError):
        build_triathlon_week_template("not-a-date")
