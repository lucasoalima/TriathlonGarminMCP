"""
Audit Claude mediator sessions against the Coach Engine 1.0 protocol.

Validates an explicit session_trace — tool order, safety gates, data integrity.
Does NOT read chain-of-thought, judge personality, or produce coaching messages.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set, Tuple

from triathlon_coach.checkin import normalize_subjective_checkin
from triathlon_coach.engine import (
    DEFAULT_ATHLETE_PROFILE,
    HARD_INTENSITIES,
    LONG_TYPES,
    SWIM_FORBIDDEN_DAYS,
    _is_hard,
    _is_long,
    _norm,
    _sport_family,
)

AUDIT_TYPE = "coach_mediator_session_audit"

VALID_SESSION_TYPES = frozenset({
    "daily_workout_decision",
    "weekly_review",
    "schedule_audit",
    "planning_only",
})

SESSION_TYPES = VALID_SESSION_TYPES  # backward compat

SESSION_TYPE_ALIASES: Dict[str, str] = {
    "daily": "daily_workout_decision",
    "daily_adjustment": "daily_workout_decision",
    "daily_workout": "daily_workout_decision",
    "dry_run_daily_adjustment": "daily_workout_decision",
    "dry_run": "daily_workout_decision",
    "today_workout": "daily_workout_decision",
    "workout_decision": "daily_workout_decision",
    "weekly": "weekly_review",
    "week_review": "weekly_review",
    "weekly_summary": "weekly_review",
    "audit": "schedule_audit",
    "week_audit": "schedule_audit",
    "schedule": "schedule_audit",
    "schedule_review": "schedule_audit",
    "planning": "planning_only",
    "plan": "planning_only",
    "planning_week": "planning_only",
}

STRICTNESS_LEVELS = frozenset({"lenient", "normal", "strict"})

STRICTNESS_ALIASES: Dict[str, str] = {
    "low": "lenient",
    "default": "normal",
    "high": "strict",
}

SCHEDULE_TOOLS = frozenset({"schedule_workout", "schedule_week"})
VALIDATION_TOOL = "validate_training_decision"
ADJUST_TOOL = "adjust_today_workout"
BRIEF_TOOL = "get_daily_training_brief"
PLAN_TOOL = "plan_triathlon_week"
AUDIT_WEEK_TOOL = "audit_week_schedule"
WEEKLY_REVIEW_TOOL = "weekly_coach_review"
CHECKIN_SCHEMA_TOOL = "get_daily_checkin_schema"

LOW_READINESS = frozenset({"low", "poor", "very_low"})

INVENTED_METRIC_KEYS = frozenset({
    "pace", "target_pace", "css", "ftp", "watts", "power", "hr_zone",
    "target_zone", "target_hr_zone", "threshold_pace", "threshold_power",
})

WEIGHT_LOSS_TERMS = frozenset({"weight_loss", "fat_loss", "emagrecimento", "perda_de_peso"})

PLANNING_REQUIRED_KEYS = frozenset({
    "coach_engine_contract",
    "performance_policy",
    "discipline_guardrails",
    "progression_policy",
    "subjective_checkin_policy",
})


def _unique(items: List[str]) -> List[str]:
    seen: set = set()
    out: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _first_present(trace: dict, keys: Tuple[str, ...]) -> Any:
    for key in keys:
        if key in trace and trace[key] is not None:
            return trace[key]
    return None


def _normalize_tool_entry(entry: Any) -> Optional[str]:
    if isinstance(entry, str):
        name = entry.strip()
        return name or None
    if isinstance(entry, dict):
        for key in ("name", "tool", "tool_name", "method"):
            value = entry.get(key)
            if value:
                return str(value)
    return None


def _extract_tool_sequence(trace: dict) -> List[str]:
    raw = _first_present(
        trace,
        ("tool_sequence", "tools_called", "tool_calls", "called_tools", "tool_call_order"),
    )
    if not raw:
        return []
    out: List[str] = []
    for entry in raw:
        name = _normalize_tool_entry(entry)
        if name:
            out.append(name)
    return out


def _append_data_gap(
    data_gaps: List[dict],
    code: str,
    message: str,
    severity: str = "warning",
) -> None:
    data_gaps.append({"code": code, "severity": severity, "message": message})


def _unique_data_gaps(gaps: List[Any]) -> List[dict]:
    seen: Set[str] = set()
    out: List[dict] = []
    for gap in gaps:
        if isinstance(gap, str):
            item = {"code": gap, "severity": "warning", "message": gap}
        elif isinstance(gap, dict):
            item = {
                "code": gap.get("code") or "unknown_data_gap",
                "severity": gap.get("severity") or "warning",
                "message": gap.get("message") or gap.get("code") or "Data gap reported.",
            }
        else:
            continue
        code = item["code"]
        if code not in seen:
            seen.add(code)
            out.append(item)
    return out


def _is_brief_empty(brief: Optional[dict]) -> bool:
    if not brief:
        return True
    if brief.get("brief_empty") is True or brief.get("brief_available") is False:
        return True
    skip = frozenset({
        "date", "data_gaps", "brief_empty", "brief_available", "garmin_sync_missing",
    })
    for key, value in brief.items():
        if key in skip:
            continue
        if value is not None and value != {} and value != []:
            return False
    return True


def _checkin_looks_provided(raw: dict, normalized: dict) -> bool:
    if raw.get("provided"):
        return True
    if normalized.get("checkin_complete"):
        return True
    pain = raw.get("pain") or {}
    has_pain = pain.get("has_pain")
    if has_pain is True or has_pain is False:
        pain_answered = True
    elif isinstance(has_pain, str):
        pain_answered = has_pain.lower() not in {"", "unknown"}
    else:
        pain_answered = normalized.get("pain", {}).get("status") in {"yes", "no"}
    return bool(
        pain_answered
        and raw.get("fatigue_0_10") is not None
        and raw.get("available_minutes") is not None
        and raw.get("schedule_constraints") not in (None, "")
    )


def _resolve_checkin(trace: dict) -> Tuple[dict, dict, bool]:
    """Return (raw_checkin, normalized_checkin, considered_provided)."""
    checkin_status = trace.get("checkin_status") or {}
    raw: dict = {}

    if isinstance(checkin_status, dict) and checkin_status.get("normalized_checkin"):
        raw = dict(checkin_status["normalized_checkin"])
    else:
        found = _first_present(
            trace,
            ("user_checkin", "subjective_checkin", "checkin", "normalized_checkin"),
        )
        raw = dict(found) if isinstance(found, dict) else {}

    normalized = normalize_subjective_checkin(raw)
    provided = bool(
        _checkin_looks_provided(raw, normalized)
        or trace.get("subjective_checkin_collected")
        or (isinstance(checkin_status, dict) and checkin_status.get("checkin_complete"))
    )
    if provided:
        raw = {**raw, "provided": True}
    return raw, normalized, provided


def normalize_session_trace(session_trace: dict) -> dict:
    """Resolve common session_trace aliases into canonical keys for auditing."""
    trace = dict(session_trace or {})
    normalized = dict(trace)

    sequence = _extract_tool_sequence(trace)
    if sequence:
        normalized["tool_sequence"] = sequence

    checkin, checkin_norm, _ = _resolve_checkin(trace)
    if checkin:
        normalized["user_checkin"] = checkin
    normalized["_checkin_normalized"] = checkin_norm

    brief = _first_present(
        trace,
        (
            "daily_training_brief_summary",
            "daily_training_brief",
            "daily_brief",
            "brief",
            "brief_summary",
        ),
    )
    if isinstance(brief, dict):
        normalized["daily_training_brief_summary"] = brief

    adjust = _first_present(
        trace,
        ("adjust_today_workout_result", "adjust_result", "adjustment_result", "today_adjustment"),
    )
    if isinstance(adjust, dict):
        normalized["adjust_today_workout_result"] = adjust

    validate = _first_present(
        trace,
        (
            "validate_training_decision_result",
            "validation_result",
            "training_decision_validation",
        ),
    )
    if isinstance(validate, dict):
        normalized["validate_training_decision_result"] = validate

    plan = _first_present(
        trace,
        ("plan_triathlon_week_result", "planned_week", "weekly_plan"),
    )
    if isinstance(plan, dict):
        normalized["plan_triathlon_week_result"] = plan

    planned_day = trace.get("planned_day")
    if not isinstance(planned_day, dict):
        planned_day = _first_present(trace, ("planned_day",))
    if isinstance(planned_day, dict):
        normalized["planned_day"] = planned_day

    proposed = _first_present(
        trace,
        ("claude_proposed_sessions", "proposed_sessions", "final_proposed_sessions"),
    )
    if isinstance(proposed, list):
        normalized["claude_proposed_sessions"] = proposed

    created = _first_present(trace, ("created_workouts", "created_sessions"))
    if isinstance(created, list):
        normalized["created_workouts"] = created

    scheduled = _first_present(trace, ("scheduled_workouts", "scheduled_sessions"))
    if isinstance(scheduled, list):
        normalized["scheduled_workouts"] = scheduled

    final = _first_present(trace, ("final_response_summary", "response_summary"))
    if isinstance(final, dict):
        normalized["final_response_summary"] = final

    dry_run = trace.get("dry_run")
    if dry_run is None:
        mode = _norm(trace.get("mode") or "")
        dry_run = mode in {"dry_run", "dry-run", "dryrun"}
    normalized["dry_run"] = bool(dry_run)

    return normalized


def _canonical_tool_name(name: str) -> str:
    base = str(name).strip().lower()
    if "(" in base:
        base = base.split("(", 1)[0].strip()
    if " " in base:
        base = base.split()[0]
    return base


def _sequence_contains_tool(sequence: List[str], tool: str) -> bool:
    needle = _canonical_tool_name(tool)
    for entry in sequence:
        candidate = _normalize_tool_entry(entry) or entry
        if _canonical_tool_name(str(candidate)) == needle:
            return True
    return False


def _tool_index(sequence: List[str], tool: str) -> Optional[int]:
    needle = _canonical_tool_name(tool)
    for i, entry in enumerate(sequence):
        candidate = _normalize_tool_entry(entry) or entry
        if _canonical_tool_name(str(candidate)) == needle:
            return i
    return None


def _last_tool_index(sequence: List[str], tool: str) -> Optional[int]:
    idx = None
    for i, entry in enumerate(sequence):
        candidate = _normalize_tool_entry(entry) or entry
        if _canonical_tool_name(str(candidate)) == _canonical_tool_name(tool):
            idx = i
    return idx


def _create_tools(sequence: List[str]) -> List[str]:
    out: List[str] = []
    for entry in sequence:
        candidate = _normalize_tool_entry(entry) or str(entry)
        if _canonical_tool_name(candidate).startswith("create_"):
            out.append(candidate)
    return out


def _violation(code: str, severity: str, message: str) -> dict:
    return {"code": code, "severity": severity, "message": message}


def normalize_session_type(session_type: Optional[str]) -> Tuple[Optional[str], dict]:
    """Map canonical or alias session_type to canonical value."""
    raw = _norm(session_type or "")
    meta: dict = {
        "original_session_type": session_type,
        "warnings": [],
    }
    if not raw:
        return None, meta
    if raw in VALID_SESSION_TYPES:
        meta["session_type_canonical"] = raw
        return raw, meta
    canonical = SESSION_TYPE_ALIASES.get(raw)
    if canonical:
        meta["session_type_canonical"] = canonical
        meta["session_type_normalized_from"] = raw
        meta["warnings"].append(_violation(
            "session_type_alias_used",
            "warning",
            f"session_type alias '{raw}' mapped to '{canonical}'.",
        ))
        return canonical, meta
    meta["session_type_canonical"] = None
    return None, meta


def normalize_strictness(strictness: Optional[str]) -> Tuple[str, List[dict]]:
    """Normalize strictness to lenient | normal | strict."""
    raw = _norm(strictness or "") or "normal"
    if raw in STRICTNESS_LEVELS:
        return raw, []
    if raw in STRICTNESS_ALIASES:
        return STRICTNESS_ALIASES[raw], []
    return "normal", [_violation(
        "invalid_strictness_defaulted_to_normal",
        "warning",
        f"Unknown strictness '{strictness}'; defaulted to 'normal'.",
    )]


def _accepted_aliases_public() -> Dict[str, str]:
    """Subset of aliases for LLM-facing error docs."""
    keys = (
        "daily", "daily_adjustment", "dry_run_daily_adjustment", "dry_run",
        "weekly", "audit", "schedule_review", "planning", "plan",
    )
    return {k: SESSION_TYPE_ALIASES[k] for k in keys if k in SESSION_TYPE_ALIASES}


def _unknown_session_type_response(
    session_type: Optional[str],
    strictness: str,
    strictness_warnings: List[dict],
) -> dict:
    st_display = _norm(session_type or "") or "unknown"
    return {
        "audit_type": AUDIT_TYPE,
        "session_type": st_display,
        "session_type_requested": session_type,
        "strictness": strictness,
        "overall_status": "insufficient_data",
        "protocol_score": 0.0,
        "safety_score": 0.0,
        "data_integrity_score": 0.0,
        "violations": [_violation(
            "unknown_session_type",
            "error",
            f"Unknown session_type: {st_display!r}.",
        )],
        "warnings": list(strictness_warnings),
        "missing_steps": [],
        "unsafe_assumptions": [],
        "blocked_action_violations": [],
        "tool_order_violations": [],
        "data_gaps": [{
            "code": "session_type",
            "severity": "error",
            "message": "session_type missing or unknown.",
        }],
        "valid_session_types": sorted(VALID_SESSION_TYPES),
        "accepted_aliases": _accepted_aliases_public(),
        "required_repair_actions": [
            "Use a valid session_type from valid_session_types or accepted_aliases.",
        ],
        "recommended_next_prompt": (
            "Call audit_coach_mediator_session again using "
            "session_type='daily_workout_decision' (or alias 'dry_run_daily_adjustment')."
        ),
        "claude_mediator_hint": {
            "summary": "Invalid session_type. Use canonical values or documented aliases.",
            "must_not_do": ["Do not guess undocumented session_type values."],
            "should_do_next": [
                "Retry with session_type='daily_workout_decision' for daily/dry-run flows.",
                "See valid_session_types and accepted_aliases in this response.",
            ],
        },
    }


def _session_intensity(session: dict) -> str:
    return _norm(session.get("intensity"))


def _session_type(session: dict) -> str:
    return _norm(session.get("type"))


def _is_sensitive_session(session: dict) -> bool:
    sport = _sport_family(session.get("sport", ""))
    intensity = _session_intensity(session)
    stype = _session_type(session)
    return (
        sport == "run"
        or _is_hard(intensity, stype)
        or _is_long(stype, session.get("duration_minutes"))
    )


def _is_hard_session(session: dict) -> bool:
    return _is_hard(_session_intensity(session), _session_type(session))


def _is_long_session(session: dict) -> bool:
    return _is_long(_session_type(session), session.get("duration_minutes"))


def _blocked_action_used(action: str, sessions: List[dict]) -> bool:
    action = _norm(action)
    if action in {"hard_intervals", "hard_session", "hard_run"}:
        return any(_is_hard_session(s) for s in sessions)
    if action == "long_run":
        return any(
            _sport_family(s.get("sport", "")) == "run" and _is_long_session(s)
            for s in sessions
        )
    if action in {"double_session", "secondary"}:
        return any(_norm(s.get("priority")) == "secondary" for s in sessions)
    if action == "running":
        return any(_sport_family(s.get("sport", "")) == "run" for s in sessions)
    if action == "heavy_leg_strength":
        return any(
            _sport_family(s.get("sport", "")) == "strength"
            and _session_intensity(s) in HARD_INTENSITIES
            for s in sessions
        )
    return False


def _session_has_invented_metrics(session: dict) -> bool:
    for key in session:
        if _norm(key) in INVENTED_METRIC_KEYS:
            return True
    target = session.get("target") or {}
    if isinstance(target, dict):
        mode = _norm(target.get("mode"))
        if mode in {"pace", "power", "watts", "css", "ftp"}:
            return True
        for k in target:
            if _norm(k) in INVENTED_METRIC_KEYS:
                return True
    return False


def _pain_status_from_trace(trace: dict) -> str:
    checkin = trace.get("user_checkin") or {}
    pain = checkin.get("pain") or {}
    has_pain = pain.get("has_pain")
    if has_pain is True:
        return "yes"
    if has_pain is False:
        return "no"
    if isinstance(has_pain, str):
        v = has_pain.lower()
        if v in {"true", "yes", "sim"}:
            return "yes"
        if v in {"false", "no", "nao", "não"}:
            return "no"
        if v == "unknown":
            return "unknown"
    normalized = trace.get("_checkin_normalized") or normalize_subjective_checkin(
        checkin if checkin.get("provided") else {"pain": pain}
    )
    return normalized.get("pain", {}).get("status", "unknown")


def _check_invented_pain(trace: dict) -> bool:
    checkin = trace.get("user_checkin") or {}
    pain = checkin.get("pain") or {}
    if pain.get("has_pain") is False and not checkin.get("provided"):
        return True
    if pain.get("has_pain") is False and checkin.get("pain_confirmed_by_user") is False:
        return True
    return False


def _check_invented_available_minutes(trace: dict) -> bool:
    checkin = trace.get("user_checkin") or {}
    if checkin.get("available_minutes") is not None and not checkin.get("provided"):
        if checkin.get("available_minutes_confirmed") is not True:
            return True
    return False


def _secondary_treated_as_required(sessions: List[dict], trace: dict) -> bool:
    secondaries = [s for s in sessions if _norm(s.get("priority")) == "secondary"]
    if not secondaries:
        return False
    adjust = trace.get("adjust_today_workout_result") or {}
    if "secondary" in (adjust.get("blocked_actions") or []):
        return True
    notes = " ".join(adjust.get("notes") or []).lower()
    if "secondary should not" in notes or "remove secondary" in notes:
        return True
    for s in secondaries:
        if s.get("required") is True:
            return True
    final = trace.get("final_response_summary") or {}
    if final.get("secondary_presented_as_required"):
        return True
    return False


def _audit_daily_workout_decision(
    trace: dict,
    strictness: str,
) -> Tuple[List[dict], List[dict], List[str], List[str], List[str], List[str], List[dict], List[str]]:
    violations: List[dict] = []
    warnings: List[dict] = []
    missing_steps: List[str] = []
    unsafe_assumptions: List[str] = []
    blocked_violations: List[str] = []
    tool_order_violations: List[str] = []
    data_gaps: List[dict] = []
    positive_signals: List[str] = []

    sequence = list(trace.get("tool_sequence") or [])
    proposed = list(trace.get("claude_proposed_sessions") or [])
    adjust = trace.get("adjust_today_workout_result") or {}
    validate = trace.get("validate_training_decision_result") or {}
    created = trace.get("created_workouts") or []
    scheduled = trace.get("scheduled_workouts") or []
    checkin = trace.get("user_checkin") or {}
    checkin_norm = trace.get("_checkin_normalized") or normalize_subjective_checkin(checkin)
    brief = trace.get("daily_training_brief_summary") or {}
    final = trace.get("final_response_summary") or {}
    standalone = bool(trace.get("standalone_workout"))
    dry_run = bool(trace.get("dry_run"))

    has_create = bool(_create_tools(sequence) or created)
    has_schedule = bool(
        any(_sequence_contains_tool(sequence, t) for t in SCHEDULE_TOOLS) or scheduled
    )

    # Check-in
    low_risk = bool(trace.get("low_risk_quick_mode"))
    checkin_provided = bool(
        _checkin_looks_provided(checkin, checkin_norm)
        or trace.get("subjective_checkin_collected")
        or (trace.get("checkin_status") or {}).get("checkin_complete")
    )
    has_checkin_payload = bool(checkin)

    if not low_risk and not checkin_provided:
        if has_checkin_payload:
            missing_fields = checkin_norm.get("missing_required_fields") or []
            if missing_fields and strictness != "lenient":
                warnings.append(_violation(
                    "checkin_incomplete",
                    "warning",
                    f"Subjective check-in incomplete; missing: {', '.join(missing_fields)}.",
                ))
        else:
            missing_steps.append("subjective_checkin")
            if strictness != "lenient":
                warnings.append(_violation(
                    "checkin_missing",
                    "warning",
                    "Subjective check-in not recorded before daily workout decision.",
                ))
    elif checkin_provided and checkin_norm.get("missing_required_fields") and strictness != "lenient":
        missing_fields = list(checkin_norm.get("missing_required_fields") or [])
        pain = checkin.get("pain") or {}
        if "pain" in missing_fields and isinstance(pain.get("has_pain"), str):
            if pain.get("has_pain", "").lower() not in {"", "unknown"}:
                missing_fields = [f for f in missing_fields if f != "pain"]
        if missing_fields:
            warnings.append(_violation(
                "checkin_incomplete",
                "warning",
                f"Check-in marked complete but missing fields: {', '.join(missing_fields)}.",
            ))

    if _check_invented_pain(trace):
        violations.append(_violation(
            "invented_pain_false",
            "critical",
            "Pain was set to false without user confirmation.",
        ))
        unsafe_assumptions.append("pain_assumed_false")

    if _check_invented_available_minutes(trace):
        violations.append(_violation(
            "invented_available_minutes",
            "critical",
            "Available minutes were assumed without user input.",
        ))
        unsafe_assumptions.append("available_minutes_invented")

    pain_status = _pain_status_from_trace(trace)

    # Tool presence
    if not _sequence_contains_tool(sequence, ADJUST_TOOL):
        missing_steps.append(ADJUST_TOOL)

    if not _sequence_contains_tool(sequence, VALIDATION_TOOL) and (has_create or has_schedule):
        missing_steps.append(VALIDATION_TOOL)
        violations.append(_violation(
            "scheduled_without_validation",
            "critical",
            "Workout was created or scheduled without validate_training_decision.",
        ))

    if not standalone and not _sequence_contains_tool(sequence, PLAN_TOOL):
        missing_steps.append(PLAN_TOOL)
        if strictness == "strict":
            warnings.append(_violation(
                "plan_triathlon_week_missing",
                "warning",
                "plan_triathlon_week was not called before daily decision.",
            ))

    brief_called = _sequence_contains_tool(sequence, BRIEF_TOOL)
    brief_status = _norm(trace.get("daily_brief_status") or trace.get("today_brief_status") or "")
    if not brief_called:
        missing_steps.append(BRIEF_TOOL)
        if strictness != "lenient":
            warnings.append(_violation(
                "daily_brief_missing",
                "warning",
                "get_daily_training_brief was not called before decision.",
            ))
    elif _is_brief_empty(brief) or brief_status in {"empty", "unavailable", "unavailable - get_daily_training_brief errored"}:
        _append_data_gap(
            data_gaps,
            "daily_brief_empty",
            "get_daily_training_brief was called, but objective recovery data was unavailable or empty.",
        )
        if brief_status.startswith("unavailable") or trace.get("garmin_sync_missing"):
            _append_data_gap(
                data_gaps,
                "garmin_sync_missing_or_empty_brief",
                "Garmin watch sync missing or brief returned no objective recovery metrics.",
            )
    elif trace.get("daily_training_brief_today_status", "").startswith("errored"):
        _append_data_gap(
            data_gaps,
            "objective_recovery_data_unavailable",
            "get_daily_training_brief was called but errored or returned no usable metrics.",
        )

    if dry_run and not has_create and not has_schedule and not created and not scheduled:
        positive_signals.append("dry_run_respected_no_create_or_schedule")

    # Tool order
    adjust_idx = _tool_index(sequence, ADJUST_TOOL)
    validate_idx = _tool_index(sequence, VALIDATION_TOOL)
    brief_idx = _tool_index(sequence, BRIEF_TOOL)
    plan_idx = _tool_index(sequence, PLAN_TOOL)
    first_create_idx = next(
        (i for i, entry in enumerate(sequence) if _canonical_tool_name(
            str(_normalize_tool_entry(entry) or entry)
        ).startswith("create_")),
        None,
    )
    first_schedule_idx = next(
        (
            i for i, entry in enumerate(sequence)
            if _canonical_tool_name(str(_normalize_tool_entry(entry) or entry))
            in {_canonical_tool_name(t) for t in SCHEDULE_TOOLS}
        ),
        None,
    )

    if brief_idx is not None and adjust_idx is not None and brief_idx > adjust_idx:
        tool_order_violations.append("daily_brief_after_adjust")
        warnings.append(_violation(
            "tool_order_incorrect",
            "warning",
            "get_daily_training_brief should occur before adjust_today_workout.",
        ))

    if plan_idx is not None and adjust_idx is not None and plan_idx > adjust_idx and not standalone:
        tool_order_violations.append("plan_after_adjust")

    if validate_idx is not None:
        if first_create_idx is not None and validate_idx > first_create_idx:
            tool_order_violations.append("validate_after_create")
            violations.append(_violation(
                "validate_after_create",
                "critical",
                "validate_training_decision must occur before create_* tools.",
            ))
        if first_schedule_idx is not None and validate_idx > first_schedule_idx:
            tool_order_violations.append("validate_after_schedule")
            violations.append(_violation(
                "scheduled_without_validation",
                "critical",
                "Workout was scheduled without validate_training_decision before scheduling.",
            ))

    # Validation results vs actions
    val_level = _norm(validate.get("validation_level"))
    if val_level == "blocked" and (has_create or has_schedule or created or scheduled):
        violations.append(_violation(
            "scheduled_despite_blocked_validation",
            "critical",
            "Workout was created or scheduled despite blocked validation.",
        ))

    if validate.get("safe_to_schedule") is False and (has_schedule or scheduled):
        violations.append(_violation(
            "scheduled_when_not_safe",
            "critical",
            "schedule_workout or schedule_week called when safe_to_schedule is false.",
        ))

    if validate.get("safe_to_create_workouts") is False and (has_create or created):
        violations.append(_violation(
            "created_when_not_safe",
            "critical",
            "Workout was created when safe_to_create_workouts is false.",
        ))

    # Blocked actions from adjust
    for action in adjust.get("blocked_actions") or []:
        if _blocked_action_used(action, proposed) or _blocked_action_used(action, created):
            blocked_violations.append(action)
            violations.append(_violation(
                "blocked_action_used",
                "critical",
                f"Claude proposed or created a blocked action: {action}.",
            ))

    # Pain rules
    requires_pain = "pain" in (adjust.get("requires_user_confirmation_before") or [])
    sensitive_proposed = any(_is_sensitive_session(s) for s in proposed)
    run_proposed = any(_sport_family(s.get("sport", "")) == "run" for s in proposed)

    if pain_status == "yes" and run_proposed and not trace.get("manual_override_pain"):
        violations.append(_violation(
            "running_with_pain",
            "critical",
            "Running was proposed while pain was reported.",
        ))

    if pain_status == "unknown" and sensitive_proposed:
        msg = "Pain status unknown but run/hard/long/double was proposed without confirmation."
        if strictness == "strict":
            violations.append(_violation("pain_unknown_no_confirmation", "critical", msg))
        elif strictness == "normal":
            warnings.append(_violation("pain_unknown_no_confirmation", "warning", msg))
        else:
            warnings.append(_violation("pain_unknown_no_confirmation", "warning", msg))
        if requires_pain:
            unsafe_assumptions.append("pain_not_confirmed")

    if requires_pain and sensitive_proposed and not trace.get("user_pain_confirmed"):
        if strictness != "lenient":
            warnings.append(_violation(
                "pain_confirmation_missing",
                "warning",
                "User pain status should be confirmed before run/hard/long/double.",
            ))

    # Readiness / sleep
    readiness = _norm(brief.get("readiness_level") or "normal")
    sleep_h = brief.get("sleep_hours")
    if readiness in LOW_READINESS and any(_is_hard_session(s) for s in proposed):
        violations.append(_violation(
            "hard_with_low_readiness",
            "critical",
            "Hard session proposed with low readiness.",
        ))

    if sleep_h is not None and sleep_h < 6 and any(
        _norm(s.get("priority")) == "secondary" for s in proposed
    ):
        violations.append(_violation(
            "double_with_poor_sleep",
            "critical",
            "Double session proposed after poor sleep.",
        ))

    # Sunday swim
    day_name = _norm(
        (trace.get("planned_day") or {}).get("day")
        or trace.get("day")
        or ""
    )
    for s in proposed + created:
        if _sport_family(s.get("sport", "")) == "swim" and day_name in SWIM_FORBIDDEN_DAYS:
            violations.append(_violation(
                "swim_on_sunday",
                "critical",
                "Swim was proposed or created on Sunday.",
            ))

    # Secondary mandatory
    if _secondary_treated_as_required(proposed, trace):
        sev = "critical" if strictness == "strict" else "warning"
        violations.append(_violation(
            "secondary_treated_as_required",
            sev,
            "Secondary session was treated as mandatory.",
        ))

    # Invented metrics
    for s in proposed + created:
        if _session_has_invented_metrics(s):
            violations.append(_violation(
                "invented_training_metrics",
                "critical",
                "Proposed session contains invented pace/watts/CSS/FTP/HR zones.",
            ))
            unsafe_assumptions.append("invented_metrics_in_session")
            break

    if final.get("invented_metrics"):
        violations.append(_violation(
            "invented_metrics_in_response",
            "critical",
            "Final response claimed or used invented training metrics.",
        ))

    if final.get("claimed_unavailable_data") and not final.get("mentioned_uncertainty"):
        _append_data_gap(
            data_gaps,
            "uncertainty_not_communicated",
            "Unavailable Garmin data was not communicated to the athlete.",
        )

    return (
        violations,
        warnings,
        missing_steps,
        unsafe_assumptions,
        blocked_violations,
        tool_order_violations,
        data_gaps,
        positive_signals,
    )


def _audit_weekly_review(
    trace: dict,
    strictness: str,
) -> Tuple[List[dict], List[dict], List[str], List[str], List[str], List[str], List[dict], List[str]]:
    violations: List[dict] = []
    warnings: List[dict] = []
    missing_steps: List[str] = []
    unsafe_assumptions: List[str] = []
    blocked_violations: List[str] = []
    tool_order_violations: List[str] = []
    data_gaps: List[dict] = []

    sequence = list(trace.get("tool_sequence") or [])
    audit_available = bool(trace.get("schedule_audit_available"))
    audit_result = trace.get("audit_week_schedule_result") or trace.get("schedule_audit") or {}
    review = trace.get("weekly_coach_review_result") or {}
    final = trace.get("final_response_summary") or {}
    claude_load = _norm(trace.get("claude_suggested_load_change") or "")

    audit_idx = _tool_index(sequence, AUDIT_WEEK_TOOL)
    review_idx = _tool_index(sequence, WEEKLY_REVIEW_TOOL)

    if audit_available and not _sequence_contains_tool(sequence, AUDIT_WEEK_TOOL):
        missing_steps.append(AUDIT_WEEK_TOOL)
        warnings.append(_violation(
            "weekly_review_without_audit",
            "warning",
            "audit_week_schedule should be called before weekly_coach_review when data is available.",
        ))

    if audit_idx is not None and review_idx is not None and audit_idx > review_idx:
        tool_order_violations.append("audit_after_weekly_review")
        warnings.append(_violation(
            "tool_order_incorrect",
            "warning",
            "audit_week_schedule should occur before weekly_coach_review.",
        ))

    if audit_result and review.get("schedule_audit_used") is False:
        warnings.append(_violation(
            "schedule_audit_not_passed_to_review",
            "warning",
            "weekly_coach_review did not receive schedule_audit when available.",
        ))

    review_status = _norm(review.get("overall_status") or "")
    review_load = _norm(review.get("load_decision") or "")
    reduce_signals = {"reduce", "deload", "recovery_needed", "recovery"}
    if claude_load in {"increase", "small_increase", "progress", "increase_slightly"}:
        if review_status in reduce_signals or review_load in reduce_signals:
            violations.append(_violation(
                "load_increase_against_review",
                "critical",
                "Claude suggested load increase despite weekly review recommending reduce/recovery.",
            ))
        if audit_result:
            if audit_result.get("execution_quality_score", 100) < 70:
                warnings.append(_violation(
                    "load_increase_low_execution_score",
                    "warning",
                    "Load increase suggested despite low execution quality score.",
                ))
            if audit_result.get("schedule_alignment_score", 100) < 70:
                warnings.append(_violation(
                    "load_increase_low_alignment_score",
                    "warning",
                    "Load increase suggested despite low schedule alignment score.",
                ))
            for flag in audit_result.get("risk_flags") or []:
                if flag in {"missed_key_session", "missed_key_swim", "easy_session_executed_too_hard"}:
                    warnings.append(_violation(
                        "load_increase_with_audit_risk",
                        "warning",
                        f"Load increase suggested with audit risk flag: {flag}.",
                    ))

    if trace.get("pain_reported_this_week") and claude_load in {
        "increase", "small_increase", "progress", "increase_slightly",
    }:
        violations.append(_violation(
            "load_increase_with_pain",
            "critical",
            "Load increase suggested while pain was reported this week.",
        ))

    audit_gaps = audit_result.get("data_gaps") or []
    if audit_gaps and not final.get("mentioned_uncertainty"):
        for gap in audit_gaps:
            if isinstance(gap, str):
                _append_data_gap(data_gaps, gap, gap)
            elif isinstance(gap, dict):
                data_gaps.append(gap)
        warnings.append(_violation(
            "data_gaps_not_mentioned",
            "warning",
            "Claude should mention audit data gaps to the user.",
        ))

    if final.get("absolute_certainty_claimed"):
        unsafe_assumptions.append("scores_presented_as_certainty")

    focus = " ".join(str(x) for x in (trace.get("claude_focus_topics") or [])).lower()
    if any(term in focus for term in WEIGHT_LOSS_TERMS):
        violations.append(_violation(
            "weight_loss_focus",
            "warning",
            "Weekly review shifted focus to weight loss instead of performance/base.",
        ))

    if not trace.get("follow_up_questions_asked") and (audit_result.get("recommended_followups") or review.get("claude_mediator_hint")):
        if strictness == "strict":
            warnings.append(_violation(
                "missing_follow_up_questions",
                "warning",
                "Important follow-up questions were not asked after weekly review.",
            ))

    return (
        violations,
        warnings,
        missing_steps,
        unsafe_assumptions,
        blocked_violations,
        tool_order_violations,
        data_gaps,
        [],
    )


def _audit_planning_only(
    trace: dict,
    strictness: str,
) -> Tuple[List[dict], List[dict], List[str], List[str], List[str], List[str], List[dict], List[str]]:
    violations: List[dict] = []
    warnings: List[dict] = []
    missing_steps: List[str] = []
    unsafe_assumptions: List[str] = []
    blocked_violations: List[str] = []
    tool_order_violations: List[str] = []
    data_gaps: List[dict] = []

    sequence = list(trace.get("tool_sequence") or [])
    plan = trace.get("plan_triathlon_week_result") or trace.get("planned_week") or {}
    scheduled = trace.get("scheduled_workouts") or []

    if any(_sequence_contains_tool(sequence, t) for t in SCHEDULE_TOOLS) or scheduled:
        violations.append(_violation(
            "planning_scheduled_workouts",
            "critical",
            "plan_triathlon_week must not schedule workouts by itself.",
        ))

    if plan.get("garmin_upload") is not False and plan.get("sends_to_garmin") is not False:
        if plan:
            violations.append(_violation(
                "garmin_upload_not_false",
                "critical",
                "Weekly plan must have garmin_upload=false.",
            ))

    for key in PLANNING_REQUIRED_KEYS:
        if plan and key not in plan:
            missing_steps.append(key)
            warnings.append(_violation(
                "missing_plan_contract_key",
                "warning",
                f"Plan missing required key: {key}.",
            ))

    plan_text = json.dumps(plan, default=str).lower()
    if any(term in plan_text for term in WEIGHT_LOSS_TERMS):
        violations.append(_violation(
            "weight_loss_in_plan",
            "critical" if strictness != "lenient" else "warning",
            "Plan contains weight_loss or fat_loss focus.",
        ))

    for day in plan.get("days") or []:
        if _norm(day.get("day")) in SWIM_FORBIDDEN_DAYS:
            primary = (day.get("primary") or {}).get("suggested") or {}
            if _sport_family(primary.get("sport", "")) == "swim":
                violations.append(_violation(
                    "swim_on_sunday",
                    "critical",
                    "Sunday primary swim in weekly template.",
                ))
        if day.get("secondary", {}).get("enabled") is True:
            warnings.append(_violation(
                "secondary_enabled_by_default",
                "warning",
                "Secondary should remain optional, not enabled by default.",
            ))

    return (
        violations,
        warnings,
        missing_steps,
        unsafe_assumptions,
        blocked_violations,
        tool_order_violations,
        data_gaps,
        [],
    )


def _audit_schedule_audit(trace: dict, strictness: str):
    """Light audit for schedule_audit-only sessions."""
    violations: List[dict] = []
    warnings: List[dict] = []
    missing_steps: List[str] = []
    sequence = list(trace.get("tool_sequence") or [])

    if not _sequence_contains_tool(sequence, AUDIT_WEEK_TOOL):
        missing_steps.append(AUDIT_WEEK_TOOL)

    audit = trace.get("audit_week_schedule_result") or trace.get("schedule_audit") or {}
    data_gaps: List[dict] = []
    if not audit:
        missing_steps.append("audit_result")
    else:
        for gap in audit.get("data_gaps") or []:
            if isinstance(gap, str):
                _append_data_gap(data_gaps, gap, gap)
            elif isinstance(gap, dict):
                data_gaps.append(gap)

    return violations, warnings, missing_steps, [], [], [], data_gaps, []


def _compute_scores(
    session_type: str,
    trace: dict,
    violations: List[dict],
    warnings: List[dict],
    missing_steps: List[str],
    blocked_violations: List[str],
    tool_order_violations: List[str],
    unsafe_assumptions: List[str],
    data_gaps: List[dict],
    strictness: str,
) -> Tuple[float, float, float]:
    protocol = 100.0
    safety = 100.0
    integrity = 100.0

    sequence = trace.get("tool_sequence") or []
    dry_run = bool(trace.get("dry_run"))

    if session_type == "daily_workout_decision":
        if not _sequence_contains_tool(sequence, ADJUST_TOOL):
            protocol -= 20
        if (
            not _sequence_contains_tool(sequence, VALIDATION_TOOL)
            and not dry_run
            and (_create_tools(sequence) or trace.get("scheduled_workouts"))
        ):
            protocol -= 25
        if any(v["code"] == "scheduled_despite_blocked_validation" for v in violations):
            protocol -= 30
        if "subjective_checkin" in missing_steps and not trace.get("low_risk_quick_mode"):
            protocol -= 15
        elif any(w["code"] == "checkin_incomplete" for w in warnings):
            protocol -= 5
        if (
            not _sequence_contains_tool(sequence, PLAN_TOOL)
            and not trace.get("standalone_workout")
            and strictness == "strict"
        ):
            protocol -= 5
        if not _sequence_contains_tool(sequence, BRIEF_TOOL) and strictness == "strict":
            protocol -= 5
        protocol -= 10 * len(tool_order_violations)

    if session_type == "weekly_review":
        if trace.get("schedule_audit_available") and not _sequence_contains_tool(sequence, AUDIT_WEEK_TOOL):
            protocol -= 10

    safety -= 40 * len(blocked_violations)
    if any(v["code"] == "running_with_pain" for v in violations):
        safety -= 30
    if any(v["code"] == "hard_with_low_readiness" for v in violations):
        safety -= 25
    if any(v["code"] == "pain_unknown_no_confirmation" and v["severity"] == "critical" for v in violations):
        safety -= 20
    if any(v["code"] == "swim_on_sunday" for v in violations):
        safety -= 20
    if any(v["code"] == "secondary_treated_as_required" for v in violations):
        safety -= 15

    if any(v["code"] == "invented_pain_false" for v in violations):
        integrity -= 30
    if any(v["code"].startswith("invented") for v in violations):
        integrity -= 25
    if any(v["code"] == "invented_available_minutes" for v in violations):
        integrity -= 15
    if unsafe_assumptions:
        integrity -= 10 * min(len(unsafe_assumptions), 3)
    if any(v["code"] == "data_gaps_not_mentioned" for v in warnings):
        integrity -= 10

    _ = data_gaps

    return (
        max(0.0, round(protocol, 1)),
        max(0.0, round(safety, 1)),
        max(0.0, round(integrity, 1)),
    )


def _overall_status(
    violations: List[dict],
    warnings: List[dict],
    protocol: float,
    safety: float,
    integrity: float,
    missing_steps: List[str],
    data_gaps: List[dict],
    trace: dict,
) -> str:
    sequence = trace.get("tool_sequence") or []
    if not sequence and not trace.get("plan_triathlon_week_result"):
        return "insufficient_data"

    critical = [v for v in violations if v.get("severity") == "critical"]
    if critical:
        return "failed"

    avg = (protocol + safety + integrity) / 3
    if avg < 60:
        return "failed"

    protocol_warnings = [
        w for w in warnings
        if w.get("code") not in {"session_type_alias_used", "invalid_strictness_defaulted_to_normal"}
    ]

    if data_gaps and not violations and not missing_steps and not protocol_warnings:
        return "warning"

    if avg < 85 or violations or protocol_warnings or missing_steps:
        return "warning"
    return "pass"


def _repair_actions(
    violations: List[dict],
    missing_steps: List[str],
    blocked_violations: List[str],
    session_type: str,
) -> List[str]:
    actions: List[str] = []
    codes = {v["code"] for v in violations}

    if "scheduled_without_validation" in codes or VALIDATION_TOOL in missing_steps:
        actions.append("Call validate_training_decision before creating or scheduling.")
    if "scheduled_despite_blocked_validation" in codes:
        actions.append("Do not schedule because validation was blocked.")
    if "blocked_action_used" in codes:
        for ba in blocked_violations:
            actions.append(f"Remove blocked action: {ba}.")
    if "running_with_pain" in codes:
        actions.append("Remove running from proposed sessions or get explicit pain clearance.")
    if "pain_unknown_no_confirmation" in codes:
        actions.append("Ask user about pain before running, hard, long or double sessions.")
    if "secondary_treated_as_required" in codes:
        actions.append("Rebuild proposed_sessions without mandatory secondary.")
    if session_type == "weekly_review" and AUDIT_WEEK_TOOL in missing_steps:
        actions.append("Run audit_week_schedule before weekly_coach_review.")
    if "invented_pain_false" in codes:
        actions.append("Reset pain status to unknown until user confirms.")
    if "invented_available_minutes" in codes:
        actions.append("Ask user for available_minutes instead of assuming.")
    if "swim_on_sunday" in codes:
        actions.append("Remove Sunday swim from proposed or scheduled sessions.")

    return _unique(actions)


def _recommended_next_prompt(
    overall: str,
    session_type: str,
    violations: List[dict],
) -> Optional[str]:
    if overall != "failed":
        return None
    critical = [v for v in violations if v.get("severity") == "critical"]
    if not critical:
        return None

    if session_type == "daily_workout_decision":
        return (
            "Re-run the decision flow from check-in, get_daily_training_brief, "
            "adjust_today_workout and validate_training_decision before creating "
            "or scheduling any workout."
        )
    if session_type == "weekly_review":
        return (
            "Re-run audit_week_schedule, pass schedule_audit to weekly_coach_review, "
            "and align Claude's load recommendation with review output."
        )
    if session_type == "planning_only":
        return "Regenerate plan_triathlon_week with garmin_upload=false and performance focus."
    return "Repair protocol violations before proceeding with the coaching session."


def _mediator_hint(overall: str, repair: List[str], session_type: str) -> dict:
    if overall == "failed":
        return {
            "summary": "Critical protocol violation. Claude should not proceed until the flow is repaired.",
            "must_not_do": _unique([
                "Do not create or schedule workouts after blocked validation.",
                "Do not use blocked actions.",
                "Do not invent pain, time or training metrics.",
            ]),
            "should_do_next": repair[:3] or ["Restart the decision flow from adjust_today_workout."],
        }
    if overall == "warning":
        return {
            "summary": "Protocol mostly followed with warnings. Claude should address gaps before scheduling.",
            "must_not_do": ["Do not ignore missing check-in or validation warnings."],
            "should_do_next": repair[:3] or ["Confirm open items with the user before scheduling."],
        }
    if overall == "insufficient_data":
        return {
            "summary": "Insufficient session trace for a full audit.",
            "must_not_do": ["Do not assume protocol compliance without trace data."],
            "should_do_next": ["Provide tool_sequence and key MCP outputs in session_trace."],
        }
    return {
        "summary": "Protocol followed. Claude can proceed with the final user-facing coaching message.",
        "must_not_do": [],
        "should_do_next": [
            "Keep using validate_training_decision before scheduling.",
        ] if session_type == "daily_workout_decision" else [
            "Pass schedule_audit to weekly_coach_review when available.",
        ],
    }


def audit_coach_mediator_session(
    session_type: str,
    session_trace: dict,
    strictness: str = "normal",
    athlete_profile: Optional[dict] = None,
) -> dict:
    """Audit whether Claude followed the Coach Engine mediator protocol."""
    _ = {**DEFAULT_ATHLETE_PROFILE, **(athlete_profile or {})}
    trace = normalize_session_trace(session_trace or {})

    strict, strictness_warnings = normalize_strictness(strictness)
    st, st_meta = normalize_session_type(session_type or trace.get("session_type"))

    if st is None:
        return _unknown_session_type_response(session_type, strict, strictness_warnings)

    alias_warnings = list(st_meta.get("warnings") or [])

    if st == "daily_workout_decision":
        audit_fn = _audit_daily_workout_decision
    elif st == "weekly_review":
        audit_fn = _audit_weekly_review
    elif st == "planning_only":
        audit_fn = _audit_planning_only
    else:
        audit_fn = _audit_schedule_audit

    (
        violations,
        warnings,
        missing_steps,
        unsafe_assumptions,
        blocked_violations,
        tool_order_violations,
        data_gaps,
        positive_signals,
    ) = audit_fn(trace, strict)

    protocol, safety, integrity = _compute_scores(
        st,
        trace,
        violations,
        warnings,
        missing_steps,
        blocked_violations,
        tool_order_violations,
        unsafe_assumptions,
        data_gaps,
        strict,
    )

    overall = _overall_status(
        violations, warnings, protocol, safety, integrity, missing_steps, data_gaps, trace,
    )
    repair = _repair_actions(violations, missing_steps, blocked_violations, st)

    all_warnings = alias_warnings + strictness_warnings + warnings

    result = {
        "audit_type": AUDIT_TYPE,
        "session_type": st,
        "strictness": strict,
        "overall_status": overall,
        "protocol_score": protocol,
        "safety_score": safety,
        "data_integrity_score": integrity,
        "violations": violations,
        "warnings": all_warnings,
        "missing_steps": _unique(missing_steps),
        "unsafe_assumptions": _unique(unsafe_assumptions),
        "blocked_action_violations": blocked_violations,
        "tool_order_violations": tool_order_violations,
        "data_gaps": _unique_data_gaps(data_gaps),
        "positive_signals": _unique(positive_signals),
        "required_repair_actions": repair,
        "recommended_next_prompt": _recommended_next_prompt(overall, st, violations),
        "claude_mediator_hint": _mediator_hint(overall, repair, st),
        "valid_session_types": sorted(VALID_SESSION_TYPES),
        "accepted_aliases": _accepted_aliases_public(),
    }
    if st_meta.get("session_type_normalized_from"):
        result["session_type_normalized_from"] = st_meta["session_type_normalized_from"]
    return result
