"""
LLM simulado (offline): um 'mediator' falso gera um session_trace e a auditoria
determinística (audit_coach_mediator_session) pega a sessão não-conforme.

Demonstra o padrão central do projeto: o LLM age, o motor determinístico audita.
Não depende de rede nem de chaves.
"""
from triathlon_coach.engine import validate_training_decision
from triathlon_coach.mediator_audit import audit_coach_mediator_session


def _compliant_trace():
    """Mediator que segue o protocolo: checkin -> brief -> validate -> cria treino fácil."""
    sessions = [{"sport": "bike", "type": "endurance", "duration_minutes": 45,
                 "intensity": "easy", "priority": "primary"}]
    day_ctx = {"readiness_level": "normal", "sleep_hours": 7.0, "pain_status": "no", "day": "monday"}
    v = validate_training_decision(sessions, day_ctx)
    return {
        "user_checkin": {"provided": True, "pain": {"has_pain": False, "pain_confirmed_by_user": True},
                         "fatigue_0_10": 4, "available_minutes": 60, "schedule_constraints": "none"},
        "tool_sequence": ["get_daily_checkin_schema", "get_daily_training_brief",
                          "plan_triathlon_week", "adjust_today_workout",
                          "validate_training_decision", "create_easy_bike_workout"],
        "planned_day": {"day": "monday", "date": "2026-06-16"},
        "daily_training_brief_summary": {"readiness_level": "normal", "sleep_hours": 7.0, "hrv_status": "balanced"},
        "adjust_today_workout_result": {"decision": "keep", "blocked_actions": [], "risk_flags": [],
                                        "requires_user_confirmation_before": []},
        "claude_proposed_sessions": sessions,
        "validate_training_decision_result": v,
        "created_workouts": [{"tool": "create_easy_bike_workout", "sport": "bike", "duration_minutes": 45}],
        "scheduled_workouts": [],
        "final_response_summary": {"mentioned_uncertainty": False, "explained_reasoning": True,
                                   "claimed_unavailable_data": False, "invented_metrics": False},
    }


def _noncompliant_trace():
    """Mediator que PULA o safety gate e cria treino forte direto (violação de protocolo)."""
    sessions = [{"sport": "run", "type": "interval", "duration_minutes": 50,
                 "intensity": "hard", "priority": "primary"}]
    t = _compliant_trace()
    t["tool_sequence"] = ["get_daily_training_brief", "create_easy_bike_workout"]  # sem checkin/validate
    t["claude_proposed_sessions"] = sessions
    t.pop("validate_training_decision_result", None)  # pulou o guardrail
    t["created_workouts"] = [{"tool": "create_strength_workout", "sport": "run", "duration_minutes": 50}]
    return t


def test_compliant_session_passes_audit():
    res = audit_coach_mediator_session("daily_workout_decision", _compliant_trace())
    assert res["overall_status"] in {"pass", "warn"}


def test_noncompliant_session_is_flagged():
    res = audit_coach_mediator_session("daily_workout_decision", _noncompliant_trace())
    # a auditoria deve penalizar: status pior OU violações/etapas faltando
    flagged = (
        res["overall_status"] == "fail"
        or res.get("violations")
        or res.get("missing_steps")
    )
    assert flagged, f"auditoria não pegou sessão não-conforme: {res.get('overall_status')}"


def test_audit_scores_compliant_higher_than_noncompliant():
    good = audit_coach_mediator_session("daily_workout_decision", _compliant_trace())
    bad = audit_coach_mediator_session("daily_workout_decision", _noncompliant_trace())
    assert good["protocol_score"] >= bad["protocol_score"]
