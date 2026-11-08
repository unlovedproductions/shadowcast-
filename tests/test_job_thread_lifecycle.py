"""Regression: live workers must never be replaced by a second thread."""

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import job_store  # noqa: E402


def test_stale_heartbeat_does_not_dual_start_live_worker(monkeypatch):
    job_id = "dual-writer-guard"
    started = threading.Event()
    release = threading.Event()
    runs = []

    def _target(_jid: str) -> None:
        runs.append("start")
        started.set()
        release.wait(timeout=5)
        runs.append("done")

    monkeypatch.setitem(job_store._job_heartbeats, job_id, time.time() - 10_000)
    assert job_store._start_job_thread(job_id, _target) is True
    assert started.wait(timeout=2)

    # Heartbeat is ancient, but the worker is still alive — must refuse.
    monkeypatch.setitem(job_store._job_heartbeats, job_id, time.time() - 10_000)
    assert job_store._job_thread_is_alive(job_id) is True
    assert job_store._job_thread_is_stale(job_id) is False
    assert job_store._start_job_thread(job_id, _target) is False

    release.set()
    deadline = time.time() + 2
    while job_store._job_thread_is_alive(job_id) and time.time() < deadline:
        time.sleep(0.01)

    assert runs == ["start", "done"]
    assert job_store._start_job_thread(job_id, _target) is True
    release.set()
    deadline = time.time() + 2
    while job_store._job_thread_is_alive(job_id) and time.time() < deadline:
        time.sleep(0.01)


def test_dead_worker_bookkeeping_allows_restart():
    job_id = "dead-worker-restart"

    def _boom(_jid: str) -> None:
        raise RuntimeError("intentional")

    assert job_store._start_job_thread(job_id, _boom) is True
    deadline = time.time() + 2
    while job_store._job_thread_is_alive(job_id) and time.time() < deadline:
        time.sleep(0.01)

    assert job_store._job_thread_is_alive(job_id) is False
    assert job_store._job_thread_is_stale(job_id) is True
    assert job_store._start_job_thread(job_id, lambda _j: None) is True
    deadline = time.time() + 2
    while job_store._job_thread_is_alive(job_id) and time.time() < deadline:
        time.sleep(0.01)
