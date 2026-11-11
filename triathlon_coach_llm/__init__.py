"""
Camada de IA/LLM sobre o motor deterministico:

- backends: Fake (offline, baseline), Ollama (modelo local), Claude (API).
- mediator_task: monta o prompt e extrai o veredito SAFE/UNSAFE do modelo.
- compare: roda a tarefa em cada backend e mede concordancia com o motor e com o gold.

O motor deterministico (triathlon_coach) e o ORACULO/guardrail; os LLMs sao avaliados
contra ele e contra os rotulos humanos. Assim medimos IA de forma quantitativa.
"""
from triathlon_coach_llm import backends, mediator_task  # noqa: F401

__all__ = ["backends", "mediator_task"]
