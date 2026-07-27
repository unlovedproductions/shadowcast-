"""HTTP integration tests for ShadowCast FastAPI routes."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app import app, jobs  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("INTERNAL_SERVICE_SECRET", raising=False)
    return TestClient(app)


@pytest.fixture
def admin_client(monkeypatch):
    monkeypatch.setenv("INTERNAL_SERVICE_SECRET", "test-secret")
    client = TestClient(app)
    client.headers.update({"X-Service-Key": "test-secret"})
    return client


@pytest.fixture(autouse=True)
def clear_jobs():
    jobs.clear()
    yield
    jobs.clear()


class TestOpsRoutes:
    def test_health_returns_shape(self, client):
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["app"] == "ShadowCast"
        assert "version" in data

    def test_openapi_json_available(self, client):
        res = client.get("/api/openapi.json")
        assert res.status_code == 200
        spec = res.json()
        assert spec["openapi"].startswith("3.")
        assert "/api/health" in spec["paths"]

    def test_readiness_returns_checks(self, client):
        res = client.get("/api/readiness")
        assert res.status_code == 200
        data = res.json()
        assert "ready" in data
        assert "blockers" in data
        assert "checks" in data
        assert "ffmpeg" in data["checks"]


class TestConfigRoutes:
    def test_providers_returns_current(self, client):
        res = client.get("/api/providers")
        assert res.status_code == 200
        data = res.json()
        assert "providers" in data
        assert "current" in data
        assert "provider" in data["current"]

    def test_config_post_validates_provider(self, admin_client):
        res = admin_client.post("/api/config", json={"provider": ""})
        assert res.status_code == 422
        body = res.json()
        assert "detail" in body
        assert "error" in body
        assert body["error"]["code"] == "VALIDATION_ERROR"

    @patch("app.test_chat_completion", return_value=(True, "ok", "pong"))
    def test_llm_test_shape(self, _mock_test, client):
        res = client.get("/api/llm/test")
        assert res.status_code == 200
        data = res.json()
        assert "ok" in data
        assert "provider" in data


class TestCatalogRoutes:
    def test_hooks_lists_types(self, client):
        res = client.get("/api/hooks")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data["hooks"], list)
        assert isinstance(data["descriptions"], dict)

    def test_content_styles_default(self, client):
        res = client.get("/api/content-styles")
        assert res.status_code == 200
        data = res.json()
        assert "styles" in data
        assert "default" in data

    def test_tts_providers(self, client):
        res = client.get("/api/tts-providers")
        assert res.status_code == 200
        data = res.json()
        assert "providers" in data
        assert "best" in data


class TestInputRoutes:
    @patch("app.scrape_amazon_product", return_value={"error": "bad url"})
    def test_scrape_amazon_bad_result_400(self, _mock_scrape, client):
        res = client.post("/api/scrape-amazon", data={"url": "https://amazon.com/dp/B000"})
        assert res.status_code == 400
        assert "detail" in res.json()

    @patch("app.scrape_amazon_product", return_value={"product_name": "", "price": "$10"})
    def test_scrape_amazon_empty_product_name_422(self, _mock_scrape, client):
        res = client.post("/api/scrape-amazon", data={"url": "https://amazon.com/dp/B000"})
        assert res.status_code == 422
        assert "product name" in res.json()["detail"].lower()

    @patch("app.research_youtube_keywords", return_value={"recommended_tags": ["tag1"]})
    def test_youtube_research(self, _mock_research, client):
        res = client.post("/api/youtube-research", data={"query": "blender review"})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert "data" in data


class TestJobRoutes:
    def test_generate_missing_product_name_422(self, client):
        res = client.post(
            "/api/generate",
            json={
                "product_info": {"product_name": ""},
                "hook_types": ["curiosity"],
                "formats": ["short_form"],
            },
        )
        assert res.status_code == 422

    @patch("app._start_job_thread", return_value=True)
    @patch("app._ensure_generation_ready")
    def test_generate_starts_job(self, _ready, _thread, client):
        res = client.post(
            "/api/generate",
            json={
                "product_info": {
                    "product_name": "Test Product",
                    "niche": "Kitchen",
                    "key_features": ["fast"],
                },
                "hook_types": ["curiosity"],
                "formats": ["short_form"],
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "running"
        assert data["mode"] == "single"
        assert "job_id" in data

    def test_status_not_found(self, client):
        res = client.get("/api/status/doesnotexist")
        assert res.status_code == 404
        body = res.json()
        assert body["detail"]
        assert body["error"]["code"] == "NOT_FOUND"

    @patch("app._load_job")
    def test_status_known_job(self, mock_load, client):
        mock_load.return_value = {
            "id": "abc12345",
            "mode": "single",
            "status": "complete",
            "progress": 100,
            "current_step": "Done",
            "errors": [],
            "warnings": [],
            "hook_types": ["curiosity"],
            "formats": ["short_form"],
            "results": {},
        }
        res = client.get("/api/status/abc12345")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == "abc12345"
        assert "summary" in data

    @patch("app._load_job", return_value=None)
    def test_audit_not_found(self, _mock_load, client):
        res = client.get("/api/audit/missing")
        assert res.status_code == 404


class TestOAuthRoutes:
    def test_oauth_callback_rejects_unknown_state(self, client):
        res = client.get("/api/oauth/youtube/callback?code=fake-code&state=unknown-state", follow_redirects=False)
        assert res.status_code == 302
        assert "oauth_error" in res.headers["location"]
        assert "state" in res.headers["location"].lower()


class TestAuthAllowlist:
    def test_config_requires_service_key_when_secret_set(self, monkeypatch):
        monkeypatch.setenv("INTERNAL_SERVICE_SECRET", "test-secret")
        bare = TestClient(app)
        res = bare.post("/api/config", json={"provider": "ollama"})
        assert res.status_code == 401

    def test_publish_batch_not_blocked_by_service_key(self, monkeypatch):
        monkeypatch.setenv("INTERNAL_SERVICE_SECRET", "test-secret")
        bare = TestClient(app)
        res = bare.post("/api/publish/batch", json={})
        assert res.status_code != 401

    def test_openapi_marks_publish_public(self, client):
        from auth_public_routes import is_public_path

        assert is_public_path("/api/publish")
        assert is_public_path("/api/analytics/dashboard")
        assert not is_public_path("/api/config")
        spec = client.get("/api/openapi.json").json()
        publish_sec = spec["paths"]["/api/publish/batch"]["post"].get("security")
        assert publish_sec == []
        config_sec = spec["paths"]["/api/config"]["post"].get("security")
        assert config_sec and any("ServiceKeyAuth" in (item or {}) for item in config_sec)