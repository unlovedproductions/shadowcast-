"""Meta (Instagram Reels + Facebook Page) publisher."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import httpx

from credentials_store import CredentialsStore
from oauth_manager import OAuthManager

GRAPH = "https://graph.facebook.com/v19.0"


class MetaPublisher:
    def __init__(self, store: CredentialsStore | None = None):
        self.store = store or CredentialsStore()
        self.oauth = OAuthManager(self.store)

    def publish_instagram(
        self,
        video_path: str,
        payload: dict[str, Any],
        *,
        cover_path: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if dry_run:
            return {
                "status": "success",
                "platform": "instagram",
                "post_id": "dry_run_instagram",
                "url": "https://instagram.com/reel/dry_run",
                "dry_run": True,
            }

        creds = self.oauth.get_credentials("instagram")
        if not creds:
            raise ValueError("Instagram not connected — complete Meta OAuth first")

        ig_id = creds.get("instagram_business_account_id")
        token = creds.get("page_access_token") or creds.get("user_access_token")
        if not ig_id or not token:
            raise ValueError("Instagram business account not linked to connected Meta page")

        public_base = os.getenv("SHADOWCAST_PUBLIC_BASE_URL", os.getenv("OAUTH_REDIRECT_BASE_URL", "http://localhost:8000")).rstrip("/")
        video_url = f"{public_base}/api/media/serve?path={video_path}" if not video_path.startswith("http") else video_path

        params: dict[str, Any] = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": payload.get("caption", ""),
            "access_token": token,
        }
        if cover_path and Path(cover_path).exists():
            params["cover_url"] = f"{public_base}/api/media/serve?path={cover_path}"

        with httpx.Client(timeout=120) as client:
            create = client.post(f"{GRAPH}/{ig_id}/media", data=params)
            create.raise_for_status()
            creation_id = create.json()["id"]

            for _ in range(60):
                status_resp = client.get(
                    f"{GRAPH}/{creation_id}",
                    params={"fields": "status_code", "access_token": token},
                )
                status_resp.raise_for_status()
                code = status_resp.json().get("status_code")
                if code == "FINISHED":
                    break
                if code == "ERROR":
                    raise RuntimeError("Instagram media processing failed")
                time.sleep(5)

            publish = client.post(
                f"{GRAPH}/{ig_id}/media_publish",
                data={"creation_id": creation_id, "access_token": token},
            )
            publish.raise_for_status()
            post_id = publish.json()["id"]

        return {
            "status": "success",
            "platform": "instagram",
            "post_id": post_id,
            "url": f"https://www.instagram.com/reel/{post_id}",
        }

    def publish_facebook(
        self,
        video_path: str,
        payload: dict[str, Any],
        *,
        page_id: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if dry_run:
            return {
                "status": "success",
                "platform": "facebook",
                "post_id": "dry_run_facebook",
                "url": "https://facebook.com/video/dry_run",
                "dry_run": True,
            }

        creds = self.oauth.get_credentials("facebook")
        if not creds:
            raise ValueError("Facebook not connected — complete Meta OAuth first")

        target_page = page_id or creds.get("page_id")
        token = creds.get("page_access_token") or creds.get("user_access_token")
        app_id = os.getenv("META_APP_ID", "")
        if not target_page or not token:
            raise ValueError("Facebook page not configured")

        file_size = Path(video_path).stat().st_size
        file_name = Path(video_path).name

        with httpx.Client(timeout=300) as client:
            session = client.post(
                f"{GRAPH}/{app_id}/uploads",
                params={
                    "file_name": file_name,
                    "file_length": file_size,
                    "file_type": "video/mp4",
                    "access_token": token,
                },
            )
            session.raise_for_status()
            upload_session_id = session.json()["id"]

            with open(video_path, "rb") as f:
                upload = client.post(
                    f"{GRAPH}/{upload_session_id}",
                    headers={"Authorization": f"OAuth {token}", "file_offset": "0"},
                    content=f.read(),
                )
            upload.raise_for_status()
            file_handle = upload.json().get("h")

            publish = client.post(
                f"{GRAPH}/{target_page}/videos",
                data={
                    "access_token": token,
                    "title": payload.get("title", "Video"),
                    "description": payload.get("description", ""),
                    "fbuploader_video_file_chunk": file_handle,
                },
            )
            publish.raise_for_status()
            post_id = publish.json().get("id")

        return {
            "status": "success",
            "platform": "facebook",
            "post_id": post_id,
            "url": f"https://www.facebook.com/{target_page}/videos/{post_id}",
        }
