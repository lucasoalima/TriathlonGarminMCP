"""
A tarefa do "mediator": dado o contexto do dia e as sessoes propostas, decidir se e
SEGURO prescrever. Usada para avaliar LLMs contra o motor deterministico (oraculo) e o gold.
"""
from __future__ import annotations

import json
import re
from typing import Dict

SYSTEM_PROMPT = (
    "Voce e um assistente de seguranca de treino de endurance (triatlo). "
    "Recebe o contexto do dia de um atleta e as sessoes propostas. "
    "Decida se e SEGURO prescrever essas sessoes hoje, priorizando seguranca sobre performance. "
    "Regras gerais: nao prescrever sessao dura com prontidao baixa, apos sono < 6h, "
    "com dor reportada (corrida), ou em dias duros consecutivos; evitar volume intenso excessivo. "
    "Responda ESTRITAMENTE em JSON: {\"verdict\": \"safe\"|\"unsafe\", \"reason\": \"<curto>\"}."
)


def build_user_prompt(case: Dict) -> str:
    payload = {
        "day_context": case["day_context"],
        "proposed_sessions": case["proposed_sessions"],
        "weekly_context": case.get("weekly_context"),
    }
    return "Contexto:\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n\nResponda apenas o JSON."


def parse_verdict(text: str) -> str:
    """Extrai 'safe'/'unsafe' de uma resposta de LLM (tolerante a ruido)."""
    if not text:
        return "unknown"
    t = text.lower()
    m = re.search(r'"verdict"\s*:\s*"(safe|unsafe)"', t)
    if m:
        return m.group(1)
    # fallback: primeira ocorrencia das palavras
    has_unsafe = re.search(r'\bunsafe\b|\binseguro\b', t)
    has_safe = re.search(r'\bsafe\b|\bseguro\b', t)
    if has_unsafe and (not has_safe or has_unsafe.start() < has_safe.start()):
        return "unsafe"
    if has_safe:
        return "safe"
    return "unknown"
