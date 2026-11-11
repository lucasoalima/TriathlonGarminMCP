"""
triathlon_coach — camada determinística de coaching de triatlo (regras + guardrails + auditoria).

Projetada para rodar como conjunto de ferramentas de um agente LLM (via MCP): o motor
computa/valida/classifica/sinaliza; o LLM (Claude) é o mediador que decide a mensagem final.
Lógica pura, sem I/O — testável e reprodutível offline.
"""
from triathlon_coach import checkin, engine, mediator_audit, planning  # noqa: F401

__all__ = ["checkin", "engine", "mediator_audit", "planning"]
__version__ = "0.1.0"
