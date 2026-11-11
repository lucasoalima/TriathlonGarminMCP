"""
Subjective daily check-in schema and normalization for the triathlon coach engine.

Pain and available time are never assumed when missing — they stay unknown until
the athlete (via Claude) provides them.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

DAILY_CHECKIN_SCHEMA: Dict[str, Any] = {
    "version": "1",
    "purpose": "Required before adjust_today_workout when planning run/hard/long/double sessions.",
    "required_fields": [
        "pain",
        "fatigue_0_10",
        "available_minutes",
        "schedule_constraints",
    ],
    "optional_fields_with_defaults": {
        "motivation_0_10": 5,
        "stress_0_10": 5,
    },
    "nullable_fields": [
        "sleep_quality_subjective_0_10",
        "notes",
    ],
    "pain_field": {
        "has_pain": "true | false | null (unknown if omitted)",
        "location": "optional string",
        "severity_0_10": "optional 0-10 when has_pain is true",
    },
    "schedule_constraints": {
        "description": "Free text: agenda limits, no pool/gym, equipment missing, etc.",
        "example": "Só tenho 45 min; sem academia; piscina fechada",
    },
    "claude_prompt_short_pt": (
        "Antes de ajustar o treino: está com alguma dor? "
        "Fadiga de 0 a 10? Quanto tempo tem hoje? "
        "Alguma restrição de agenda ou equipamento?"
    ),
    "rules": [
        "Never default has_pain to false when omitted.",
        "Never invent available_minutes.",
        "If pain or available time is unknown, ask before run/hard/long/double sessions.",
        "motivation and stress may default to 5 if omitted.",
    ],
}

CHECKIN_PROMPT_SHORT_PT = DAILY_CHECKIN_SCHEMA["claude_prompt_short_pt"]

CHECKIN_FIELD_SPECS: Dict[str, Dict[str, str]] = {
    "pain": {
        "description": "Dor atual. Não assumir false se omitido.",
        "missing_behavior": "unknown",
    },
    "fatigue_0_10": {
        "description": "Fadiga subjetiva de 0 a 10.",
    },
    "available_minutes": {
        "description": "Tempo disponível hoje em minutos. Não inventar.",
    },
    "schedule_constraints": {
        "description": (
            "Restrições de agenda, piscina, bike, academia, equipamento ou viagem."
        ),
    },
}


def get_daily_checkin_schema() -> dict:
    """Return a JSON-serializable check-in schema for Claude or clients."""
    return {
        "schema_type": "daily_subjective_checkin",
        "version": DAILY_CHECKIN_SCHEMA["version"],
        "purpose": DAILY_CHECKIN_SCHEMA["purpose"],
        "required_fields": list(DAILY_CHECKIN_SCHEMA["required_fields"]),
        "optional_fields_with_defaults": dict(
            DAILY_CHECKIN_SCHEMA["optional_fields_with_defaults"]
        ),
        "nullable_fields": list(DAILY_CHECKIN_SCHEMA["nullable_fields"]),
        "prompt_pt": CHECKIN_PROMPT_SHORT_PT,
        "claude_prompt_short_pt": CHECKIN_PROMPT_SHORT_PT,
        "fields": deepcopy(CHECKIN_FIELD_SPECS),
        "pain_field": dict(DAILY_CHECKIN_SCHEMA["pain_field"]),
        "schedule_constraints_help": dict(DAILY_CHECKIN_SCHEMA["schedule_constraints"]),
        "rules": list(DAILY_CHECKIN_SCHEMA["rules"]),
    }


def get_checkin_prompt(language: str = "pt") -> str:
    if language.startswith("pt"):
        return CHECKIN_PROMPT_SHORT_PT
    return (
        "Before adjusting today's workout: any pain? Fatigue 0-10? "
        "How much time do you have? Any schedule or equipment constraints?"
    )


def _parse_pain(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {"has_pain": None, "status": "unknown"}
    if isinstance(raw, bool):
        return {
            "has_pain": raw,
            "status": "yes" if raw else "no",
        }
    if not isinstance(raw, dict):
        return {"has_pain": None, "status": "unknown"}

    has_pain = raw.get("has_pain")
    if has_pain is None and "status" in raw:
        st = str(raw.get("status", "")).lower()
        if st in {"yes", "true", "sim"}:
            has_pain = True
        elif st in {"no", "false", "nao", "não"}:
            has_pain = False

    if has_pain is True:
        status = "yes"
    elif has_pain is False:
        status = "no"
    else:
        status = "unknown"

    out: Dict[str, Any] = {"has_pain": has_pain, "status": status}
    if raw.get("location") is not None:
        out["location"] = raw.get("location")
    if raw.get("severity_0_10") is not None:
        out["severity_0_10"] = int(raw.get("severity_0_10"))
    return out


def normalize_subjective_checkin(raw: Optional[dict] = None) -> dict:
    """Normalize raw check-in; apply safe defaults only where allowed."""
    raw = raw or {}
    missing: List[str] = []

    pain = _parse_pain(raw.get("pain"))
    if pain["status"] == "unknown":
        missing.append("pain")

    fatigue = raw.get("fatigue_0_10")
    if fatigue is None:
        missing.append("fatigue_0_10")
    else:
        fatigue = max(0, min(10, int(fatigue)))

    available = raw.get("available_minutes")
    if available is None:
        missing.append("available_minutes")
    else:
        available = max(0, int(available))

    constraints = raw.get("schedule_constraints")
    if constraints is None or (isinstance(constraints, str) and not constraints.strip()):
        missing.append("schedule_constraints")
    elif isinstance(constraints, dict):
        constraints = constraints.get("notes") or constraints.get("description") or ""
        if not str(constraints).strip():
            missing.append("schedule_constraints")
    else:
        constraints = str(constraints).strip()

    motivation = raw.get("motivation_0_10")
    if motivation is None:
        motivation = DAILY_CHECKIN_SCHEMA["optional_fields_with_defaults"]["motivation_0_10"]
    else:
        motivation = max(0, min(10, int(motivation)))

    stress = raw.get("stress_0_10")
    if stress is None:
        stress = DAILY_CHECKIN_SCHEMA["optional_fields_with_defaults"]["stress_0_10"]
    else:
        stress = max(0, min(10, int(stress)))

    sleep_q = raw.get("sleep_quality_subjective_0_10")
    if sleep_q is not None:
        sleep_q = max(0, min(10, int(sleep_q)))

    normalized: Dict[str, Any] = {
        "pain": pain,
        "fatigue_0_10": fatigue,
        "available_minutes": available,
        "schedule_constraints": constraints if "schedule_constraints" not in missing else None,
        "motivation_0_10": motivation,
        "stress_0_10": stress,
        "sleep_quality_subjective_0_10": sleep_q,
        "notes": raw.get("notes"),
        "checkin_complete": len(missing) == 0,
        "missing_required_fields": missing,
    }
    return normalized


def checkin_required_before(
    normalized_checkin: dict,
    session_tags: List[str],
) -> List[str]:
    """Return fields Claude must clarify before certain session types."""
    needs: List[str] = []
    missing = set(normalized_checkin.get("missing_required_fields") or [])
    pain = normalized_checkin.get("pain") or {}

    high_risk = {"run", "hard", "long", "double"}
    if not high_risk.intersection(set(session_tags)):
        return needs

    if pain.get("status") == "unknown" or "pain" in missing:
        needs.append("pain")
    if "available_minutes" in missing and {"long", "double"}.intersection(session_tags):
        needs.append("available_minutes")
    return needs
