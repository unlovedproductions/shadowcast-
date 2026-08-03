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

    def test_lifespan_runs_cleanup_and_resume(self, monkeypatch):
        called = {"cleanup": 0, "resume": 0}

        monkeypatch.setattr("app.cleanup_old_job_outputs", lambda: called.__setitem__("cleanup", called["cleanup"] + 1))
        monkeypatch.setattr("app._resume_incomplete_jobs", lambda: called.__setitem__("resume", called["resume"] + 1))
        monkeypatch.delenv("INTERNAL_SERVICE_SECRET", raising=False)

        with TestClient(app) as lifespan_client:
            res = lifespan_client.get("/api/health")
            assert res.status_code == 200

        assert called["cleanup"] == 1
        assert called["resume"] == 1

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

    def test_oauth_status_shape(self, client):
        res = client.get("/api/oauth/status")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, dict)
        for platform in ("youtube", "instagram", "facebook", "tiktok", "rumble"):
            assert platform in data
            assert "connected" in data[platform]

    def test_oauth_config_shape(self, client):
        res = client.get("/api/oauth/config")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, dict)
        for key in ("youtube", "meta", "tiktok"):
            assert key in data
            assert isinstance(data[key], bool)

    def test_oauth_authorize_youtube_without_client_id_400(self, client, monkeypatch):
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
        res = client.get("/api/oauth/youtube/authorize")
        assert res.status_code == 400
        assert "GOOGLE_CLIENT_ID" in res.json()["detail"]

    def test_oauth_authorize_unsupported_platform_400(self, client):
        res = client.get("/api/oauth/myspace/authorize")
        assert res.status_code == 400
        assert "Unsupported" in res.json()["detail"]

    def test_oauth_authorize_rumble_returns_login_url(self, client):
        res = client.get("/api/oauth/rumble/authorize")
        assert res.status_code == 200
        data = res.json()
        assert "authorize_url" in data
        assert "rumble/login" in data["authorize_url"]
        assert data.get("state")

    def test_oauth_authorize_youtube_with_client_id(self, client, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
        res = client.get("/api/oauth/youtube/authorize")
        assert res.status_code == 200
        data = res.json()
        assert data["authorize_url"].startswith("https://accounts.google.com/")
        assert "client_id=test-client-id" in data["authorize_url"]
        assert data.get("state")

    def test_oauth_disconnect_shape(self, client):
        res = client.delete("/api/oauth/youtube")
        assert res.status_code == 200
        assert res.json() == {"platform": "youtube", "status": "disconnected"}

    def test_oauth_callback_missing_code_redirects(self, client):
        res = client.get("/api/oauth/youtube/callback?state=abc", follow_redirects=False)
        assert res.status_code == 302
        assert "oauth_error" in res.headers["location"]
        assert "code" in res.headers["location"].lower()

    def test_oauth_rumble_login_failure_500(self, client, monkeypatch):
        def _boom(_user, _password):
            raise RuntimeError("login failed")

        monkeypatch.setattr("app.rumble_publisher.login_and_capture_session", _boom)
        res = client.post("/api/oauth/rumble/login", json={"username": "u", "password": "p"})
        assert res.status_code == 500
        assert "login failed" in res.json()["detail"]

    def test_oauth_youtube_authorize_callback_happy_path(self, client, monkeypatch, tmp_path):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
        monkeypatch.setenv("SHADOWCAST_ALLOW_DEV_CREDENTIALS", "1")
        monkeypatch.setenv("CREDENTIALS_STORE_DIR", str(tmp_path / "creds"))

        import app as app_module
        from credentials_store import CredentialsStore

        app_module.oauth_manager.store = CredentialsStore(store_dir=tmp_path / "creds")

        def _fake_exchange(code: str):
            assert code == "auth-code-ok"
            app_module.oauth_manager.store.save(
                "youtube",
                {"access_token": "tok", "refresh_token": "ref", "channel_id": "UC_test"},
            )
            return {"platform": "youtube", "status": "connected"}

        monkeypatch.setattr(app_module.oauth_manager, "_exchange_google", _fake_exchange)

        auth = client.get("/api/oauth/youtube/authorize")
        assert auth.status_code == 200
        state = auth.json()["state"]

        cb = client.get(
            f"/api/oauth/youtube/callback?code=auth-code-ok&state={state}",
            follow_redirects=False,
        )
        assert cb.status_code == 302
        assert "connected=youtube" in cb.headers["location"]

        status = client.get("/api/oauth/status").json()
        assert status["youtube"]["connected"] is True
        assert "access_token" not in status["youtube"].get("details", {})


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
        assert is_public_path("/api/cancel/abc")
        assert not is_public_path("/api/config")
        spec = client.get("/api/openapi.json").json()
        publish_sec = spec["paths"]["/api/publish/batch"]["post"].get("security")
        assert publish_sec == []
        config_sec = spec["paths"]["/api/config"]["post"].get("security")
        assert config_sec and any("ServiceKeyAuth" in (item or {}) for item in config_sec)

class TestPublishSocialAnalyticsApf:
    @patch("app.publish_service.publish_batch")
    def test_publish_batch_dry_run(self, mock_batch, client):
        mock_batch.return_value = [
            {"status": "success", "dry_run": True, "post_id": "dry_run_youtube"}
        ]
        res = client.post(
            "/api/publish/batch",
            json={
                "job_id": "jobtest1",
                "hook_type": "curiosity",
                "video_format": "short_form",
                "platforms": ["youtube"],
                "dry_run": True,
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert "results" in body
        assert body["results"][0]["dry_run"] is True
        mock_batch.assert_called_once()
        assert mock_batch.call_args.kwargs.get("dry_run") is True

    def test_social_schedule_with_video_path(self, client):
        res = client.post(
            "/api/social/schedule",
            json={
                "platform": "instagram",
                "video_path": "/tmp/fake.mp4",
                "caption": "test caption",
                "hashtags": ["shadowcast"],
                "scheduled_time": "2099-01-01T12:00:00",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "scheduled"
        assert data.get("platform") == "instagram"

        queue = client.get("/api/social/queue")
        assert queue.status_code == 200
        assert isinstance(queue.json().get("queue"), list)

    def test_analytics_track_and_dashboard(self, client):
        track = client.post(
            "/api/analytics/track",
            data={
                "product_name": "Test Gadget",
                "hook_type": "curiosity",
                "format_type": "short_form",
                "video_path": "/tmp/test.mp4",
            },
        )
        assert track.status_code == 200
        video_id = track.json()["video_id"]
        assert video_id

        record = client.post(
            "/api/analytics/record",
            json={"video_id": video_id, "metric_type": "views", "value": 42},
        )
        assert record.status_code == 200

        dash = client.get("/api/analytics/dashboard")
        assert dash.status_code == 200
        assert isinstance(dash.json(), dict)

    def test_apf_direct_import_round_trip(self, client, tmp_path):
        import app as app_mod

        app_mod._UNLOVED_APF_IMPORT_DIR = tmp_path
        tmp_path.mkdir(parents=True, exist_ok=True)

        payload = {
            "product": {
                "name": "Audit Fix Widget",
                "category": "Tech",
                "affiliate_url": "https://example.com/aff",
                "price": "$29.99",
            }
        }
        post = client.post("/api/import-apf/direct", json=payload)
        assert post.status_code == 200
        body = post.json()
        assert body.get("ok") is True
        token = body["token"]
        assert body.get("productName") or body.get("normalized", {}).get("productName")

        get = client.get(f"/api/import-apf/direct/{token}")
        assert get.status_code == 200
        fetched = get.json()
        assert fetched.get("token") == token
        assert fetched.get("normalized", {}).get("productName")

    def test_retry_missing_not_found(self, client):
        res = client.post("/api/retry-missing/does-not-exist")
        assert res.status_code == 404

    @patch("app._summarize_job_output")
    @patch("app._start_job_thread", return_value=True)
    @patch("app._save_job")
    def test_retry_missing_starts_when_partial(self, _save, _start, mock_summary, client):
        mock_summary.return_value = {
            "is_partial": True,
            "videos_ready": 0,
            "scripts_ready": 0,
            "packages_ready": 0,
            "videos_expected": 1,
            "packages_expected": 1,
            "warning_count": 0,
        }
        jobs["retry1"] = {
            "id": "retry1",
            "mode": "single",
            "status": "partial",
            "hook_types": ["curiosity"],
            "formats": ["short_form"],
            "progress": 50,
            "errors": [],
        }
        res = client.post("/api/retry-missing/retry1")
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "running"
        assert body["job_id"] == "retry1"
        _start.assert_called_once()

    def test_cancel_job_not_found(self, client):
        res = client.post("/api/cancel/missing-job")
        assert res.status_code == 404

    @patch("app._save_job")
    def test_cancel_running_job(self, _save, client):
        jobs["cxl1"] = {
            "id": "cxl1",
            "status": "running",
            "current_step": "Rendering...",
            "progress": 40,
            "errors": [],
        }
        res = client.post("/api/cancel/cxl1")
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "cancelling"
        assert jobs["cxl1"]["cancel_requested"] is True


    def test_analytics_dashboard_shape_after_track(self, client):
        track = client.post(
            "/api/analytics/track",
            data={
                "product_name": "Shape Widget",
                "hook_type": "curiosity",
                "format_type": "short_form",
                "video_path": "/tmp/shape.mp4",
            },
        )
        assert track.status_code == 200
        video_id = track.json()["video_id"]
        client.post(
            "/api/analytics/record",
            json={"video_id": video_id, "metric_type": "views", "value": 100},
        )
        client.post(
            "/api/analytics/record",
            json={"video_id": video_id, "metric_type": "affiliate_clicks", "value": 5},
        )
        client.post(
            "/api/analytics/record",
            json={"video_id": video_id, "metric_type": "revenue", "value": 12.5},
        )
        dash = client.get("/api/analytics/dashboard").json()
        assert isinstance(dash.get("hook_performance"), list)
        assert isinstance(dash.get("format_performance"), list)
        assert "summary" in dash
        assert "avg_conversion_rate" in dash["summary"]
        assert "revenue_report" in dash
        if dash["hook_performance"]:
            row = dash["hook_performance"][0]
            assert "hook" in row and "avg_views" in row

    @patch("app.publish_service.publish")
    def test_social_post_dry_run_via_job(self, mock_publish, client):
        mock_publish.return_value = {"status": "success", "dry_run": True, "post_id": "dry"}
        res = client.post(
            "/api/social/post",
            json={
                "platform": "youtube",
                "job_id": "job1",
                "hook_type": "curiosity",
                "video_format": "short_form",
                "dry_run": True,
                "caption": "",
                "hashtags": [],
            },
        )
        assert res.status_code == 200
        assert res.json().get("dry_run") is True
        mock_publish.assert_called_once()
        assert mock_publish.call_args.kwargs.get("dry_run") is True

    @patch("app._start_job_thread", return_value=True)
    @patch("app._ensure_generation_ready")
    def test_batch_generate_starts_job(self, _ready, _thread, client):
        res = client.post(
            "/api/batch-generate",
            json={
                "products": [
                    {
                        "product_name": "Batch A",
                        "niche": "Tech",
                        "key_features": ["fast"],
                    },
                    {
                        "product_name": "Batch B",
                        "niche": "Tech",
                        "key_features": ["cheap"],
                    },
                ],
                "hook_types": ["curiosity"],
                "formats": ["short_form"],
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "running"
        assert data["mode"] == "batch"
        assert data.get("product_count") == 2 or "job_id" in data
        _thread.assert_called_once()

    def test_bg_recommend_returns_known_style(self, client):
        res = client.get(
            "/api/bg-recommend",
            params={"content_style": "honest_review", "hook_type": "curiosity"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["recommended_style"] in data["all_styles"]
        assert "gradient" in data["all_styles"]

    def test_tracking_link_embeds_video_id(self, client):
        res = client.get(
            "/api/tracking-link",
            params={
                "affiliate_url": "https://amzn.to/example",
                "video_id": "job-abc",
                "platform": "youtube",
            },
        )
        assert res.status_code == 200
        url = res.json()["tracking_url"]
        assert "job-abc" in url
        assert "amzn.to/example" in url or "amzn.to" in url

