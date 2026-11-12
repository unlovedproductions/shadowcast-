"""Env-gated bounded parallel product renders for batch jobs."""

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import app as app_mod  # noqa: E402
from app import (  # noqa: E402
    _batch_workers,
    _run_batch_generation,
    jobs,
)


def test_batch_workers_default_and_parse(monkeypatch):
    monkeypatch.delenv("SHADOWCAST_BATCH_WORKERS", raising=False)
    assert _batch_workers() == 1
    monkeypatch.setenv("SHADOWCAST_BATCH_WORKERS", "3")
    assert _batch_workers() == 3
    monkeypatch.setenv("SHADOWCAST_BATCH_WORKERS", "0")
    assert _batch_workers() == 1
    monkeypatch.setenv("SHADOWCAST_BATCH_WORKERS", "nope")
    assert _batch_workers() == 1


def _seed_batch_job(job_id: str, names: list[str]) -> dict:
    job = {
        "job_id": job_id,
        "status": "running",
        "mode": "batch",
        "products": [{"product_name": n, "content_style": "honest_review"} for n in names],
        "hook_types": ["problem_agitate_solve"],
        "formats": ["short_form"],
        "content_style": "honest_review",
        "errors": [],
        "warnings": [],
        "progress": 0,
        "current_step": "starting",
    }
    jobs[job_id] = job
    return job


def test_batch_workers_one_preserves_product_order(tmp_path, monkeypatch):
    monkeypatch.setenv("SHADOWCAST_BATCH_WORKERS", "1")
    monkeypatch.setattr(app_mod, "OUTPUT_BASE", tmp_path)
    monkeypatch.setattr(app_mod, "_finalize_job_status", lambda *a, **k: None)

    job_id = "batch-seq"
    names = ["Alpha", "Beta", "Gamma"]
    job = _seed_batch_job(job_id, names)
    (tmp_path / job_id).mkdir(parents=True)
    call_order: list[str] = []

    def _fake_single_ordered(
        jid, product, product_dir, hook_types, formats, content_style, step_offset, total_steps, **kwargs
    ):
        call_order.append(product["product_name"])
        product_dir.mkdir(exist_ok=True)
        return {"product_name": product["product_name"], "hooks": {}}, step_offset + 1

    monkeypatch.setattr(app_mod, "_run_single_product", _fake_single_ordered)
    _run_batch_generation(job_id)

    assert call_order == names
    assert [r["product_name"] for r in job["product_results"]] == names
    assert (tmp_path / job_id / "all_products.zip").exists()


def test_batch_workers_parallel_completes_all(tmp_path, monkeypatch):
    monkeypatch.setenv("SHADOWCAST_BATCH_WORKERS", "3")
    monkeypatch.setattr(app_mod, "OUTPUT_BASE", tmp_path)
    monkeypatch.setattr(app_mod, "_finalize_job_status", lambda *a, **k: None)

    job_id = "batch-par"
    names = ["Alpha", "Beta", "Gamma"]
    job = _seed_batch_job(job_id, names)
    (tmp_path / job_id).mkdir(parents=True)
    active = {"n": 0, "peak": 0}
    lock = threading.Lock()
    seen: list[str] = []

    def _fake_single(jid, product, product_dir, hook_types, formats, content_style, step_offset, total_steps, **kwargs):
        with lock:
            active["n"] += 1
            active["peak"] = max(active["peak"], active["n"])
            seen.append(product["product_name"])
        time.sleep(0.05)
        product_dir.mkdir(exist_ok=True)
        with lock:
            active["n"] -= 1
        return {"product_name": product["product_name"], "hooks": {}, "step_offset": step_offset}, step_offset

    monkeypatch.setattr(app_mod, "_run_single_product", _fake_single)
    _run_batch_generation(job_id)

    result_names = [r["product_name"] for r in job["product_results"]]
    assert sorted(result_names) == sorted(names)
    assert set(seen) == set(names)
    assert active["peak"] > 1
    assert (tmp_path / job_id / "all_products.zip").exists()


def test_batch_workers_parallel_records_product_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("SHADOWCAST_BATCH_WORKERS", "2")
    monkeypatch.setattr(app_mod, "OUTPUT_BASE", tmp_path)
    monkeypatch.setattr(app_mod, "_finalize_job_status", lambda *a, **k: None)

    job_id = "batch-fail"
    names = ["OkProd", "BadProd"]
    job = _seed_batch_job(job_id, names)
    (tmp_path / job_id).mkdir(parents=True)

    def _fake_single(jid, product, product_dir, hook_types, formats, content_style, step_offset, total_steps, **kwargs):
        product_dir.mkdir(exist_ok=True)
        if product["product_name"] == "BadProd":
            raise RuntimeError("boom")
        return {"product_name": product["product_name"], "hooks": {}}, step_offset

    monkeypatch.setattr(app_mod, "_run_single_product", _fake_single)
    _run_batch_generation(job_id)

    assert [r["product_name"] for r in job["product_results"]] == ["OkProd"]
    assert any("BadProd" in e and "boom" in e for e in job["errors"])
