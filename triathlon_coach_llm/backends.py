"""
Backends plugaveis para a tarefa do mediator.

- FakeBackend: baseline deterministico e OFFLINE (heuristica simples). Sempre disponivel;
  serve de linha de base ("simple baseline vs LLM") e permite rodar a comparacao em CI.
- OllamaBackend: modelo local via Ollama (http://localhost:11434). Requer Ollama instalado.
- ClaudeBackend: API da Anthropic. Requer ANTHROPIC_API_KEY.

Interface comum: .name, .available(), .decide(case) -> {"verdict", "raw", "latency_ms"}.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Dict

from triathlon_coach_llm.mediator_task import SYSTEM_PROMPT, build_user_prompt, parse_verdict


class LLMBackend:
    name = "base"

    def available(self) -> bool:
        raise NotImplementedError

    def decide(self, case: Dict) -> Dict:
        raise NotImplementedError


class FakeBackend(LLMBackend):
    """Baseline heuristico simples e deterministico (NAO chama o motor)."""
    name = "fake_baseline"

    def available(self) -> bool:
        return True

    def decide(self, case: Dict) -> Dict:
        t0 = time.perf_counter()
        dc = case["day_context"]
        sessions = case["proposed_sessions"]
        readiness = str(dc.get("readiness_level", "normal")).lower()
        sleep_h = dc.get("sleep_hours")
        pain = str(dc.get("pain_status", "")).lower()
        hard_words = {"hard", "very_hard", "vo2", "threshold", "interval", "race"}
        has_hard = any(
            str(s.get("intensity", "")).lower() in hard_words
            or str(s.get("session_type", "")).lower() in hard_words
            for s in sessions
        )
        has_run = any(str(s.get("sport", "")).lower() in {"run", "running"} for s in sessions)
        verdict = "safe"
        if has_hard and readiness in {"low", "poor", "very_low"}:
            verdict = "unsafe"
        elif has_hard and sleep_h is not None and sleep_h < 6:
            verdict = "unsafe"
        elif has_hard and dc.get("previous_day_hard"):
            verdict = "unsafe"
        elif pain == "yes" and has_run:
            verdict = "unsafe"
        dt = (time.perf_counter() - t0) * 1000
        return {"verdict": verdict, "raw": f"heuristic:{verdict}", "latency_ms": round(dt, 3)}


class OllamaBackend(LLMBackend):
    """Modelo local via Ollama. Config: OLLAMA_HOST, OLLAMA_MODEL."""
    name = "ollama"

    def __init__(self):
        self.host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.model = os.environ.get("OLLAMA_MODEL", "llama3.1")

    def available(self) -> bool:
        try:
            with urllib.request.urlopen(self.host + "/api/tags", timeout=1.5) as r:
                return r.status == 200
        except Exception:
            return False

    def decide(self, case: Dict) -> Dict:
        body = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(case)},
            ],
            "stream": False,
            "options": {"temperature": 0},
            "format": "json",
        }).encode("utf-8")
        req = urllib.request.Request(self.host + "/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read().decode("utf-8"))
        dt = (time.perf_counter() - t0) * 1000
        text = (data.get("message") or {}).get("content", "")
        return {"verdict": parse_verdict(text), "raw": text, "latency_ms": round(dt, 1)}


class ClaudeBackend(LLMBackend):
    """API da Anthropic. Config: ANTHROPIC_API_KEY, ANTHROPIC_MODEL."""
    name = "claude"

    def __init__(self):
        self.key = os.environ.get("ANTHROPIC_API_KEY")
        self.model = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")

    def available(self) -> bool:
        if not self.key:
            return False
        try:
            import anthropic  # noqa: F401
            return True
        except Exception:
            return False

    def decide(self, case: Dict) -> Dict:
        import anthropic
        client = anthropic.Anthropic(api_key=self.key)
        t0 = time.perf_counter()
        msg = client.messages.create(
            model=self.model, max_tokens=200, temperature=0,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_user_prompt(case)}],
        )
        dt = (time.perf_counter() - t0) * 1000
        text = "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")
        return {"verdict": parse_verdict(text), "raw": text, "latency_ms": round(dt, 1)}


ALL_BACKENDS = [FakeBackend, OllamaBackend, ClaudeBackend]


def available_backends():
    out = []
    for cls in ALL_BACKENDS:
        try:
            b = cls()
            if b.available():
                out.append(b)
        except Exception:
            pass
    return out
