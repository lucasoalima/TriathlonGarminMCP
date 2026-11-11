"""
Triathlon coach engine — deterministic rules layer for Garmin MCP.

Computes, validates, classifies and flags. Does NOT make final coaching decisions
or produce motivational messages; Claude/Cursor remains the mediator.
"""

from __future__ import annotations

import datetime
from copy import deepcopy
from typing import Any, Dict, List, Optional, Union

from triathlon_coach.checkin import (
    checkin_required_before,
    normalize_subjective_checkin,
)

# Dependência OPCIONAL: só é necessária para o auto-fetch de dados do Garmin, que
# só existe quando este motor roda dentro do servidor MCP completo (Taxuspt/garmin_mcp).
# No repositório focado (lógica pura + avaliação) ela está ausente e tudo funciona offline.
try:  # pragma: no cover
    from garmin_mcp import coach_weekly_data  # type: ignore
except Exception:  # pragma: no cover
    coach_weekly_data = None  # type: ignore

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

DEFAULT_ATHLETE_PROFILE: Dict[str, Any] = {
    "level": "beginner_returning",
    "main_goal": "ironman_70_3_long_term",
    "current_focus": [
        "performance",
        "aerobic_base",
        "consistency",
        "durability",
        "injury_prevention",
        "return_to_performance",
    ],
    "aggressiveness": "conservative",
}

HARD_INTENSITIES = frozenset({"hard", "very_hard", "vo2", "threshold", "interval", "race"})
LONG_TYPES = frozenset({"long"})
EASY_INTENSITIES = frozenset({"easy", "recovery", "easy_to_moderate"})
MODERATE_INTENSITIES = frozenset({"moderate", "easy_to_moderate"})

SPORT_FAMILIES: Dict[str, frozenset] = {
    "run": frozenset({"run", "running", "trail_running", "treadmill_running"}),
    "bike": frozenset({"bike", "cycling", "indoor_cycling", "virtual_ride"}),
    "swim": frozenset({"swim", "swimming", "lap_swimming", "open_water_swimming"}),
    "strength": frozenset({"strength", "strength_training", "fitness_equipment"}),
}

SWIM_FORBIDDEN_DAYS = frozenset({"sunday"})

MEDIATOR_HINT_BASE: Dict[str, Any] = {
    "summary": "Use this output as technical constraints, not as the final coaching message.",
    "decision_style": "Claude should explain the tradeoff and choose the final workout.",
}


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def _sport_family(sport: str) -> str:
    s = _norm(sport)
    for family, members in SPORT_FAMILIES.items():
        if s in members or s == family:
            return family
    return s


def _is_hard(intensity: str, session_type: str = "") -> bool:
    i = _norm(intensity)
    t = _norm(session_type)
    return i in HARD_INTENSITIES or t in {"interval", "hard", "vo2", "threshold", "race"}


def _is_long(session_type: str, duration_minutes: Optional[int] = None) -> bool:
    if _norm(session_type) in LONG_TYPES:
        return True
    return duration_minutes is not None and duration_minutes >= 65


def _readiness_score(brief: Optional[dict]) -> Optional[float]:
    if not brief:
        return None
    morning = brief.get("morning_readiness") or {}
    readiness = brief.get("readiness") or {}
    for key in ("readiness_score", "score"):
        val = morning.get(key) or readiness.get(key)
        if val is not None:
            return float(val)
    return None


def _sleep_hours(brief: Optional[dict]) -> Optional[float]:
    if not brief:
        return None
    sleep = brief.get("sleep") or {}
    if sleep.get("sleep_hours") is not None:
        return float(sleep["sleep_hours"])
    secs = sleep.get("sleep_seconds")
    return float(secs) / 3600.0 if secs else None


def _hrv_low(brief: Optional[dict]) -> bool:
    if not brief:
        return False
    hrv = brief.get("hrv") or {}
    status = _norm(hrv.get("status"))
    return "low" in status or "unbalanced" in status or "poor" in status


def _recovery_hours(brief: Optional[dict]) -> Optional[float]:
    if not brief:
        return None
    morning = brief.get("morning_readiness") or {}
    readiness = brief.get("readiness") or {}
    val = morning.get("recovery_time_hours") or readiness.get("recovery_time_hours")
    return float(val) if val is not None else None


def _tsb(brief: Optional[dict]) -> Optional[float]:
    if not brief:
        return None
    load = brief.get("training_load") or {}
    tsb = load.get("tsb")
    return float(tsb) if tsb is not None else None


def _primary_block(planned_day: dict) -> dict:
    return planned_day.get("primary") or {}


def _primary_suggested(planned_day: dict) -> dict:
    primary = _primary_block(planned_day)
    return primary.get("suggested") or {}


def _planned_primary_minutes(planned_day: dict) -> int:
    suggested = _primary_suggested(planned_day)
    comp = planned_day.get("complement") or {}
    comp_s = comp.get("suggested") or {}
    return int(
        suggested.get("duration_minutes", 0)
        + (comp_s.get("duration_minutes", 0) if comp.get("required", True) else 0)
    )


def _claude_mediator_hint(
    should_ask: Optional[List[str]] = None,
    summary: Optional[str] = None,
) -> Dict[str, Any]:
    hint = deepcopy(MEDIATOR_HINT_BASE)
    if summary:
        hint["summary"] = summary
    if should_ask:
        hint["should_ask_user"] = should_ask
    return hint


def _unique(items: List[str]) -> List[str]:
    seen: set = set()
    out: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


# ---------------------------------------------------------------------------
# 1. adjust_today_workout
# ---------------------------------------------------------------------------

def adjust_today_workout(
    planned_day: dict,
    daily_training_brief: Optional[dict] = None,
    subjective_checkin: Optional[dict] = None,
    recent_context: Optional[dict] = None,
    athlete_profile: Optional[dict] = None,
) -> dict:
    """Return structured technical guidance for today's planned training."""
    _ = {**DEFAULT_ATHLETE_PROFILE, **(athlete_profile or {})}
    checkin = normalize_subjective_checkin(subjective_checkin)
    context = recent_context or {}

    risk_flags: List[str] = []
    reason_codes: List[str] = []
    blocked: List[str] = []
    requires_confirmation: List[str] = []
    allowed: List[str] = [
        "keep_primary_easy",
        "keep_technique_swim",
        "do_mobility",
        "do_easy_bike",
        "do_core",
        "do_prehab",
    ]
    adjustments: List[dict] = []
    notes: List[str] = []
    ask_user: List[str] = []

    decision = "keep"
    confidence = "medium"
    rec_level = "normal"

    readiness = _readiness_score(daily_training_brief)
    sleep_h = _sleep_hours(daily_training_brief)
    recovery_h = _recovery_hours(daily_training_brief)
    tsb_val = _tsb(daily_training_brief)

    pain = checkin.get("pain") or {}
    pain_status = pain.get("status", "unknown")
    pain_severity = int(pain.get("severity_0_10") or 0)
    fatigue = checkin.get("fatigue_0_10")
    motivation = checkin.get("motivation_0_10")
    available_min = checkin.get("available_minutes")
    stress = checkin.get("stress_0_10")

    primary = _primary_suggested(planned_day)
    primary_intensity = _norm(primary.get("intensity"))
    primary_type = _norm(primary.get("type"))
    primary_sport = _primary_block(planned_day).get("suggested", {}).get("sport", "")
    primary_long_or_hard = _is_long(primary_type, primary.get("duration_minutes")) or _is_hard(
        primary_intensity, primary_type
    )

    session_tags: List[str] = []
    if _sport_family(primary_sport) == "run":
        session_tags.append("run")
    if primary_long_or_hard:
        session_tags.extend(["hard", "long"])
    if planned_day.get("secondary", {}).get("enabled"):
        session_tags.append("double")

    if not checkin.get("checkin_complete"):
        risk_flags.append("checkin_incomplete")
        reason_codes.append("missing_subjective_checkin")
        notes.append("Subjective check-in incomplete — Claude should ask required fields.")
        for field in checkin.get("missing_required_fields") or []:
            if field == "pain":
                ask_user.append("Está com alguma dor hoje?")
            elif field == "fatigue_0_10":
                ask_user.append("Fadiga de 0 a 10?")
            elif field == "available_minutes":
                ask_user.append("Quanto tempo disponível tem hoje?")
            elif field == "schedule_constraints":
                ask_user.append("Alguma restrição de agenda ou equipamento?")

    confirm_fields = checkin_required_before(checkin, session_tags)
    if confirm_fields:
        requires_confirmation.extend(confirm_fields)
        if "pain" in confirm_fields:
            risk_flags.append("pain_unknown")
            reason_codes.append("pain_status_unknown")
            notes.append("Pain status unknown — confirm before run/hard/long/double sessions.")
        if "available_minutes" in confirm_fields:
            reason_codes.append("available_time_unknown")
            notes.append("Available time unknown — confirm before long or double sessions.")

    prev_hard = bool(context.get("previous_day_had_hard_session"))
    prev_long = bool(context.get("previous_day_had_long_session"))
    run_load = _norm(context.get("recent_run_load_increase") or "normal")

    # --- Rule evaluation ---
    if readiness is not None and readiness < 50:
        risk_flags.append("low_readiness")
        reason_codes.append("readiness_below_threshold")
        blocked.extend(["hard_intervals", "long_run", "double_session", "heavy_leg_strength"])
        adjustments.append({
            "target": "secondary",
            "action": "remove",
            "reason": "secondary_not_recommended_today",
        })
        decision = "reduce"
        rec_level = "caution"
        notes.append("Secondary should not be added today.")
        allowed = [a for a in allowed if a not in ("keep_primary_easy",)]

    if sleep_h is not None and sleep_h < 6:
        risk_flags.append("poor_sleep")
        reason_codes.append("sleep_under_target")
        blocked.extend(["hard_intervals", "double_session"])
        if decision == "keep":
            decision = "modify"
        if rec_level == "normal":
            rec_level = "caution"

    if _hrv_low(daily_training_brief):
        risk_flags.append("low_hrv")
        reason_codes.append("hrv_suppressed")
        rec_level = "caution" if rec_level == "normal" else rec_level
        notes.append("HRV outside habitual range — prefer conservative intensity.")

    if recovery_h is not None and recovery_h > 24:
        blocked.extend(["hard_intervals", "long_run", "long_bike"])
        reason_codes.append("recovery_time_elevated")
        if decision == "keep":
            decision = "modify"

    if tsb_val is not None and tsb_val < -20:
        risk_flags.append("high_fatigue")
        reason_codes.append("tsb_very_negative")
        adjustments.append({
            "target": "primary",
            "action": "reduce_duration",
            "reason": "fatigue_or_low_readiness",
        })
        decision = "reduce"

    if pain_status == "yes":
        risk_flags.append("pain_reported")
        reason_codes.append("pain_reported")
        blocked.extend(["hard_intervals", "long_run", "double_session", "heavy_leg_strength", "running"])
        allowed = [a for a in allowed if "run" not in a]
        ask_user.append("Confirm pain location and whether running aggravates it.")
        notes.append("Claude should ask for pain details before allowing running.")
        if decision == "keep":
            decision = "modify"
        rec_level = "high_caution" if pain_severity < 6 else "stop"

    if pain_status == "unknown" and session_tags:
        requires_confirmation.extend(["running", "hard_intervals", "long_run", "long_bike", "double_session"])
        requires_confirmation = _unique(requires_confirmation)
        if decision == "keep":
            decision = "modify"
        rec_level = "caution" if rec_level == "normal" else rec_level

    if pain_status == "yes" and pain_severity >= 6:
        rec_level = "stop"
        decision = "rest"
        blocked.extend(["running", "hard_intervals", "long_run", "long_bike", "heavy_leg_strength"])
        allowed = ["do_mobility", "do_easy_bike"]
        reason_codes.append("pain_severity_high")
        notes.append("High pain severity — rest or manual review recommended.")

    if primary_long_or_hard:
        risk_flags.append("primary_session_is_long_or_hard")
        blocked.append("double_session")
        adjustments.append({
            "target": "secondary",
            "action": "remove",
            "reason": "primary_session_is_long_or_hard",
        })
        notes.append("Secondary blocked because primary is long or hard.")

    if prev_hard:
        risk_flags.append("previous_session_was_hard")
        reason_codes.append("previous_day_hard")
        blocked.extend(["hard_intervals"])
        if decision == "keep":
            decision = "modify"

    if prev_long and _sport_family(primary_sport) == "run":
        blocked.append("long_run")

    if run_load == "high":
        risk_flags.append("run_load_risk")
        reason_codes.append("run_load_increased")
        blocked.extend(["long_run", "hard_intervals"])
        notes.append("Recent run load increase — avoid long or hard running today.")

    if fatigue is not None and fatigue >= 7:
        risk_flags.append("high_fatigue")
        reason_codes.append("subjective_fatigue_high")
        adjustments.append({
            "target": "complement",
            "action": "replace_strength_with_mobility",
            "reason": "fatigue_or_low_readiness",
        })
        decision = "reduce" if decision == "keep" else decision
        rec_level = "caution" if rec_level == "normal" else rec_level

    if motivation is not None and motivation <= 4 and (readiness is None or readiness >= 50):
        allowed.append("short_easy_session")
        notes.append("Low motivation but readiness acceptable — short easy session is an option.")
        if decision == "keep":
            decision = "modify"

    if available_min is not None:
        planned_min = _planned_primary_minutes(planned_day)
        if planned_min > 0 and available_min < planned_min:
            adjustments.append({
                "target": "primary",
                "action": "shorten",
                "reason": "available_time_limited",
                "suggested_duration_minutes": max(20, int(available_min * 0.85)),
            })
            reason_codes.append("time_constraint")
            if decision == "keep":
                decision = "modify"
            ask_user.append("Confirm available time today.")

    if stress is not None and stress >= 8:
        reason_codes.append("high_stress")
        notes.append("High subjective stress — keep session simple and aerobic.")

    complement = planned_day.get("complement") or {}
    if _norm(complement.get("category")) == "strength" and "heavy_leg_strength" in blocked:
        adjustments.append({
            "target": "complement",
            "action": "replace_strength_with_mobility",
            "reason": "heavy_leg_strength_blocked",
        })

    # Finalize allowed/blocked unique
    blocked = _unique(blocked)
    allowed = _unique(allowed)

    if rec_level == "stop":
        confidence = "high"
    elif len(risk_flags) >= 3:
        confidence = "high"
        if decision == "keep":
            decision = "reduce"
    elif not risk_flags and decision == "keep":
        confidence = "high"

    if not ask_user:
        ask_user = ["Confirm how the body feels before finalizing intensity."]

    return {
        "decision": decision,
        "confidence": confidence,
        "recommendation_level": rec_level,
        "allowed_actions": allowed,
        "blocked_actions": blocked,
        "requires_user_confirmation_before": _unique(requires_confirmation),
        "recommended_adjustments": adjustments,
        "risk_flags": _unique(risk_flags),
        "reason_codes": _unique(reason_codes),
        "checkin_status": checkin,
        "coach_engine_notes": notes,
        "claude_mediator_hint": _claude_mediator_hint(should_ask=ask_user),
    }


# ---------------------------------------------------------------------------
# 2. validate_training_decision
# ---------------------------------------------------------------------------

def _session_intensity(session: dict) -> str:
    return _norm(session.get("intensity"))


def _session_type(session: dict) -> str:
    return _norm(session.get("type"))


def _count_hard_sessions(sessions: List[dict]) -> int:
    return sum(
        1 for s in sessions
        if _is_hard(_session_intensity(s), _session_type(s))
    )


def validate_training_decision(
    proposed_sessions: List[dict],
    day_context: dict,
    weekly_context: Optional[dict] = None,
    athlete_profile: Optional[dict] = None,
    *,
    manual_override_pain: bool = False,
) -> dict:
    """Safety gate before creating/scheduling workouts."""
    profile = {**DEFAULT_ATHLETE_PROFILE, **(athlete_profile or {})}
    weekly = weekly_context or {}
    conservative = profile.get("aggressiveness", "conservative") == "conservative"

    violations: List[str] = []
    warnings: List[str] = []
    suggested: List[str] = []
    risk_score = 0

    readiness_level = _norm(day_context.get("readiness_level") or "normal")
    sleep_h = day_context.get("sleep_hours")
    pain_status = _norm(day_context.get("pain_status") or "")
    if not pain_status and "pain_reported" in day_context:
        pain_status = "yes" if day_context.get("pain_reported") else "no"
    if not pain_status:
        pain_status = "unknown"
    prev_hard = bool(day_context.get("previous_day_hard"))
    day_name = _norm(day_context.get("day") or day_context.get("weekday") or "")

    primaries = [s for s in proposed_sessions if _norm(s.get("priority")) == "primary"]
    secondaries = [s for s in proposed_sessions if _norm(s.get("priority")) == "secondary"]
    complements = [s for s in proposed_sessions if _norm(s.get("priority")) == "complement"]

    hard_count = _count_hard_sessions(proposed_sessions)
    long_count = sum(
        1 for s in proposed_sessions
        if _is_long(_session_type(s), s.get("duration_minutes"))
    )

    low_readiness = readiness_level in {"low", "poor", "very_low"}

    if low_readiness and hard_count:
        violations.append("hard_session_with_low_readiness")
        suggested.append("convert_run_to_easy_bike")
        risk_score += 30

    if low_readiness and secondaries:
        violations.append("secondary_not_allowed_with_low_readiness")
        suggested.append("remove_secondary")
        risk_score += 25

    if sleep_h is not None and sleep_h < 6 and hard_count:
        violations.append("hard_session_after_poor_sleep")
        risk_score += 25

    if prev_hard and hard_count:
        violations.append("hard_on_consecutive_days")
        risk_score += 20

    if pain_status == "yes" and not manual_override_pain:
        for s in proposed_sessions:
            if _sport_family(s.get("sport", "")) == "run":
                violations.append("running_with_pain_reported")
                suggested.append("convert_run_to_easy_bike")
                risk_score += 40

    if pain_status == "unknown" and not manual_override_pain:
        for s in proposed_sessions:
            sport = _sport_family(s.get("sport", ""))
            if sport == "run" or _is_hard(_session_intensity(s), _session_type(s)):
                warnings.append("pain_status_unknown_confirm_before_running")
                risk_score += 15
                break
        if long_count or len(secondaries) >= 1:
            warnings.append("pain_status_unknown_confirm_before_long_or_double")
            risk_score += 10

    for s in proposed_sessions:
        if _sport_family(s.get("sport", "")) == "swim" and day_name in SWIM_FORBIDDEN_DAYS:
            violations.append("swim_on_forbidden_day")
            risk_score += 50

    week_hard = int(weekly.get("hard_sessions_so_far") or 0) + hard_count
    max_hard = 1 if conservative else 2
    if week_hard > max_hard:
        warnings.append("hard_sessions_exceed_weekly_target")
        risk_score += 15

    week_long = int(weekly.get("long_sessions_so_far") or 0) + long_count
    if week_long > 1:
        warnings.append("long_sessions_exceed_weekly_target")
        risk_score += 15

    if long_count >= 2 and conservative:
        violations.append("two_long_sessions_same_day")
        risk_score += 20

    run_sessions = [s for s in proposed_sessions if _sport_family(s.get("sport", "")) == "run"]
    leg_strength = [
        s for s in complements
        if _sport_family(s.get("sport", "")) == "strength"
        and _norm(s.get("type")) in {"leg_strength", "strength", "general_strength"}
        and _session_intensity(s) in MODERATE_INTENSITIES | HARD_INTENSITIES
    ]
    key_run = any(
        _is_hard(_session_intensity(s), _session_type(s)) or _is_long(_session_type(s), s.get("duration_minutes"))
        for s in run_sessions
    )
    if leg_strength and key_run:
        warnings.append("heavy_leg_strength_near_key_run")
        suggested.append("replace_strength_with_mobility")
        risk_score += 10

    run_so_far = int(weekly.get("run_sessions_so_far") or 0)
    if run_so_far >= 4 and any(_is_long(_session_type(s), s.get("duration_minutes")) for s in run_sessions):
        warnings.append("run_load_is_high_this_week")
        risk_score += 10

    risk_score = min(100, risk_score)
    if violations:
        level = "blocked"
        is_valid = False
        safe_create = False
        safe_schedule = False
    elif warnings:
        level = "warning"
        is_valid = True
        safe_create = True
        safe_schedule = True
    else:
        level = "pass"
        is_valid = True
        safe_create = True
        safe_schedule = True

    return {
        "is_valid": is_valid,
        "validation_level": level,
        "risk_score": risk_score,
        "violations": violations,
        "warnings": warnings,
        "suggested_changes": _unique(suggested),
        "safe_to_create_workouts": safe_create,
        "safe_to_schedule": safe_schedule,
    }


# ---------------------------------------------------------------------------
# 3. classify_completed_activity
# ---------------------------------------------------------------------------

STRENGTH_SPORTS = frozenset({"strength", "other"})
SWIM_SPORTS = frozenset({"swim"})
ACCEPTABLE_SUBSTITUTIONS = {
    ("run", "bike"),
    ("bike", "run"),
}


def _duration_ratio(planned_min: Optional[float], actual_min: Optional[float]) -> Optional[float]:
    if not planned_min or not actual_min or planned_min <= 0:
        return None
    return actual_min / planned_min


def _duration_match_label(ratio: Optional[float]) -> str:
    if ratio is None:
        return "unknown"
    if ratio >= 1.20:
        return "very_long"
    if ratio > 1.10:
        return "long"
    if ratio >= 0.70:
        return "matched"
    if ratio >= 0.40:
        return "short"
    return "very_short"


def _intensity_rank(zone: str) -> Optional[int]:
    z = _norm(zone)
    if z.startswith("z"):
        try:
            return int(z[1:])
        except ValueError:
            return None
    mapping = {
        "recovery": 1,
        "easy": 2,
        "easy_to_moderate": 3,
        "moderate": 3,
        "hard": 4,
        "very_hard": 5,
        "interval": 4,
        "threshold": 4,
    }
    return mapping.get(z)


def _normalize_zone_distribution(raw: Optional[dict]) -> Dict[str, float]:
    if not raw:
        return {}
    out: Dict[str, float] = {}
    for key, val in raw.items():
        k = _norm(key).upper()
        if not k.startswith("Z"):
            continue
        try:
            out[k] = float(val)
        except (TypeError, ValueError):
            continue
    return out


def _zone_time_pct(distribution: Dict[str, float], zones: List[str]) -> Optional[float]:
    if not distribution:
        return None
    total = sum(distribution.values())
    if total <= 0:
        return None
    selected = sum(distribution.get(z, 0) for z in zones)
    return round(selected / total * 100, 1)


def _planned_target_zone(planned_session: dict) -> Optional[str]:
    target = planned_session.get("target") or {}
    zone = target.get("zone")
    if zone:
        return _norm(zone).upper()
    intensity = _norm(planned_session.get("intensity"))
    if intensity in {"recovery", "easy"}:
        return "Z1" if intensity == "recovery" else "Z2"
    if intensity == "easy_to_moderate":
        return "Z2"
    if intensity in {"moderate", "hard"}:
        return "Z3" if intensity == "moderate" else "Z4"
    return None


def _is_easy_planned(planned_session: dict) -> bool:
    intensity = _norm(planned_session.get("intensity"))
    zone = _planned_target_zone(planned_session)
    if intensity in {"recovery", "easy"}:
        return True
    if zone in {"Z1", "Z2"}:
        return True
    return False


def _is_recovery_planned(planned_session: dict) -> bool:
    intensity = _norm(planned_session.get("intensity"))
    zone = _planned_target_zone(planned_session)
    return intensity == "recovery" or zone == "Z1"


def _assess_sport_match(planned_sport: str, actual_sport: str) -> str:
    if not planned_sport or not actual_sport:
        return "unknown"
    if planned_sport == actual_sport:
        return "matched"
    pair = (planned_sport, actual_sport)
    if pair in ACCEPTABLE_SUBSTITUTIONS:
        return "substituted"
    if planned_sport in STRENGTH_SPORTS or actual_sport in STRENGTH_SPORTS:
        return "mismatch" if planned_sport != actual_sport else "matched"
    return "substituted" if _sport_family(planned_sport) != _sport_family(actual_sport) else "same_family"


def _assess_duration(
    planned_session: dict,
    ratio: Optional[float],
    dur_match: str,
) -> tuple:
    """Return (status_hint, execution_quality, impacts, risks)."""
    impact: List[str] = []
    risks: List[str] = []
    execution = "acceptable"
    status_hint = "completed"

    if ratio is None:
        return status_hint, execution, impact, risks

    if ratio < 0.40:
        status_hint = "partial"
        execution = "too_short"
    elif ratio < 0.70:
        status_hint = "partial"
        execution = "acceptable"
    elif ratio > 1.20:
        execution = "too_long"
        impact.append("monitor_fatigue")
        risks.append("duration_exceeded_planned")
        if _is_long(_session_type(planned_session), planned_session.get("duration_minutes")):
            risks.append("long_session_exceeded_planned")
    elif ratio > 1.10:
        execution = "too_long"
        impact.append("monitor_fatigue")
        risks.append("duration_above_planned")

    return status_hint, execution, impact, risks


def _merge_execution(current: str, new: str) -> str:
    rank = {
        "good": 0,
        "acceptable": 1,
        "too_easy": 2,
        "too_short": 3,
        "too_long": 3,
        "too_hard": 4,
        "risky": 5,
        "wrong_sport": 6,
        "unknown": -1,
    }
    if rank.get(new, 1) > rank.get(current, 1):
        return new
    return current


def _assess_intensity_from_hr(
    planned_session: dict,
    completed_activity: dict,
    planned_sport: str,
) -> dict:
    """Analyze HR zones / training effect vs plan. Returns analysis dict."""
    result: Dict[str, Any] = {
        "intensity_match": "unknown",
        "execution_hint": "acceptable",
        "impact": [],
        "risks": [],
        "metrics_used": {},
    }

    if planned_sport in STRENGTH_SPORTS or _norm(planned_session.get("type")) in {
        "strength", "core", "mobility", "prehab", "general_strength", "leg_strength",
    }:
        result["intensity_match"] = "unknown"
        result["metrics_used"]["hr_skipped"] = "strength_or_complement_session"
        return result

    distribution = _normalize_zone_distribution(
        completed_activity.get("hr_zone_distribution")
        or completed_activity.get("hr_zones_time_pct")
    )
    avg_zone = _norm(completed_activity.get("avg_hr_zone") or "").upper()
    max_zone = _norm(completed_activity.get("max_hr_zone") or "").upper()
    avg_hr = completed_activity.get("avg_hr_bpm") or completed_activity.get("average_hr")
    max_hr = completed_activity.get("max_hr_bpm") or completed_activity.get("max_hr")
    training_effect = completed_activity.get("training_effect") or completed_activity.get("aerobic_te")

    planned_zone = _planned_target_zone(planned_session)
    planned_rank = _intensity_rank(planned_zone or _norm(planned_session.get("intensity")))
    actual_rank = _intensity_rank(avg_zone) if avg_zone else None

    result["metrics_used"] = {
        k: v for k, v in {
            "planned_zone": planned_zone,
            "avg_hr_zone": avg_zone or None,
            "max_hr_zone": max_zone or None,
            "avg_hr_bpm": avg_hr,
            "max_hr_bpm": max_hr,
            "hr_zone_distribution": distribution or None,
            "training_effect": training_effect,
        }.items() if v is not None
    }

    z3_z4_pct = _zone_time_pct(distribution, ["Z3", "Z4", "Z5"])
    z4_z5_pct = _zone_time_pct(distribution, ["Z4", "Z5"])
    above_z2_pct = _zone_time_pct(distribution, ["Z3", "Z4", "Z5"])
    z1_z2_pct = _zone_time_pct(distribution, ["Z1", "Z2"])

    run_conservative = planned_sport == "run"
    easy_z3_z4_threshold = 35.0 if run_conservative else 45.0
    easy_z3_dominant_threshold = 45.0 if run_conservative else 50.0

    has_hr_signal = bool(distribution or avg_zone or training_effect is not None)

    # --- Zone distribution (strongest signal) ---
    if distribution and (_is_easy_planned(planned_session) or _is_recovery_planned(planned_session)):
        z3_alone = _zone_time_pct(distribution, ["Z3"]) or 0
        if _is_recovery_planned(planned_session):
            if (above_z2_pct or 0) > 30:
                result["intensity_match"] = "higher_than_planned"
                result["execution_hint"] = "risky" if (z4_z5_pct or 0) > 10 else "too_hard"
                result["risks"].append("recovery_session_too_hard")
                result["impact"].extend(["monitor_fatigue", "avoid_hard_session_next_day"])
        elif (z3_z4_pct or 0) >= easy_z3_z4_threshold or z3_alone >= easy_z3_dominant_threshold:
            result["intensity_match"] = "higher_than_planned"
            result["execution_hint"] = "too_hard"
            result["risks"].append("intensity_too_high_for_easy_day")
            result["risks"].append("z3_z4_dominant_on_easy_session")
            result["impact"].extend([
                "monitor_fatigue",
                "avoid_hard_session_next_day",
                "consider_recovery_or_easy_session_next",
            ])
        elif (z1_z2_pct or 0) >= 70 and planned_rank and planned_rank <= 2:
            result["intensity_match"] = "matched"
            result["execution_hint"] = "good"

    # --- Average zone fallback ---
    elif avg_zone and planned_rank and actual_rank is not None:
        if actual_rank <= planned_rank:
            result["intensity_match"] = "matched" if actual_rank == planned_rank else "lower_than_planned"
            if actual_rank < planned_rank and _is_easy_planned(planned_session):
                result["execution_hint"] = "too_easy"
        elif actual_rank == planned_rank + 1:
            result["intensity_match"] = "higher_than_planned"
            if _is_easy_planned(planned_session) or _is_recovery_planned(planned_session):
                result["execution_hint"] = "too_hard"
                result["risks"].append("intensity_too_high_for_easy_day")
                result["impact"].extend(["monitor_fatigue", "avoid_hard_session_next_day"])
        else:
            result["intensity_match"] = "higher_than_planned"
            result["execution_hint"] = "too_hard"
            result["risks"].append("intensity_too_high_for_easy_day")
            result["impact"].extend([
                "monitor_fatigue",
                "avoid_hard_session_next_day",
                "consider_recovery_or_easy_session_next",
            ])

    # --- Max zone peak on easy day ---
    if max_zone in {"Z4", "Z5"} and (_is_easy_planned(planned_session) or _is_recovery_planned(planned_session)):
        if result["execution_hint"] not in {"too_hard", "risky"}:
            result["execution_hint"] = "risky"
        result["risks"].append("high_peak_intensity_on_easy_day")

    # --- Training effect supplement ---
    if training_effect is not None and (_is_easy_planned(planned_session) or _is_recovery_planned(planned_session)):
        try:
            te = float(training_effect)
            te_limit = 2.5 if planned_sport == "run" else 3.0
            if te >= te_limit:
                result["execution_hint"] = _merge_execution(result["execution_hint"], "too_hard")
                result["risks"].append("training_effect_high_for_easy_session")
                result["impact"].append("monitor_fatigue")
        except (TypeError, ValueError):
            pass

    # --- Swim pace (optional, no invention) ---
    if planned_sport == "swim":
        planned_pace = (planned_session.get("target") or {}).get("pace_seconds_per_100m")
        actual_pace = completed_activity.get("avg_pace_seconds_per_100m")
        if planned_pace and actual_pace:
            result["metrics_used"]["avg_pace_seconds_per_100m"] = actual_pace
            if float(actual_pace) < float(planned_pace) * 0.97:
                result["intensity_match"] = "higher_than_planned"
                result["execution_hint"] = _merge_execution(result["execution_hint"], "too_hard")
                result["risks"].append("swim_pace_faster_than_planned")
        elif not has_hr_signal:
            result["intensity_match"] = "unknown"

    if not has_hr_signal and planned_sport != "swim":
        result["intensity_match"] = "unknown"

    if run_conservative and result["execution_hint"] == "too_hard":
        result["risks"].append("run_executed_harder_than_planned")

    if _is_long(_session_type(planned_session), planned_session.get("duration_minutes")):
        if (z3_z4_pct or 0) >= 40 or (actual_rank or 0) >= 4:
            result["risks"].append("long_session_executed_too_hard")
            result["impact"].append("monitor_fatigue")

    result["impact"] = _unique(result["impact"])
    result["risks"] = _unique(result["risks"])
    return result


def _build_interpretation(
    status: str,
    execution: str,
    sport_match: str,
    planned_sport: str,
    actual_sport: str,
    planned_session: dict,
    intensity_match: str,
    dur_match: str,
) -> str:
    planned_zone = _planned_target_zone(planned_session)
    zone_label = f"/{planned_zone}" if planned_zone else ""

    if sport_match in {"mismatch", "wrong_sport"}:
        return f"Planned {planned_sport} but completed {actual_sport} — sport mismatch."
    if status == "substituted" or sport_match == "substituted":
        return f"Substituted planned {planned_sport} with {actual_sport}."
    if execution == "too_hard" and intensity_match == "higher_than_planned":
        return (
            f"Completed the planned duration, but the session was harder than prescribed "
            f"for an easy{zone_label} day."
        )
    if execution == "too_long":
        return "Completed but duration exceeded the planned session — extra load accumulated."
    if execution == "too_short" or status == "partial":
        return "Partial completion relative to planned duration."
    if execution == "risky":
        return "Session completed with risky intensity peaks relative to plan."
    if execution == "good":
        return "Duration and intensity aligned with the planned easy/aerobic session."
    if execution == "too_easy":
        return "Completed below planned intensity — acceptable for recovery or easy days."
    return f"Status: {status}, duration: {dur_match}, intensity: {intensity_match}."


def classify_completed_activity(
    planned_session: dict,
    completed_activity: dict,
    athlete_profile: Optional[dict] = None,
) -> dict:
    """Classify execution quality using duration, sport and HR zone data when available."""
    _ = {**DEFAULT_ATHLETE_PROFILE, **(athlete_profile or {})}

    planned_sport = _sport_family(planned_session.get("sport", ""))
    actual_sport = _sport_family(completed_activity.get("sport", ""))
    planned_min = planned_session.get("duration_minutes")
    actual_min = completed_activity.get("duration_minutes")

    if not actual_min and not actual_sport:
        return {
            "status": "missed",
            "execution_quality": "unknown",
            "duration_match": "unknown",
            "intensity_match": "unknown",
            "sport_match": "unknown",
            "coach_interpretation": "Insufficient data to classify execution.",
            "impact_on_next_plan": [],
            "risk_flags": ["insufficient_data"],
            "intensity_analysis": {},
        }

    ratio = _duration_ratio(
        float(planned_min) if planned_min else None,
        float(actual_min) if actual_min else None,
    )
    dur_match = _duration_match_label(ratio)
    sport_match = _assess_sport_match(planned_sport, actual_sport)

    if sport_match == "mismatch":
        return {
            "status": "substituted",
            "execution_quality": "wrong_sport",
            "duration_match": dur_match,
            "intensity_match": "unknown",
            "sport_match": "mismatch",
            "coach_interpretation": _build_interpretation(
                "substituted", "wrong_sport", "mismatch", planned_sport, actual_sport,
                planned_session, "unknown", dur_match,
            ),
            "impact_on_next_plan": ["manual_review"],
            "risk_flags": ["sport_mismatch"],
            "intensity_analysis": {},
        }

    status = "completed"
    if sport_match == "substituted":
        status = "substituted"
    elif ratio is not None and ratio < 0.70:
        status = "partial"

    dur_status, dur_execution, dur_impact, dur_risks = _assess_duration(
        planned_session, ratio, dur_match,
    )
    if status == "completed" and dur_status == "partial":
        status = "partial"

    intensity = _assess_intensity_from_hr(planned_session, completed_activity, planned_sport)
    intensity_match = intensity["intensity_match"]
    execution = intensity["execution_hint"]
    impact: List[str] = list(intensity["impact"]) + dur_impact
    risks: List[str] = list(intensity["risks"]) + dur_risks

    execution = _merge_execution(execution, dur_execution)

    if (
        status == "completed"
        and sport_match == "matched"
        and dur_match == "matched"
        and intensity_match in {"matched", "lower_than_planned"}
        and execution in {"acceptable", "good"}
        and not risks
    ):
        execution = "good"

    if status == "partial" and execution not in {"too_short", "too_hard", "risky", "too_long"}:
        execution = "acceptable"

    return {
        "status": status,
        "execution_quality": execution,
        "duration_match": dur_match,
        "intensity_match": intensity_match,
        "sport_match": sport_match,
        "coach_interpretation": _build_interpretation(
            status, execution, sport_match, planned_sport, actual_sport,
            planned_session, intensity_match, dur_match,
        ),
        "impact_on_next_plan": _unique(impact),
        "risk_flags": _unique(risks),
        "intensity_analysis": intensity.get("metrics_used") or {},
    }


def classify_unplanned_activity(completed_activity: dict) -> dict:
    """Mark an extra activity as unplanned."""
    return {
        "status": "unplanned",
        "execution_quality": "unknown",
        "duration_match": "unknown",
        "intensity_match": "unknown",
        "sport_match": "mismatch",
        "coach_interpretation": "Activity was not part of the planned schedule.",
        "impact_on_next_plan": ["monitor_fatigue"],
        "risk_flags": ["unplanned_volume"],
    }


# ---------------------------------------------------------------------------
# 4. weekly_coach_review
# ---------------------------------------------------------------------------

def weekly_coach_review(
    week_start: Union[str, datetime.date],
    week_end: Union[str, datetime.date],
    planned_week: Optional[dict] = None,
    compliance_data: Optional[dict] = None,
    activities_summary: Optional[dict] = None,
    wellness_summary: Optional[dict] = None,
    athlete_profile: Optional[dict] = None,
    *,
    pain_reported_this_week: bool = False,
    execution_classifications: Optional[List[dict]] = None,
    auto_fetch: bool = True,
    schedule_audit: Optional[dict] = None,
) -> dict:
    """Structured weekly review for Claude to turn into human conversation.

    auto_fetch=True fetches compliance, activities and wellness from Garmin when
    garmin_client is configured. auto_fetch=False uses only the inputs passed.
    """
    _ = {**DEFAULT_ATHLETE_PROFILE, **(athlete_profile or {})}

    if isinstance(week_start, datetime.date):
        ws = week_start.isoformat()
    else:
        ws = str(week_start)
    if isinstance(week_end, datetime.date):
        we = week_end.isoformat()
    else:
        we = str(week_end)

    manual_inputs = any([
        compliance_data is not None,
        activities_summary is not None,
        wellness_summary is not None,
        execution_classifications is not None,
    ])
    fetched: Dict[str, Any] = {}
    fetch_gaps: List[str] = []
    data_mode = "manual"

    if auto_fetch and coach_weekly_data is not None and coach_weekly_data.garmin_client is not None:
        fetched = coach_weekly_data.fetch_weekly_garmin_context(ws, we)
        fetch_gaps = list(fetched.get("data_gaps") or [])
        if fetched.get("error"):
            data_mode = "manual" if manual_inputs else "auto_failed"
        elif manual_inputs:
            data_mode = "hybrid"
        else:
            data_mode = "auto"
    elif auto_fetch and not manual_inputs:
        fetch_gaps.append("garmin_client_unavailable")
        data_mode = "auto_failed"

    def _pick(manual_val, fetched_key):
        if manual_val is not None:
            return manual_val
        return fetched.get(fetched_key)

    compliance = _pick(compliance_data, "compliance_data") or {}
    activities = _pick(activities_summary, "activities_summary") or {}
    wellness = _pick(wellness_summary, "wellness_summary") or {}
    exec_class = execution_classifications
    if exec_class is None:
        exec_class = fetched.get("execution_classifications")

    summary = compliance.get("summary") or compliance

    planned = int(summary.get("scheduled") or summary.get("planned_sessions") or 0)
    completed = int(summary.get("completed") or summary.get("completed_sessions") or 0)
    partial = int(summary.get("partial") or summary.get("partial_sessions") or 0)
    missed = int(summary.get("missed") or summary.get("missed_sessions") or 0)
    unplanned = int(summary.get("unplanned_activities") or 0)
    rate = summary.get("compliance_rate")
    if rate is None and planned:
        rate = round(completed / planned, 2)

    sport_dist = activities.get("sport_distribution") or activities.get("minutes_by_sport") or {}
    total_minutes = activities.get("total_training_minutes") or sum(sport_dist.values()) if sport_dist else None

    exec_summary = {"good": 0, "acceptable": 0, "too_hard": 0, "too_short": 0, "risky": 0}
    for item in exec_class or []:
        q = item.get("execution_quality", "acceptable")
        if q in exec_summary:
            exec_summary[q] += 1
        elif q == "too_long":
            exec_summary["acceptable"] += 1

    risk_flags: List[str] = []
    positive: List[str] = []
    perf_notes: List[str] = [
        "Maintain aerobic base focus.",
        "Do not add intensity until easy sessions are controlled.",
        "Prioritize swim consistency and long bike progression.",
    ]

    wellness_data = wellness
    sleep_stable = wellness_data.get("sleep_stable", True)
    hrv_ok = wellness_data.get("hrv_not_suppressed", True)

    audit = schedule_audit or {}
    if audit:
        risk_flags.extend(audit.get("risk_flags") or [])
        positive.extend(audit.get("positive_signals") or [])
        if audit.get("execution_quality_score") is not None:
            if audit["execution_quality_score"] < 70:
                exec_summary["too_hard"] = max(exec_summary["too_hard"], 1)
        if audit.get("schedule_alignment_score") is not None:
            if audit["schedule_alignment_score"] < 70 and rate is not None and rate >= 0.8:
                rate = min(rate, 0.79)
        for item in (audit.get("scheduled_vs_completed") or {}).get("completed_but_too_hard") or []:
            exec_summary["too_hard"] += 1
        followups_from_audit = audit.get("recommended_followups") or []
    else:
        followups_from_audit = []

    if rate is not None and rate < 0.8:
        risk_flags.append("compliance_below_target")
    if pain_reported_this_week:
        risk_flags.append("pain_reported")
    if exec_summary["too_hard"] >= 2:
        risk_flags.append("easy_sessions_executed_too_hard")
    if activities.get("run_load_increased"):
        risk_flags.append("run_load_increased")
    if activities.get("swim_sessions", 0) < 2:
        risk_flags.append("missed_key_swim")
    if not sleep_stable:
        risk_flags.append("sleep_unstable")
    if not hrv_ok:
        risk_flags.append("hrv_suppressed")

    if completed >= 1 and planned_week:
        key = planned_week.get("key_sessions") or []
        if key:
            positive.append("completed_main_endurance_session")
    if sport_dist.get("strength", 0) >= 25:
        positive.append("consistent_strength_work")
    if sleep_stable:
        positive.append("sleep_stable")
    if rate is not None and rate >= 0.85:
        positive.append("good_compliance")

    overall = "maintain"
    load_decision = "maintain"
    week_type = "foundation"
    load_change = "hold"

    if pain_reported_this_week or exec_summary["too_hard"] >= 2 or not hrv_ok:
        overall = "reduce"
        load_decision = "reduce"
        load_change = "reduce"
        week_type = "recovery"
    elif audit.get("overall_status") == "misaligned":
        overall = "maintain"
        load_decision = "maintain"
        load_change = "hold"
    elif audit.get("execution_quality_score") is not None and audit["execution_quality_score"] < 60:
        overall = "reduce"
        load_decision = "reduce"
        load_change = "reduce"
        week_type = "recovery"
    elif rate is not None and rate < 0.8:
        overall = "maintain"
        load_decision = "maintain"
        load_change = "hold"
    elif (
        rate is not None and rate >= 0.8
        and not pain_reported_this_week
        and exec_summary["too_hard"] == 0
        and sleep_stable
        and hrv_ok
        and exec_summary["good"] >= 2
        and (not audit or audit.get("overall_status") in {None, "aligned", "partially_aligned"})
        and (audit.get("execution_quality_score") or 100) >= 70
        and (audit.get("schedule_alignment_score") or 100) >= 70
    ):
        overall = "progress"
        load_decision = "increase_slightly"
        load_change = "small_increase"
        week_type = "build"
    elif exec_summary["risky"] or not sleep_stable:
        overall = "recovery_needed"
        load_decision = "deload"
        load_change = "reduce"

    confidence = "medium"
    has_compliance = bool(summary.get("scheduled") or summary.get("planned_sessions"))
    has_activities = bool(activities.get("total_training_minutes") or activities.get("activity_count"))
    if data_mode in {"auto", "hybrid"} and has_compliance and has_activities:
        confidence = "high"
    elif data_mode == "manual" and has_compliance and has_activities:
        confidence = "high"
    elif data_mode == "auto_failed" and not manual_inputs:
        confidence = "low"

    return {
        "week_start": ws,
        "week_end": we,
        "review_type": "weekly_coach_engine_summary",
        "data_mode": data_mode,
        "data_gaps": _unique(fetch_gaps),
        "fetched_summary": {
            k: fetched.get(k)
            for k in (
                "scheduled_workout_count",
                "activities_summary",
                "wellness_summary",
            )
            if fetched.get(k) is not None
        } if fetched else {},
        "overall_status": overall,
        "load_decision": load_decision,
        "confidence": confidence,
        "summary_metrics": {
            "planned_sessions": planned,
            "completed_sessions": completed,
            "partial_sessions": partial,
            "missed_sessions": missed,
            "unplanned_activities": unplanned,
            "compliance_rate": rate,
            "total_training_minutes": total_minutes,
            "sport_distribution": sport_dist,
        },
        "execution_quality_summary": exec_summary,
        "risk_flags": _unique(risk_flags),
        "positive_signals": _unique(positive),
        "performance_focus_notes": perf_notes,
        "next_week_recommendation": {
            "week_type": week_type,
            "load_change": load_change,
            "priority_sessions": [
                "swim_technique",
                "long_bike",
                "easy_run_frequency",
                "strength_consistency",
            ],
            "adjustments": _unique([
                "keep_secondary_optional",
                "avoid_adding_extra_run_intensity",
                "maintain_two_strength_sessions",
                "reduce" if load_change == "reduce" else "hold_current_load",
                *followups_from_audit[:3],
            ]),
        },
        "schedule_audit_used": bool(audit),
        "claude_mediator_hint": {
            "summary": "Claude should turn this into a human-readable weekly review.",
            "questions_to_ask_user": [
                "How did the key session feel?",
                "Any pain or unusual fatigue?",
                "Which days were hardest to fit into your routine?",
            ],
        },
    }


# ---------------------------------------------------------------------------
# 5. plan_training_block (skeleton)
# ---------------------------------------------------------------------------

def plan_training_block(
    start_date: Union[str, datetime.date],
    weeks: int = 4,
    athlete_profile: Optional[dict] = None,
    goal: Optional[dict] = None,
    current_fitness_context: Optional[dict] = None,
) -> dict:
    """High-level multi-week block skeleton — not full periodization."""
    _ = {**DEFAULT_ATHLETE_PROFILE, **(athlete_profile or {})}
    _ = goal or {}
    _ = current_fitness_context or {}

    if isinstance(start_date, datetime.date):
        start = start_date
    else:
        start = datetime.date.fromisoformat(str(start_date))

    weeks = max(1, min(int(weeks), 12))
    pattern = [
        ("adaptation", "low_to_moderate"),
        ("build", "moderate"),
        ("build", "moderate"),
        ("recovery", "low"),
    ]

    block_weeks: List[dict] = []
    for i in range(weeks):
        wt, load = pattern[i % len(pattern)]
        block_weeks.append({
            "week_number": i + 1,
            "week_start": (start + datetime.timedelta(weeks=i)).isoformat(),
            "week_type": wt,
            "load_target": load,
        })

    return {
        "block_type": "base_foundation",
        "target": "ironman_70_3",
        "start_date": start.isoformat(),
        "weeks": weeks,
        "week_outline": block_weeks,
        "notes": [
            "This is a high-level block structure only.",
            "Claude remains responsible for daily decisions.",
            "Use plan_triathlon_week per week and coach engine tools daily.",
        ],
        "claude_mediator_hint": _claude_mediator_hint(
            summary="Use each week outline as load context; materialize weeks with plan_triathlon_week.",
        ),
    }


# ---------------------------------------------------------------------------
# MCP registration
# ---------------------------------------------------------------------------

garmin_client = None


def configure(client):
    global garmin_client
    garmin_client = client
    if coach_weekly_data is not None:
        coach_weekly_data.configure(client)


def register_tools(app):
    import json as _json

    _adjust_fn = globals()["adjust_today_workout"]
    _validate_fn = globals()["validate_training_decision"]
    _classify_fn = globals()["classify_completed_activity"]
    _review_fn = globals()["weekly_coach_review"]
    _block_fn = globals()["plan_training_block"]
    # audit_week_schedule vive no servidor MCP completo (acoplado aos dados do Garmin);
    # ausente no repo focado — a tool só é registrada quando a base está presente.
    try:  # pragma: no cover
        from garmin_mcp.coach_week_audit import audit_week_schedule as _audit_fn  # type: ignore
    except Exception:  # pragma: no cover
        _audit_fn = None  # type: ignore
    from triathlon_coach.mediator_audit import audit_coach_mediator_session as _mediator_audit_fn
    from triathlon_coach.checkin import get_daily_checkin_schema as _get_checkin_schema_fn

    @app.tool()
    async def adjust_today_workout(
        planned_day: dict,
        daily_training_brief: Optional[dict] = None,
        subjective_checkin: Optional[dict] = None,
        recent_context: Optional[dict] = None,
        athlete_profile: Optional[dict] = None,
    ) -> str:
        """Return structured technical guidance for today's training (not a final prescription).

        Combines planned day template, Garmin daily brief, subjective check-in and
        recent context. Returns decision hints, allowed/blocked actions, risk flags
        and notes for Claude to mediate the final workout choice.
        """
        try:
            result = _adjust_fn(
                planned_day,
                daily_training_brief=daily_training_brief,
                subjective_checkin=subjective_checkin,
                recent_context=recent_context,
                athlete_profile=athlete_profile,
            )
            return _json.dumps(result, indent=2)
        except Exception as e:
            return f"Error in adjust_today_workout: {e}"

    @app.tool()
    async def validate_training_decision(
        proposed_sessions: List[dict],
        day_context: dict,
        weekly_context: Optional[dict] = None,
        athlete_profile: Optional[dict] = None,
        manual_override_pain: bool = False,
    ) -> str:
        """Safety gate before creating or scheduling workouts.

        Validates proposed sessions against day and weekly guardrails.
        Returns pass/warning/blocked with violations and suggested changes.
        """
        try:
            result = _validate_fn(
                proposed_sessions,
                day_context,
                weekly_context=weekly_context,
                athlete_profile=athlete_profile,
                manual_override_pain=manual_override_pain,
            )
            return _json.dumps(result, indent=2)
        except Exception as e:
            return f"Error in validate_training_decision: {e}"

    @app.tool()
    async def classify_completed_activity(
        planned_session: dict,
        completed_activity: dict,
        athlete_profile: Optional[dict] = None,
    ) -> str:
        """Classify execution quality of a completed activity vs plan.

        Goes beyond completed/partial/missed — evaluates duration, intensity
        and sport match and flags risky execution.
        """
        try:
            result = _classify_fn(
                planned_session,
                completed_activity,
                athlete_profile=athlete_profile,
            )
            return _json.dumps(result, indent=2)
        except Exception as e:
            return f"Error in classify_completed_activity: {e}"

    @app.tool()
    async def get_daily_checkin_schema() -> str:
        """Return the subjective daily check-in schema (JSON-serializable).

        Use before adjust_today_workout. Pain and available_minutes must not be
        assumed when the athlete has not answered.
        """
        try:
            schema = _get_checkin_schema_fn()
            return _json.dumps(schema, indent=2)
        except Exception as e:
            return f"Error in get_daily_checkin_schema: {e}"

    @app.tool()
    async def audit_coach_mediator_session(
        session_type: str,
        session_trace: dict,
        strictness: str = "normal",
        athlete_profile: Optional[dict] = None,
    ) -> str:
        """Audit whether Claude followed the Coach Engine mediator protocol.

        session_type must be one of:
        - daily_workout_decision
        - weekly_review
        - schedule_audit
        - planning_only

        Common aliases accepted (normalized automatically):
        - daily, daily_adjustment, dry_run_daily_adjustment, dry_run → daily_workout_decision
        - weekly → weekly_review
        - audit, schedule_review → schedule_audit
        - planning, plan → planning_only

        strictness: lenient | normal | strict (aliases: low, default, high).

        Returns technical JSON with valid_session_types and accepted_aliases on errors.
        """
        try:
            result = _mediator_audit_fn(
                session_type,
                session_trace,
                strictness=strictness,
                athlete_profile=athlete_profile,
            )
            return _json.dumps(result, indent=2)
        except Exception as e:
            return f"Error in audit_coach_mediator_session: {e}"

    @app.tool()
    async def audit_week_schedule(
        week_start: str,
        week_end: str,
        planned_week: Optional[dict] = None,
        scheduled_workouts: Optional[List[dict]] = None,
        compliance_data: Optional[dict] = None,
        completed_activities: Optional[List[dict]] = None,
        athlete_profile: Optional[dict] = None,
        auto_fetch: bool = True,
    ) -> str:
        """Audit weekly template vs Garmin calendar vs execution quality.

        Compares plan_triathlon_week structure with scheduled workouts, compliance
        and classify_completed_activity results. Returns technical JSON for Claude.
        """
        try:
            result = _audit_fn(
                week_start,
                week_end,
                planned_week=planned_week,
                scheduled_workouts=scheduled_workouts,
                compliance_data=compliance_data,
                completed_activities=completed_activities,
                athlete_profile=athlete_profile,
                auto_fetch=auto_fetch,
            )
            return _json.dumps(result, indent=2)
        except Exception as e:
            return f"Error in audit_week_schedule: {e}"

    @app.tool()
    async def weekly_coach_review(
        week_start: str,
        week_end: str,
        planned_week: Optional[dict] = None,
        compliance_data: Optional[dict] = None,
        activities_summary: Optional[dict] = None,
        wellness_summary: Optional[dict] = None,
        athlete_profile: Optional[dict] = None,
        pain_reported_this_week: bool = False,
        execution_classifications: Optional[List[dict]] = None,
        auto_fetch: bool = True,
        schedule_audit: Optional[dict] = None,
    ) -> str:
        """Generate structured weekly review data for Claude (not motivational text).

        Auto mode (default): fetches compliance, activities, wellness from Garmin when
        manual inputs are omitted. Hybrid: pass any manual fields to override/merge.
        Set auto_fetch=false for fully manual mode.
        """
        try:
            result = _review_fn(
                week_start,
                week_end,
                planned_week=planned_week,
                compliance_data=compliance_data,
                activities_summary=activities_summary,
                wellness_summary=wellness_summary,
                athlete_profile=athlete_profile,
                pain_reported_this_week=pain_reported_this_week,
                execution_classifications=execution_classifications,
                auto_fetch=auto_fetch,
                schedule_audit=schedule_audit,
            )
            return _json.dumps(result, indent=2)
        except Exception as e:
            return f"Error in weekly_coach_review: {e}"

    @app.tool()
    async def plan_training_block(
        start_date: str,
        weeks: int = 4,
        athlete_profile: Optional[dict] = None,
        goal: Optional[dict] = None,
        current_fitness_context: Optional[dict] = None,
    ) -> str:
        """High-level training block skeleton (4-week default) for Ironman 70.3 base.

        Not full periodization — outlines week types and load targets only.
        """
        try:
            result = _block_fn(
                start_date,
                weeks=weeks,
                athlete_profile=athlete_profile,
                goal=goal,
                current_fitness_context=current_fitness_context,
            )
            return _json.dumps(result, indent=2)
        except Exception as e:
            return f"Error in plan_training_block: {e}"

    return app
