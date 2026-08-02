"""Job output retention / GC under backend/output/."""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app import (  # noqa: E402
    _output_max_age_days,
    cleanup_old_job_outputs,
    jobs,
)


def _write_job(dir_path: Path, status: str = "complete", mtime: float | None = None) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    job_json = dir_path / "job.json"
    job_json.write_text(json.dumps({"status": status, "job_id": dir_path.name}), encoding="utf-8")
    if mtime is not None:
        os.utime(job_json, (mtime, mtime))
        os.utime(dir_path, (mtime, mtime))


def test_output_max_age_days_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SHADOWCAST_OUTPUT_MAX_AGE_DAYS", raising=False)
    assert _output_max_age_days() is None


def test_output_max_age_days_parses_and_rejects_non_positive(monkeypatch):
    monkeypatch.setenv("SHADOWCAST_OUTPUT_MAX_AGE_DAYS", "14")
    assert _output_max_age_days() == 14.0
    monkeypatch.setenv("SHADOWCAST_OUTPUT_MAX_AGE_DAYS", "0")
    assert _output_max_age_days() is None
    monkeypatch.setenv("SHADOWCAST_OUTPUT_MAX_AGE_DAYS", "nope")
    assert _output_max_age_days() is None


def test_cleanup_removes_only_aged_complete_jobs(tmp_path, monkeypatch):
    monkeypatch.delenv("SHADOWCAST_OUTPUT_MAX_AGE_DAYS", raising=False)
    now = time.time()
    old = now - (20 * 86400)
    recent = now - (2 * 86400)

    _write_job(tmp_path / "old_job", "complete", mtime=old)
    _write_job(tmp_path / "fresh_job", "complete", mtime=recent)
    _write_job(tmp_path / "running_old", "running", mtime=old)

    cred = tmp_path / "credentials"
    cred.mkdir()
    (cred / "keep.txt").write_text("secret", encoding="utf-8")
    analytics = tmp_path / "analytics.json"
    analytics.write_text("{}", encoding="utf-8")
    orphan = tmp_path / "no_job_json"
    orphan.mkdir()
    (orphan / "blob.bin").write_text("x", encoding="utf-8")

    jobs.clear()
    deleted = cleanup_old_job_outputs(
        output_base=tmp_path,
        max_age_days=14,
        now_ts=now,
    )
    assert deleted == 1
    assert not (tmp_path / "old_job").exists()
    assert (tmp_path / "fresh_job").exists()
    assert (tmp_path / "running_old").exists()
    assert (cred / "keep.txt").read_text(encoding="utf-8") == "secret"
    assert analytics.exists()
    assert (orphan / "blob.bin").exists()


def test_cleanup_skips_active_thread_and_noop_when_disabled(tmp_path, monkeypatch):
    monkeypatch.delenv("SHADOWCAST_OUTPUT_MAX_AGE_DAYS", raising=False)
    now = time.time()
    old = now - (30 * 86400)
    _write_job(tmp_path / "active_old", "complete", mtime=old)

    monkeypatch.setattr("app._active_job_threads", {"active_old"})
    assert cleanup_old_job_outputs(output_base=tmp_path, max_age_days=14, now_ts=now) == 0
    assert (tmp_path / "active_old").exists()

    assert cleanup_old_job_outputs(output_base=tmp_path, now_ts=now) == 0
    assert (tmp_path / "active_old").exists()
