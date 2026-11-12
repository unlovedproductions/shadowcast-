"""Job lifecycle: non-daemon threads, stages, interrupt marking."""

import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from job_store import (  # noqa: E402
    JobCancelled,
    _active_job_threads,
    _raise_if_cancelled,
    _start_job_thread,
    jobs,
    request_shutdown_all_jobs,
    set_job_stage,
)


def test_start_job_thread_is_non_daemon(monkeypatch, tmp_path):
    monkeypatch.setattr("job_store.OUTPUT_BASE", tmp_path)
    monkeypatch.setattr("job_store._job_path", lambda jid: tmp_path / jid / "job.json")
    started = threading.Event()
    finished = threading.Event()

    def target(job_id: str):
        started.set()
        finished.wait(timeout=2.0)

    job_id = "stage1"
    jobs[job_id] = {"status": "running", "cancel_requested": False}
    (tmp_path / job_id).mkdir()
    assert _start_job_thread(job_id, target) is True
    assert started.wait(timeout=2.0)
    with threading.Lock():
        # Thread object stored as non-daemon
        from job_store import _job_thread_objs

        t = _job_thread_objs.get(job_id)
        assert t is not None
        assert t.daemon is False
    finished.set()
    t.join(timeout=2.0)


def test_set_job_stage_persists(tmp_path, monkeypatch):
    monkeypatch.setattr("job_store.OUTPUT_BASE", tmp_path)
    monkeypatch.setattr("job_store._job_path", lambda jid: tmp_path / jid / "job.json")
    job_id = "stg"
    (tmp_path / job_id).mkdir()
    jobs[job_id] = {"status": "running"}
    set_job_stage(job_id, "scripts")
    assert jobs[job_id]["current_stage"] == "scripts"
    assert jobs[job_id]["stage_history"][-1]["stage"] == "scripts"
    saved = (tmp_path / job_id / "job.json").read_text(encoding="utf-8")
    assert '"scripts"' in saved


def test_request_shutdown_marks_interrupted(tmp_path, monkeypatch):
    monkeypatch.setattr("job_store.OUTPUT_BASE", tmp_path)
    monkeypatch.setattr("job_store._job_path", lambda jid: tmp_path / jid / "job.json")
    gate = threading.Event()
    job_id = "intr"

    def target(jid: str):
        try:
            while not jobs[jid].get("cancel_requested"):
                time.sleep(0.05)
            _raise_if_cancelled(jid)
        except JobCancelled:
            pass
        finally:
            gate.set()

    (tmp_path / job_id).mkdir()
    jobs[job_id] = {"status": "running", "cancel_requested": False}
    assert _start_job_thread(job_id, target)
    time.sleep(0.1)
    request_shutdown_all_jobs(wait_seconds=2.0)
    assert gate.wait(timeout=2.0)
    assert jobs[job_id]["status"] == "interrupted"
    assert jobs[job_id]["cancel_requested"] is True
