"""
Triathlon week planning — structured weekly template for Garmin MCP.

Returns a coaching scaffold JSON only. Does NOT upload or schedule on Garmin.
"""

from __future__ import annotations

import datetime
import json
from copy import deepcopy
from typing import Any, Dict, List, Optional, Union

DAY_NAMES = (
    "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday",
)

VOLUME_SCALE = {"low": 0.8, "medium": 1.0, "high": 1.15}

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
    "weekly_hours_target": "low_to_moderate",
    "aggressiveness": "conservative",
}

DEFAULT_GOAL: Dict[str, Any] = {
    "long_term_goal": "ironman_70_3",
    "current_focus": [
        "performance",
        "aerobic_base",
        "return_to_performance",
        "consistency",
        "durability",
        "injury_prevention",
        "race_readiness_foundation",
    ],
}

DEFAULT_AVAILABILITY: Dict[str, Any] = {
    "swim_not_allowed_days": ["sunday"],
    "swim_preferred_days": ["tuesday", "thursday"],
    "swim_optional_days": ["saturday"],
    "weekend_swim_limited": True,
    "friday_is_not_forced_rest": True,
}

DEFAULT_PREFERENCES: Dict[str, Any] = {
    "sunday_default": "rest",
    "volume": "medium",
    "bike_by_hr_zone": True,
    "no_power_meter": True,
}

SECONDARY_POLICY: Dict[str, Any] = {
    "default": "optional",
    "requires_readiness": "normal_or_good",
    "skip_if": [
        "poor_sleep",
        "low_hrv",
        "high_fatigue",
        "pain_reported",
        "previous_session_was_hard",
        "primary_session_is_long_or_hard",
    ],
}

ADJUSTMENT_RULES: Dict[str, Any] = {
    "if_low_readiness": [
        "remove_secondary_session",
        "convert_hard_to_easy",
        "replace_strength_with_mobility_or_core",
        "keep_technique_swim_if_low_load",
    ],
    "if_very_low_readiness": [
        "rest_or_mobility_only",
    ],
    "if_pain_reported": [
        "avoid_running",
        "prefer_bike_easy_or_rest",
        "suggest_manual_review",
    ],
    "if_performance_focus": [
        "prioritize_aerobic_development",
        "protect_run_load",
        "fuel_key_sessions",
        "recover_to_absorb_training",
        "avoid_excessive_high_intensity",
    ],
    "if_returning_after_break": [
        "start_conservative",
        "increase_volume_gradually",
        "avoid_back_to_back_hard_days",
    ],
}

SWIM_POLICY: Dict[str, Any] = {
    "preferred_days": ["tuesday", "thursday"],
    "optional_days": ["saturday"],
    "forbidden_days": ["sunday"],
    "pace_source": "use_get_swim_css_pace_if_needed",
    "do_not_invent_css": True,
}

COACH_FLOW_HINT: List[str] = [
    "Collect subjective check-in before adjusting today's workout.",
    "Use get_daily_training_brief before materializing today's workouts.",
    "Call adjust_today_workout with planned day + brief + check-in.",
    "Only add secondary sessions when adjust_today_workout allows it.",
    "Call validate_training_decision before create_*_workout and schedule.",
    "For swim pace targets, call get_swim_css_pace — do not invent CSS in this template.",
    "Schedule with schedule_workout or schedule_week.",
    "Review adherence with get_workout_compliance and weekly_coach_review.",
    "This template does not upload or schedule workouts by itself.",
]

COACH_ENGINE_CONTRACT: Dict[str, Any] = {
    "mcp_role": "technical_rules_engine",
    "claude_role": "coach_mediator_and_final_decision",
    "planner_role": "weekly_structure_only",
    "does_not_upload_to_garmin": True,
    "does_not_make_final_daily_decision": True,
    "requires_adjust_today_workout_before_materializing_daily_workout": True,
    "requires_validate_training_decision_before_schedule": True,
}

PERFORMANCE_POLICY: Dict[str, Any] = {
    "priority": "sustainable_performance_development",
    "principles": [
        "build_aerobic_base_before_intensity",
        "prioritize_consistency",
        "protect_run_load",
        "fuel_key_sessions",
        "recover_to_absorb_training",
        "develop_durability_before_race_specificity",
    ],
}

FUELING_POLICY: Dict[str, Any] = {
    "goal": "support_performance_and_recovery",
    "fuel_key_sessions": True,
    "fuel_long_sessions": True,
    "avoid_fasted_hard_sessions": True,
    "hydrate_on_long_sessions": True,
    "future_70_3_nutrition_practice": True,
}

DISCIPLINE_GUARDRAILS: Dict[str, Any] = {
    "run": {
        "increase_volume_slowly": True,
        "avoid_back_to_back_run_intensity": True,
        "prefer_frequency_before_intensity": True,
        "block_running_if_pain_reported": True,
    },
    "bike": {
        "can_absorb_more_aerobic_volume_than_run": True,
        "use_hr_zones_without_power_meter": True,
        "prefer_z2_for_base_phase": True,
    },
    "swim": {
        "prioritize_technique_before_volume": True,
        "preferred_days": ["tuesday", "thursday"],
        "optional_days": ["saturday"],
        "forbidden_days": ["sunday"],
        "do_not_invent_css": True,
        "use_get_swim_css_pace_if_needed": True,
    },
    "strength": {
        "target_sessions_per_week": 2,
        "avoid_heavy_legs_before_key_run": True,
        "support_durability_and_injury_prevention": True,
    },
}

PROGRESSION_POLICY: Dict[str, Any] = {
    "default": "conservative_performance_build",
    "increase_load_only_if": [
        "compliance_above_80_percent",
        "no_pain_reported",
        "sleep_stable",
        "hrv_not_suppressed",
        "easy_sessions_executed_easy",
        "previous_week_felt_manageable",
    ],
    "hold_or_reduce_if": [
        "pain_reported",
        "low_readiness_multiple_days",
        "missed_key_sessions",
        "excessive_fatigue",
        "run_load_increased_too_fast",
        "easy_sessions_executed_too_hard",
    ],
}

SUBJECTIVE_CHECKIN_POLICY: Dict[str, Any] = {
    "required_before_adjusting_today": True,
    "never_default_pain_to_false": True,
    "never_invent_available_minutes": True,
    "optional_defaults": {
        "motivation_0_10": 5,
        "stress_0_10": 5,
    },
    "claude_prompt_short_pt": (
        "Antes de ajustar o treino: está com alguma dor? "
        "Fadiga de 0 a 10? Quanto tempo tem hoje? "
        "Alguma restrição de agenda ou equipamento?"
    ),
    "fields": [
        "pain",
        "fatigue_0_10",
        "available_minutes",
        "schedule_constraints",
        "motivation_0_10",
        "stress_0_10",
        "sleep_quality_subjective_0_10",
        "notes",
    ],
    "use_get_daily_checkin_schema_tool": True,
}

RACE_SPECIFIC_ROADMAP: Dict[str, Any] = {
    "target": "ironman_70_3",
    "current_phase": "general_base_and_performance_foundation",
    "not_priority_yet": [
        "race_pace_work",
        "long_bricks",
        "open_water_specificity",
        "aero_position_duration",
        "race_nutrition_simulation",
    ],
    "future_priorities": [
        "brick_training",
        "open_water_skills",
        "long_bike_progression",
        "run_off_bike_adaptation",
        "fueling_strategy",
        "transition_practice",
    ],
}

FUTURE_TOOLS_HINT: List[str] = []

COMPLEMENT_LIBRARY: Dict[str, Dict[str, Any]] = {
    "strength_general": {
        "category": "strength",
        "type": "general_strength",
        "title": "Fortalecimento geral",
        "description": (
            "Musculação com foco em pernas, posterior, glúteo, estabilidade unilateral "
            "e prevenção de lesão. Carga moderada."
        ),
        "duration_minutes": 30,
        "intensity": "moderate",
        "load_impact": "moderate",
        "focus_areas": ["legs", "posterior", "glutes", "unilateral_stability"],
    },
    "strength_legs": {
        "category": "strength",
        "type": "leg_strength",
        "title": "Força de pernas e estabilidade",
        "description": (
            "Agachamento/controle unilateral, glúteo e panturrilha. Evitar carga alta "
            "se o primary do dia for corrida forte ou longa."
        ),
        "duration_minutes": 30,
        "intensity": "moderate",
        "load_impact": "moderate",
        "focus_areas": ["legs", "glutes", "calves", "knee_stability"],
    },
    "core_short": {
        "category": "core",
        "type": "core_stability",
        "title": "Core curto",
        "description": "Prancha, side plank, dead bug, bird dog — controle e estabilidade.",
        "duration_minutes": 15,
        "intensity": "easy_to_moderate",
        "load_impact": "low",
        "focus_areas": ["plank", "side_plank", "dead_bug", "bird_dog"],
    },
    "prehab": {
        "category": "prehab",
        "type": "injury_prevention",
        "title": "Prehab / prevenção",
        "description": (
            "Glúteo médio, quadril, panturrilha, tibial anterior, tornozelo, "
            "estabilidade de joelho, ombro/escápula."
        ),
        "duration_minutes": 20,
        "intensity": "easy",
        "load_impact": "low",
        "focus_areas": [
            "hip", "glute_med", "calves", "tibialis", "ankle", "knee", "shoulder_scapula",
        ],
    },
    "mobility": {
        "category": "mobility",
        "type": "mobility",
        "title": "Mobilidade",
        "description": "Quadril, tornozelo, torácica, ombro — alongamentos dinâmicos, baixa carga.",
        "duration_minutes": 15,
        "intensity": "easy",
        "load_impact": "low",
        "focus_areas": ["hip", "ankle", "thoracic", "shoulder"],
    },
}

KEY_SESSIONS_TEMPLATE: List[Dict[str, Any]] = [
    {
        "day": "saturday",
        "sport": "bike_or_run",
        "reason": "main_endurance_session",
    },
    {
        "day": "tuesday",
        "sport": "swim",
        "reason": "technique_and_aerobic_swim_development",
    },
    {
        "day": "wednesday",
        "sport": "run_or_bike",
        "reason": "main_midweek_aerobic_stimulus",
    },
]


def _parse_week_start(week_start: Union[str, datetime.date]) -> datetime.date:
    if isinstance(week_start, datetime.date):
        return week_start
    return datetime.date.fromisoformat(week_start)


def _scale_minutes(minutes: int, scale: float) -> int:
    if minutes <= 0:
        return 0
    return max(5, int(round(minutes * scale / 5) * 5))


def _scale_session(session: Dict[str, Any], scale: float) -> Dict[str, Any]:
    s = deepcopy(session)
    if "duration_minutes" in s:
        s["duration_minutes"] = _scale_minutes(int(s["duration_minutes"]), scale)
    return s


def _merge_config(
    athlete_profile: Optional[Dict[str, Any]],
    goal: Optional[Dict[str, Any]],
    availability: Optional[Dict[str, Any]],
    preferences: Optional[Dict[str, Any]],
    legacy_profile: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Merge all config layers; legacy_profile supports old `profile=` kwarg."""
    legacy = legacy_profile or {}
    prefs = {**DEFAULT_PREFERENCES, **(preferences or {}), **legacy}
    return {
        "athlete_profile": {**DEFAULT_ATHLETE_PROFILE, **(athlete_profile or {}), **legacy},
        "goal": {**DEFAULT_GOAL, **(goal or {})},
        "availability": {**DEFAULT_AVAILABILITY, **(availability or {})},
        "preferences": prefs,
    }


def _endurance_option(
    option_id: str,
    sport: str,
    session_type: str,
    title: str,
    description: str,
    duration: int,
    intensity: str,
    load_impact: str,
    priority: str = "normal",
) -> Dict[str, Any]:
    return {
        "id": option_id,
        "sport": sport,
        "type": session_type,
        "title": title,
        "description": description,
        "duration_minutes": duration,
        "intensity": intensity,
        "priority": priority,
        "load_impact": load_impact,
    }


def _primary_block(
    options: List[Dict[str, Any]],
    suggested_id: str,
    scale: float,
) -> Dict[str, Any]:
    scaled = [_scale_session(o, scale) for o in options]
    return {
        "required": True,
        "pick_min": 1,
        "pick_max": 1,
        "suggested_id": suggested_id,
        "options": scaled,
        "suggested": next(o for o in scaled if o["id"] == suggested_id),
    }


def _secondary_block(
    options: List[Dict[str, Any]],
    scale: float,
    enabled: bool = False,
) -> Dict[str, Any]:
    return {
        "enabled": enabled,
        "policy": "optional_only_if_readiness_is_good",
        "secondary_policy": deepcopy(SECONDARY_POLICY),
        "options": [_scale_session(o, scale) for o in options],
    }


def _complement_block(
    complement_key: str,
    *,
    required: bool = True,
    scale: float = 1.0,
    alternatives: Optional[List[str]] = None,
) -> Dict[str, Any]:
    base = deepcopy(COMPLEMENT_LIBRARY[complement_key])
    base["duration_minutes"] = _scale_minutes(base["duration_minutes"], scale)
    base["required"] = required
    alts = alternatives or [complement_key]
    options = []
    for key in alts:
        opt = deepcopy(COMPLEMENT_LIBRARY[key])
        opt["id"] = key
        opt["duration_minutes"] = _scale_minutes(opt["duration_minutes"], scale)
        options.append(opt)
    base["id"] = complement_key
    base["options"] = options
    base["suggested"] = next(o for o in options if o["id"] == complement_key)
    return base


def _build_training_day(
    *,
    day_name: str,
    date_str: str,
    focus: str,
    day_objective: str,
    primary: Dict[str, Any],
    secondary: Dict[str, Any],
    complement: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "day": day_name,
        "date": date_str,
        "focus": focus,
        "day_objective": day_objective,
        "primary": primary,
        "secondary": secondary,
        "complement": complement,
    }


def _build_recovery_day(
    day_name: str,
    date_str: str,
    suggested_id: str,
    scale: float,
) -> Dict[str, Any]:
    options = [
        _scale_session({
            "id": "rest",
            "sport": "rest",
            "type": "rest",
            "title": "Descanso total",
            "description": "Recuperação completa — opção padrão sugerida.",
            "duration_minutes": 0,
            "intensity": "recovery",
            "load_impact": "none",
        }, scale),
        _scale_session({
            "id": "recovery_run",
            "sport": "run",
            "type": "recovery",
            "title": "Recovery run",
            "description": "Corrida muito leve de recuperação ativa.",
            "duration_minutes": 30,
            "intensity": "easy",
            "load_impact": "low",
        }, scale),
        _scale_session({
            "id": "recovery_bike",
            "sport": "bike",
            "type": "recovery",
            "title": "Recovery bike",
            "description": "Pedalada muito leve de recuperação ativa.",
            "duration_minutes": 35,
            "intensity": "easy",
            "load_impact": "low",
        }, scale),
    ]
    suggested = next(o for o in options if o["id"] == suggested_id)
    return {
        "day": day_name,
        "date": date_str,
        "focus": "recovery_day",
        "day_objective": "Recuperar e preparar a próxima semana sem carga alta.",
        "recovery": {
            "required": True,
            "pick_min": 1,
            "pick_max": 1,
            "suggested_id": suggested_id,
            "options": options,
            "suggested": suggested,
            "no_swim": True,
            "no_hard_sessions": True,
        },
    }


def _weekly_guardrails(cfg: Dict[str, Any]) -> Dict[str, Any]:
    aggressive = cfg["athlete_profile"].get("aggressiveness", "conservative")
    max_hard = 1 if aggressive == "conservative" else 2
    return {
        "max_hard_sessions": max_hard,
        "max_long_sessions": 1,
        "min_recovery_days": 1,
        "strength_sessions_target": 2,
        "core_sessions_target": "2_to_4",
        "prehab_sessions_target": "2_to_3",
        "mobility_sessions_target": "as_needed_low_load",
        "avoid_hard_days_in_a_row": True,
        "avoid_two_hard_runs_in_a_row": True,
        "secondary_sessions_are_optional": True,
        "do_not_auto_add_volume": True,
        "prioritize_consistency_over_intensity": True,
    }


def _training_context(cfg: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "training_phase": "base",
        "week_type": "foundation",
        "load_target": cfg["athlete_profile"].get("weekly_hours_target", "low_to_moderate"),
        "aggressiveness": cfg["athlete_profile"].get("aggressiveness", "conservative"),
        "intensity_distribution_hint": {
            "easy": 80,
            "moderate": 15,
            "hard": 5,
        },
    }


def _build_days(
    week_start: datetime.date,
    cfg: Dict[str, Any],
) -> List[Dict[str, Any]]:
    scale = VOLUME_SCALE.get(cfg["preferences"].get("volume", "medium"), 1.0)
    sunday_default = cfg["preferences"].get("sunday_default", "rest")
    sunday_map = {
        "rest": "rest",
        "recovery_run": "recovery_run",
        "recovery_bike": "recovery_bike",
    }
    sunday_id = sunday_map.get(sunday_default, "rest")

    run_bike_secondary = [
        _endurance_option(
            "secondary_run", "run", "endurance",
            "Corrida curta leve (opcional)",
            "Só com readiness normal/bom e dia anterior controlado.",
            25, "easy", "low",
        ),
        _endurance_option(
            "secondary_bike", "bike", "endurance",
            "Bike leve (opcional)",
            "Alternativa de baixo impacto ao segundo estímulo.",
            30, "easy", "low",
        ),
    ]

    days: List[Dict[str, Any]] = []
    weekday_builders = [
        # Monday
        lambda d, ds: _build_training_day(
            day_name=d, date_str=ds, focus="aerobic_base_plus_strength",
            day_objective="Começar a semana com base aeróbica sem intensidade excessiva.",
            primary=_primary_block([
                _endurance_option(
                    "primary_run", "run", "endurance",
                    "Corrida leve/moderada",
                    "Sessão aeróbica base para retomar consistência.",
                    40, "easy_to_moderate", "moderate",
                ),
                _endurance_option(
                    "primary_bike", "bike", "endurance",
                    "Bike leve/moderada",
                    "Pedalada aeróbica base.",
                    40, "easy_to_moderate", "moderate",
                ),
            ], "primary_run", scale),
            secondary=_secondary_block(run_bike_secondary, scale),
            complement=_complement_block("strength_general", scale=scale),
        ),
        # Tuesday
        lambda d, ds: _build_training_day(
            day_name=d, date_str=ds, focus="swim_technique_plus_core_prehab",
            day_objective="Técnica de natação com carga controlada.",
            primary=_primary_block([
                _endurance_option(
                    "primary_swim", "swim", "technique",
                    "Natação técnica/endurance",
                    "Foco em técnica e eficiência — ritmo via get_swim_css_pace depois.",
                    40, "easy_to_moderate", "moderate",
                ),
            ], "primary_swim", scale),
            secondary=_secondary_block(run_bike_secondary, scale),
            complement=_complement_block(
                "core_short", scale=scale, alternatives=["core_short", "prehab"],
            ),
        ),
        # Wednesday
        lambda d, ds: _build_training_day(
            day_name=d, date_str=ds, focus="midweek_aerobic_stimulus_plus_strength",
            day_objective="Principal estímulo aeróbico/moderado da semana — conservador.",
            primary=_primary_block([
                _endurance_option(
                    "primary_run", "run", "endurance",
                    "Corrida aeróbica moderada",
                    "Estímulo principal da semana em corrida — sem intensidade agressiva.",
                    45, "easy_to_moderate", "moderate", priority="key",
                ),
                _endurance_option(
                    "primary_bike", "bike", "endurance",
                    "Bike aeróbica moderada",
                    "Estímulo principal da semana em bike — sem intensidade agressiva.",
                    45, "easy_to_moderate", "moderate", priority="key",
                ),
            ], "primary_bike", scale),
            secondary=_secondary_block(run_bike_secondary, scale),
            complement=_complement_block(
                "strength_legs", scale=scale,
                alternatives=["strength_legs", "prehab"],
            ),
        ),
        # Thursday
        lambda d, ds: _build_training_day(
            day_name=d, date_str=ds, focus="swim_consolidation_plus_mobility",
            day_objective="Consolidar natação e manter frequência.",
            primary=_primary_block([
                _endurance_option(
                    "primary_swim", "swim", "endurance",
                    "Natação técnica/endurance",
                    "Volume sustentável — ritmo via get_swim_css_pace depois.",
                    40, "easy_to_moderate", "moderate",
                ),
            ], "primary_swim", scale),
            secondary=_secondary_block(run_bike_secondary, scale),
            complement=_complement_block(
                "mobility", scale=scale, alternatives=["mobility", "core_short", "prehab"],
            ),
        ),
        # Friday
        lambda d, ds: _build_training_day(
            day_name=d, date_str=ds, focus="easy_endurance_plus_prehab",
            day_objective="Fechar a semana útil sem acumular fadiga alta — não é descanso fixo.",
            primary=_primary_block([
                _endurance_option(
                    "primary_run", "run", "endurance",
                    "Corrida leve",
                    "Sessão aeróbica leve.",
                    35, "easy", "low",
                ),
                _endurance_option(
                    "primary_bike", "bike", "endurance",
                    "Bike leve/moderada",
                    "Pedalada leve a moderada.",
                    35, "easy", "low",
                ),
            ], "primary_run", scale),
            secondary=_secondary_block(run_bike_secondary, scale),
            complement=_complement_block(
                "prehab", scale=scale, alternatives=["prehab", "mobility", "core_short"],
            ),
        ),
        # Saturday
        lambda d, ds: _build_training_day(
            day_name=d, date_str=ds, focus="long_endurance_plus_optional_swim",
            day_objective="Principal sessão de endurance da semana.",
            primary=_primary_block([
                _endurance_option(
                    "primary_run_long", "run", "long",
                    "Corrida longa fácil",
                    "Treino longo da semana — intensidade fácil a moderada.",
                    70, "easy_to_moderate", "high", priority="key",
                ),
                _endurance_option(
                    "primary_bike_long", "bike", "long",
                    "Bike longa fácil",
                    "Treino longo da semana — intensidade fácil a moderada.",
                    70, "easy_to_moderate", "high", priority="key",
                ),
            ], "primary_bike_long", scale),
            secondary=_secondary_block([
                _endurance_option(
                    "secondary_swim", "swim", "technique",
                    "Natação opcional",
                    "Só se piscina disponível, energia sobrar e readiness ok.",
                    35, "easy", "low",
                ),
                *run_bike_secondary,
            ], scale),
            complement=_complement_block("mobility", required=False, scale=scale),
        ),
        # Sunday
        lambda d, ds: _build_recovery_day(d, ds, sunday_id, scale),
    ]

    for offset in range(7):
        current = week_start + datetime.timedelta(days=offset)
        weekday = current.weekday()
        days.append(weekday_builders[weekday](DAY_NAMES[weekday], current.isoformat()))

    return days


def _count_complement_categories(days: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"strength": 0, "core": 0, "prehab": 0, "mobility": 0}
    for day in days:
        comp = day.get("complement")
        if not comp or not comp.get("required", True):
            if comp and not comp.get("required"):
                cat = comp.get("category")
                if cat in counts:
                    counts[cat] += 0  # optional complement not counted as target
            continue
        cat = comp.get("category") or comp.get("suggested", {}).get("category")
        if cat in counts:
            counts[cat] += 1
    return counts


def _swim_on_day(day: Dict[str, Any], slot: str) -> bool:
    if day.get("recovery"):
        return False
    block = day.get(slot)
    if not block:
        return False
    if slot == "primary":
        opts = block.get("options", [])
        suggested = block.get("suggested", {})
        return suggested.get("sport") == "swim" or any(o.get("sport") == "swim" for o in opts)
    if slot == "secondary":
        return any(o.get("sport") == "swim" for o in block.get("options", []))
    return False


def build_triathlon_week_template(
    week_start: Union[str, datetime.date],
    athlete_profile: Optional[Dict[str, Any]] = None,
    goal: Optional[Dict[str, Any]] = None,
    availability: Optional[Dict[str, Any]] = None,
    preferences: Optional[Dict[str, Any]] = None,
    *,
    profile: Optional[Dict[str, Any]] = None,
) -> dict:
    """Build a 7-day triathlon week coaching template."""
    start = _parse_week_start(week_start)
    cfg = _merge_config(athlete_profile, goal, availability, preferences, profile)
    days = _build_days(start, cfg)
    complement_counts = _count_complement_categories(days)

    return {
        "week_start": start.isoformat(),
        "week_end": (start + datetime.timedelta(days=6)).isoformat(),
        "plan_type": "triathlon_week_template",
        "garmin_upload": False,
        "sends_to_garmin": False,
        "goal": cfg["goal"],
        "athlete_profile": cfg["athlete_profile"],
        "training_context": _training_context(cfg),
        "weekly_guardrails": _weekly_guardrails(cfg),
        "availability_constraints": cfg["availability"],
        "swim_policy": deepcopy(SWIM_POLICY),
        "secondary_policy": deepcopy(SECONDARY_POLICY),
        "coach_engine_contract": deepcopy(COACH_ENGINE_CONTRACT),
        "performance_policy": deepcopy(PERFORMANCE_POLICY),
        "fueling_policy": deepcopy(FUELING_POLICY),
        "discipline_guardrails": deepcopy(DISCIPLINE_GUARDRAILS),
        "progression_policy": deepcopy(PROGRESSION_POLICY),
        "subjective_checkin_policy": deepcopy(SUBJECTIVE_CHECKIN_POLICY),
        "race_specific_roadmap": deepcopy(RACE_SPECIFIC_ROADMAP),
        "key_sessions": deepcopy(KEY_SESSIONS_TEMPLATE),
        "adjustment_rules": deepcopy(ADJUSTMENT_RULES),
        "coach_flow_hint": list(COACH_FLOW_HINT),
        "future_tools_hint": list(FUTURE_TOOLS_HINT),
        "notes": [
            "Template genérico de assessoria — não prescreve pace, watts, CSS ou zonas exatas.",
            "Secondary nunca é incluído por defeito; o coach decide com get_daily_training_brief.",
            "Não envia nem agenda treinos no Garmin.",
        ],
        "summary": {
            "training_days": sum(1 for d in days if "recovery" not in d),
            "strength_complement_days": complement_counts["strength"],
            "core_complement_days": complement_counts["core"],
            "prehab_complement_days": complement_counts["prehab"],
            "mobility_complement_days": complement_counts["mobility"],
            "swim_primary_days": sum(
                1 for d in days if _swim_on_day(d, "primary")
            ),
            "swim_optional_secondary_days": sum(
                1 for d in days if _swim_on_day(d, "secondary")
            ),
            "secondary_enabled_by_default": False,
            "suggested_weekly_minutes": sum(
                d.get("primary", {}).get("suggested", {}).get("duration_minutes", 0)
                + d.get("complement", {}).get("suggested", {}).get("duration_minutes", 0)
                for d in days
                if d.get("complement", {}).get("required", True)
            ) + (
                days[-1].get("recovery", {}).get("suggested", {}).get("duration_minutes", 0)
            ),
        },
        "days": days,
    }


def build_triathlon_week_plan(
    week_start: str,
    *,
    overrides: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """Deprecated alias — use build_triathlon_week_template."""
    return build_triathlon_week_template(
        week_start,
        preferences=config,
        profile={"overrides": overrides} if overrides else None,
    )


garmin_client = None


def configure(client):
    global garmin_client
    garmin_client = client


def register_tools(app):
    @app.tool()
    async def plan_triathlon_week(
        week_start: str,
        athlete_profile: Optional[Dict[str, Any]] = None,
        goal: Optional[Dict[str, Any]] = None,
        availability: Optional[Dict[str, Any]] = None,
        preferences: Optional[Dict[str, Any]] = None,
        profile: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate a conservative triathlon week coaching template (JSON only).

        Does NOT create, upload or schedule workouts on Garmin Connect.

        Returns a 7-day structure with primary/secondary/complement blocks,
        weekly guardrails, adjustment rules, key sessions and coach flow hints.

        Designed for: Ironman 70.3 long-term, current focus on athletic performance,
        aerobic base, consistency, durability, return to performance and injury prevention.

        Args:
            week_start: First day of the 7-day block (YYYY-MM-DD)
            athlete_profile: level, aggressiveness, weekly_hours_target, current_focus
            goal: long_term_goal, current_focus
            availability: swim day constraints, friday_is_not_forced_rest, etc.
            preferences: volume (low/medium/high), sunday_default (rest/recovery_run/recovery_bike)
            profile: legacy single dict (merged into preferences/athlete_profile)
        """
        try:
            datetime.date.fromisoformat(week_start)
        except ValueError:
            return f"Invalid week_start '{week_start}': expected YYYY-MM-DD."

        plan = build_triathlon_week_template(
            week_start,
            athlete_profile=athlete_profile,
            goal=goal,
            availability=availability,
            preferences=preferences,
            profile=profile,
        )
        return json.dumps(plan, indent=2)

    return app
