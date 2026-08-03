"""In-memory job cache, disk persistence, thread lifecycle, and output GC."""

from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Optional

from path_safety import OUTPUT_BASE, _PROTECTED_OUTPUT_NAMES

jobs: dict = {}
_active_job_threads: set = set()
_job_thread_lock = threading.Lock()
_job_state_lock = threading.RLock()
_job_heartbeats: dict[str, float] = {}
_JOB_HEARTBEAT_STALE_SECONDS = 120


def _job_path(job_id: str) -> Path:
    return OUTPUT_BASE / job_id / "job.json"


def _add_job_warning(job: dict, message: str) -> None:
    with _job_state_lock:
        job.setdefault("warnings", []).append(message)


def _save_job(job_id: str) -> None:
    with _job_state_lock:
        job = jobs.get(job_id)
        if not job:
            return
        _job_heartbeats[job_id] = time.time()
        path = _job_path(job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        with open(tmp, "w") as f:
            json.dump(job, f, indent=2)
        tmp.replace(path)


class JobCancelled(Exception):
    """Operator requested cooperative cancellation of a generation job."""


def _raise_if_cancelled(job_id: str) -> None:
    job = jobs.get(job_id)
    if job is None:
        job = _load_job(job_id)
    if job and job.get("cancel_requested"):
        raise JobCancelled(job_id)


def _load_job(job_id: str) -> Optional[dict]:
    if job_id in jobs:
        return jobs[job_id]
    path = _job_path(job_id)
    if not path.exists():
        return None
    try:
        with open(path) as f:
            job = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    jobs[job_id] = job
    return job


def _job_thread_is_stale(job_id: str) -> bool:
    last = _job_heartbeats.get(job_id)
    if last is None:
        return True
    return (time.time() - last) > _JOB_HEARTBEAT_STALE_SECONDS


def _start_job_thread(job_id: str, target) -> bool:
    with _job_thread_lock:
        if job_id in _active_job_threads:
            if not _job_thread_is_stale(job_id):
                return False
            _active_job_threads.discard(job_id)
        _active_job_threads.add(job_id)

    _job_heartbeats[job_id] = time.time()

    def _runner():
        try:
            target(job_id)
        finally:
            with _job_thread_lock:
                _active_job_threads.discard(job_id)

    threading.Thread(target=_runner, daemon=True).start()
    return True


def _output_max_age_days() -> Optional[float]:
    """Return retention days from env, or None when GC is disabled."""
    raw = (os.getenv("SHADOWCAST_OUTPUT_MAX_AGE_DAYS") or "").strip()
    if not raw:
        return None
    try:
        days = float(raw)
    except ValueError:
        logging.warning("Invalid SHADOWCAST_OUTPUT_MAX_AGE_DAYS=%r; output GC disabled", raw)
        return None
    if days <= 0:
        return None
    return days


def cleanup_old_job_outputs(
    *,
    output_base: Optional[Path] = None,
    max_age_days: Optional[float] = None,
    now_ts: Optional[float] = None,
) -> int:
    """Delete aged job dirs under OUTPUT_BASE. Returns count removed.

    Off unless SHADOWCAST_OUTPUT_MAX_AGE_DAYS > 0 (or max_age_days is passed).
    Skips protected names, root files (e.g. analytics.json), and running/active jobs.
    Never touches backend/credentials/.
    """
    base = OUTPUT_BASE if output_base is None else output_base
    days = _output_max_age_days() if max_age_days is None else max_age_days
    if days is None or days <= 0 or not base.exists():
        return 0

    cutoff = (time.time() if now_ts is None else now_ts) - (days * 86400.0)
    with _job_thread_lock:
        active_ids = set(_active_job_threads)
    deleted = 0

    for job_dir in list(base.iterdir()):
        if not job_dir.is_dir():
            continue
        name = job_dir.name
        if name in _PROTECTED_OUTPUT_NAMES or name in {".", ".."}:
            continue
        job_json = job_dir / "job.json"
        if not job_json.is_file():
            continue
        try:
            mtime = job_json.stat().st_mtime
        except OSError:
            continue
        if mtime >= cutoff:
            continue
        if name in active_ids:
            continue
        mem_job = jobs.get(name) or {}
        if mem_job.get("status") == "running":
            continue
        try:
            disk_job = json.loads(job_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            disk_job = {}
        if isinstance(disk_job, dict) and disk_job.get("status") == "running":
            continue
        try:
            shutil.rmtree(job_dir)
        except OSError as exc:
            logging.warning("Output GC failed for %s: %s", name, exc)
            continue
        jobs.pop(name, None)
        deleted += 1
        logging.info("Output GC removed aged job dir: %s", name)
    return deleted
