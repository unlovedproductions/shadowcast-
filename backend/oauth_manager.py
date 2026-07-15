"""OAuth flows for YouTube, Meta, TikTok, and Rumble session connect."""

from __future__ import annotations

import os
import secrets
import urllib.parse
from typing import Any

import httpx

from credentials_store import CredentialsStore

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
META_SCOPES = [
    "instagram_basic",
    "instagram_content_publish",
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_posts",
]
TIKTOK_SCOPES = ["video.publish", "video.upload"]

_pending_states: dict[str, str] = {}


class OAuthManager:
    def __init__(self, store: CredentialsStore | None = None):
        self.store = store or CredentialsStore()
        self.redirect_base = os.getenv("OAUTH_REDIRECT_BASE_URL", "http://localhost:8000").rstrip("/")

    def _redirect_uri(self, platform: str) -> str:
        return f"{self.redirect_base}/api/oauth/{platform}/callback"

    def start_authorize(self, platform: str) -> dict[str, str]:
        state = secrets.token_urlsafe(24)
        _pending_states[state] = platform

        if platform == "youtube":
            client_id = os.getenv("GOOGLE_CLIENT_ID", "")
            if not client_id:
                raise ValueError("GOOGLE_CLIENT_ID not configured")
            params = {
                "client_id": client_id,
                "redirect_uri": self._redirect_uri("youtube"),
                "response_type": "code",
                "scope": " ".join(GOOGLE_SCOPES),
                "access_type": "offline",
                "prompt": "consent",
                "state": state,
            }
            url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
            return {"authorize_url": url, "state": state}

        if platform == "meta":
            app_id = os.getenv("META_APP_ID", "")
            if not app_id:
                raise ValueError("META_APP_ID not configured")
            params = {
                "client_id": app_id,
                "redirect_uri": self._redirect_uri("meta"),
                "scope": ",".join(META_SCOPES),
                "response_type": "code",
                "state": state,
            }
            url = "https://www.facebook.com/v19.0/dialog/oauth?" + urllib.parse.urlencode(params)
            return {"authorize_url": url, "state": state}

        if platform == "tiktok":
            client_key = os.getenv("TIKTOK_CLIENT_KEY", "")
            if not client_key:
                raise ValueError("TIKTOK_CLIENT_KEY not configured")
            params = {
                "client_key": client_key,
                "scope": ",".join(TIKTOK_SCOPES),
                "response_type": "code",
                "redirect_uri": self._redirect_uri("tiktok"),
                "state": state,
            }
            url = "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(params)
            return {"authorize_url": url, "state": state}

        if platform == "rumble":
            return {
                "authorize_url": f"{self.redirect_base}/api/oauth/rumble/login",
                "state": state,
                "message": "Rumble uses browser login — open this URL to connect.",
            }

        raise ValueError(f"Unsupported OAuth platform: {platform}")

    def handle_callback(self, platform: str, code: str, state: str) -> dict[str, Any]:
        expected = _pending_states.pop(state, None)
        if expected and expected != platform:
            raise ValueError("OAuth state mismatch")

        if platform == "youtube":
            return self._exchange_google(code)
        if platform == "meta":
            return self._exchange_meta(code)
        if platform == "tiktok":
            return self._exchange_tiktok(code)
        raise ValueError(f"No OAuth callback for platform: {platform}")

    def _exchange_google(self, code: str) -> dict[str, Any]:
        client_id = os.getenv("GOOGLE_CLIENT_ID", "")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
        resp = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": self._redirect_uri("youtube"),
                "grant_type": "authorization_code",
            },
            timeout=30,
        )
        resp.raise_for_status()
        token_data = resp.json()
        creds = {
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "expires_in": token_data.get("expires_in"),
            "token_type": token_data.get("token_type", "Bearer"),
        }
        self.store.save("youtube", creds)
        return {"platform": "youtube", "status": "connected"}

    def _exchange_meta(self, code: str) -> dict[str, Any]:
        app_id = os.getenv("META_APP_ID", "")
        app_secret = os.getenv("META_APP_SECRET", "")
        token_resp = httpx.get(
            "https://graph.facebook.com/v19.0/oauth/access_token",
            params={
                "client_id": app_id,
                "client_secret": app_secret,
                "redirect_uri": self._redirect_uri("meta"),
                "code": code,
            },
            timeout=30,
        )
        token_resp.raise_for_status()
        short = token_resp.json()
        long_resp = httpx.get(
            "https://graph.facebook.com/v19.0/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": app_id,
                "client_secret": app_secret,
                "fb_exchange_token": short["access_token"],
            },
            timeout=30,
        )
        long_resp.raise_for_status()
        token_data = long_resp.json()

        pages_resp = httpx.get(
            "https://graph.facebook.com/v19.0/me/accounts",
            params={"access_token": token_data["access_token"]},
            timeout=30,
        )
        pages_resp.raise_for_status()
        pages = pages_resp.json().get("data", [])

        ig_account_id = None
        page_id = None
        page_token = None
        if pages:
            page = pages[0]
            page_id = page.get("id")
            page_token = page.get("access_token")
            ig_resp = httpx.get(
                f"https://graph.facebook.com/v19.0/{page_id}",
                params={"fields": "instagram_business_account", "access_token": page_token},
                timeout=30,
            )
            if ig_resp.status_code == 200:
                ig_account_id = ig_resp.json().get("instagram_business_account", {}).get("id")

        creds = {
            "user_access_token": token_data.get("access_token"),
            "page_id": page_id,
            "page_access_token": page_token,
            "instagram_business_account_id": ig_account_id,
            "pages": pages,
        }
        self.store.save("meta", creds)
        self.store.save("instagram", creds)
        self.store.save("facebook", creds)
        return {"platform": "meta", "status": "connected", "page_id": page_id, "instagram_account_id": ig_account_id}

    def _exchange_tiktok(self, code: str) -> dict[str, Any]:
        client_key = os.getenv("TIKTOK_CLIENT_KEY", "")
        client_secret = os.getenv("TIKTOK_CLIENT_SECRET", "")
        resp = httpx.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key": client_key,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": self._redirect_uri("tiktok"),
            },
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
        token_data = body.get("data", body)
        creds = {
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "expires_in": token_data.get("expires_in"),
            "open_id": token_data.get("open_id"),
        }
        self.store.save("tiktok", creds)
        return {"platform": "tiktok", "status": "connected"}

    def save_rumble_session(self, cookies: list[dict[str, Any]]) -> dict[str, Any]:
        self.store.save("rumble", {"cookies": cookies, "status": "connected"})
        return {"platform": "rumble", "status": "connected"}

    def disconnect(self, platform: str) -> dict[str, str]:
        if platform == "meta":
            self.store.delete("meta")
            self.store.delete("instagram")
            self.store.delete("facebook")
        else:
            self.store.delete(platform)
        return {"platform": platform, "status": "disconnected"}

    def config_status(self) -> dict[str, bool]:
        return {
            "youtube": bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET")),
            "meta": bool(os.getenv("META_APP_ID") and os.getenv("META_APP_SECRET")),
            "tiktok": bool(os.getenv("TIKTOK_CLIENT_KEY") and os.getenv("TIKTOK_CLIENT_SECRET")),
        }

    def status(self) -> dict[str, Any]:
        platforms = ("youtube", "instagram", "facebook", "tiktok", "rumble", "meta")
        result: dict[str, Any] = {}
        for p in platforms:
            data = self.store.load(p)
            if p == "meta":
                continue
            result[p] = {
                "connected": bool(data),
                "details": {k: v for k, v in (data or {}).items() if k not in ("access_token", "refresh_token", "user_access_token", "page_access_token", "cookies")},
            }
        return result

    def get_credentials(self, platform: str) -> dict[str, Any] | None:
        if platform in ("instagram", "facebook"):
            return self.store.load(platform) or self.store.load("meta")
        return self.store.load(platform)
