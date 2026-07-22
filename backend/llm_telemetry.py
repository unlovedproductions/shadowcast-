"""LLM request telemetry and optional per-job token budgets."""

from __future__ import annotations

import os
from typing import Any, Optional

from llm_config import get_config

_job_token_usage: dict[str, int] = {}


def estimate_chars(system: str, user: str, response: str = "") -> dict[str, int]:
    return {
        "prompt_chars": len(system or "") + len(user or ""),
        "response_chars": len(response or ""),
    }


def get_job_token_budget() -> Optional[int]:
    raw = os.getenv("LLM_MAX_TOKENS_PER_JOB", "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def record_job_chars(job_id: str, prompt_chars: int, response_chars: int) -> None:
    approx_tokens = int((prompt_chars + response_chars) / 4)
    _job_token_usage[job_id] = _job_token_usage.get(job_id, 0) + approx_tokens


def job_budget_exceeded(job_id: str) -> tuple[bool, str]:
    budget = get_job_token_budget()
    if budget is None:
        return False, ""
    used = _job_token_usage.get(job_id, 0)
    if used >= budget:
        return True, f"LLM token budget exceeded ({used}/{budget} approx tokens)"
    return False, ""


def build_call_record(
    *,
    call_label: str,
    provider: str,
    model: str,
    latency_ms: float,
    prompt_chars: int,
    response_chars: int,
    parse_ok: bool,
    retry_index: int,
    validator_pass: Optional[bool],
    validator_errors: list[str],
    fallback_used: bool,
    error: str = "",
) -> dict[str, Any]:
    cfg = get_config()
    return {
        "label": call_label or "chat_completion_json",
        "provider": provider,
        "model": model or cfg.model,
        "latency_ms": round(latency_ms, 1),
        "prompt_chars": prompt_chars,
        "response_chars": response_chars,
        "parse_ok": parse_ok,
        "retry_index": retry_index,
        "validator_pass": validator_pass,
        "validator_errors": validator_errors[:5],
        "fallback_used": fallback_used,
        "error": error,
    }
