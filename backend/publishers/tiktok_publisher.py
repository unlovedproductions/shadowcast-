"""TikTok Content Posting API publisher."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx

from credentials_store import CredentialsStore
from oauth_manager import OAuthManager

TIKTOK_API = "https://open.tiktokapis.com/v2"
TIKTOK_PUBLISH_POLL_SECONDS = 5
TIKTOK_PUBLISH_MAX_POLLS = 60


class TikTokPublisher:
    def __init__(self, store: CredentialsStore | None = None):
        self.store = store or CredentialsStore()
        self.oauth = OAuthManager(self.store)

    def publish(
        self,
        video_path: str,
        payload: dict[str, Any],
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if dry_run:
            return {
                "status": "success",
                "platform": "tiktok",
                "post_id": "dry_run_tiktok",
                "url": "https://www.tiktok.com/@user/video/dry_run",
                "dry_run": True,
            }

        creds = self.oauth.get_credentials("tiktok")
        if not creds or not creds.get("access_token"):
            raise ValueError("TikTok not connected — complete OAuth first")

        token = creds["access_token"]
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}

        title = payload.get("title", "Video")
        description = payload.get("description", "")
        hashtags = payload.get("hashtags", [])

        with httpx.Client(timeout=300) as client:
            init = client.post(
                f"{TIKTOK_API}/post/publish/video/init/",
                headers=headers,
                json={
                    "post_info": {
                        "title": title,
                        "description": description,
                        "privacy_level": "PUBLIC_TO_EVERYONE",
                        "disable_comment": False,
                        "disable_duet": False,
                        "disable_stitch": False,
                    },
                    "source_info": {"source": "FILE_UPLOAD", "video_size": Path(video_path).stat().st_size},
                },
            )
            init.raise_for_status()
            init_data = init.json().get("data", init.json())
            upload_url = init_data.get("upload_url")
            publish_id = init_data.get("publish_id")

            with open(video_path, "rb") as f:
                upload = client.put(upload_url, content=f.read(), headers={"Content-Type": "video/mp4"})
            upload.raise_for_status()

            result = {}
            for _ in range(TIKTOK_PUBLISH_MAX_POLLS):
                publish = client.post(
                    f"{TIKTOK_API}/post/publish/status/fetch/",
                    headers=headers,
                    json={"publish_id": publish_id},
                )
                publish.raise_for_status()
                result = publish.json().get("data", publish.json())
                status = str(result.get("status", "")).upper()
                if status in ("PUBLISH_COMPLETE", "PUBLISHED", "SUCCESS"):
                    break
                if status in ("FAILED", "FAIL"):
                    raise RuntimeError(
                        f"TikTok publish failed: {result.get('fail_reason', result)}"
                    )
                time.sleep(TIKTOK_PUBLISH_POLL_SECONDS)
            else:
                raise TimeoutError("TikTok publish did not complete within polling window")

        post_id = result.get("publish_id") or publish_id
        return {
            "status": "success",
            "platform": "tiktok",
            "post_id": post_id,
            "url": result.get("share_url", f"https://www.tiktok.com/video/{post_id}"),
            "hashtags": hashtags,
        }
