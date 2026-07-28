"""P0 localhost-trust: bind defaults, download containment, credentials fail-closed."""

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app import OUTPUT_BASE, _safe_job_file, app  # noqa: E402
from credentials_store import (  # noqa: E402
    DEFAULT_STORE_DIR,
    CredentialsStore,
    _resolve_encryption_secret,
)
from fastapi import HTTPException  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("INTERNAL_SERVICE_SECRET", raising=False)
    return TestClient(app)


def test_credentials_default_dir_outside_output():
    assert DEFAULT_STORE_DIR.resolve() == (
        Path(__file__).resolve().parents[1] / "backend" / "credentials"
    ).resolve()
    assert not DEFAULT_STORE_DIR.resolve().is_relative_to(OUTPUT_BASE.resolve())


def test_encryption_secret_fails_closed(monkeypatch):
    monkeypatch.delenv("CREDENTIALS_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("INTERNAL_SERVICE_SECRET", raising=False)
    monkeypatch.delenv("SHADOWCAST_ALLOW_DEV_CREDENTIALS", raising=False)
    with pytest.raises(RuntimeError, match="CREDENTIALS_ENCRYPTION_KEY"):
        _resolve_encryption_secret(None)


def test_encryption_secret_dev_escape(monkeypatch):
    monkeypatch.delenv("CREDENTIALS_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("INTERNAL_SERVICE_SECRET", raising=False)
    monkeypatch.setenv("SHADOWCAST_ALLOW_DEV_CREDENTIALS", "1")
    assert _resolve_encryption_secret(None) == "shadowcast-dev-key"


def test_safe_job_file_blocks_credentials_and_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr("app.OUTPUT_BASE", tmp_path)
    (tmp_path / "credentials").mkdir()
    (tmp_path / "credentials" / "youtube.json").write_text("secret", encoding="utf-8")
    job = tmp_path / "abc123"
    job.mkdir()
    (job / "ok.txt").write_text("ok", encoding="utf-8")

    with pytest.raises(HTTPException) as blocked:
        _safe_job_file("credentials", "youtube.json")
    assert blocked.value.status_code == 404

    with pytest.raises(HTTPException):
        _safe_job_file("abc123", "../credentials/youtube.json")

    assert _safe_job_file("abc123", "ok.txt").read_text(encoding="utf-8") == "ok"


def test_download_rejects_credentials_job(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.OUTPUT_BASE", tmp_path)
    cred = tmp_path / "credentials"
    cred.mkdir()
    (cred / "youtube.json").write_text("nope", encoding="utf-8")
    res = client.get("/api/download/credentials/youtube.json")
    assert res.status_code == 404


def test_download_rejects_traversal(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.OUTPUT_BASE", tmp_path)
    job = tmp_path / "job1"
    job.mkdir()
    (job / "a.txt").write_text("a", encoding="utf-8")
    outside = tmp_path / "credentials"
    outside.mkdir()
    (outside / "youtube.json").write_text("secret", encoding="utf-8")
    res = client.get("/api/download/job1/../credentials/youtube.json")
    assert res.status_code == 404
