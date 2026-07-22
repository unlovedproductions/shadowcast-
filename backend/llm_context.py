"""Per-job LLM call context for telemetry and warnings."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Optional

_job_id: ContextVar[Optional[str]] = ContextVar("shadowcast_job_id", default=None)
_pending_calls: ContextVar[list[dict[str, Any]]] = ContextVar("shadowcast_llm_calls", default=[])


def set_job_context(job_id: str) -> None:
    _job_id.set(job_id)
    _pending_calls.set([])


def clear_job_context() -> None:
    _job_id.set(None)
    _pending_calls.set([])


def get_job_id() -> Optional[str]:
    return _job_id.get()


def append_llm_call(record: dict[str, Any]) -> None:
    calls = _pending_calls.get()
    calls.append(record)


def drain_pending_calls() -> list[dict[str, Any]]:
    calls = list(_pending_calls.get())
    _pending_calls.set([])
    return calls


def merge_llm_calls_into_job(jobs: dict, job_id: str) -> None:
    pending = drain_pending_calls()
    if not pending:
        return
    job = jobs.get(job_id)
    if not job:
        return
    job.setdefault("llm_calls", []).extend(pending)
