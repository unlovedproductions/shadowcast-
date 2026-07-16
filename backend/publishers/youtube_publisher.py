"""YouTube Data API v3 publisher."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from credentials_store import CredentialsStore
from oauth_manager import OAuthManager

UPLOAD_CHUNK_TIMEOUT_SECONDS = 600


class YouTubePublisher:
    def __init__(self, store: CredentialsStore | None = None):
        self.store = store or CredentialsStore()
        self.oauth = OAuthManager(self.store)

    def _get_service(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds_data = self.oauth.get_credentials("youtube")
        if not creds_data or not creds_data.get("access_token"):
            raise ValueError("YouTube not connected — complete OAuth first")
        creds = Credentials(
            token=creds_data.get("access_token"),
            refresh_token=creds_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            self.oauth.persist_google_tokens(creds, "youtube")
        return build("youtube", "v3", credentials=creds)

    def publish(
        self,
        video_path: str,
        payload: dict[str, Any],
        *,
        thumbnail_path: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if dry_run:
            return {
                "status": "success",
                "platform": "youtube",
                "post_id": "dry_run_youtube",
                "url": "https://youtube.com/watch?v=dry_run",
                "dry_run": True,
                "title": payload.get("title"),
            }

        service = self._get_service()
        from googleapiclient.http import MediaFileUpload

        from posting_package_adapter import _sanitize_youtube_text, YOUTUBE_DESC_MAX_BYTES, YOUTUBE_TITLE_MAX

        title = _sanitize_youtube_text(payload.get("title", "Video"))
        title = title[:YOUTUBE_TITLE_MAX].rstrip() or "Video"
        description = _sanitize_youtube_text(
            payload.get("description", ""),
            max_bytes=YOUTUBE_DESC_MAX_BYTES,
        ) or title

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": payload.get("tags", []),
                "categoryId": "22",
            },
            "status": {
                "privacyStatus": payload.get("privacy", "public"),
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
        request = service.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        deadline = time.monotonic() + UPLOAD_CHUNK_TIMEOUT_SECONDS
        while response is None:
            if time.monotonic() > deadline:
                raise TimeoutError("YouTube upload timed out")
            status, response = request.next_chunk()
            if status and getattr(status, "progress", None) is not None:
                deadline = time.monotonic() + UPLOAD_CHUNK_TIMEOUT_SECONDS

        video_id = response["id"]
        url = f"https://www.youtube.com/watch?v={video_id}"

        if thumbnail_path and Path(thumbnail_path).exists():
            thumb_media = MediaFileUpload(thumbnail_path, mimetype="image/png")
            service.thumbnails().set(videoId=video_id, media_body=thumb_media).execute()

        pinned = payload.get("pinned_comment")
        if pinned:
            try:
                pinned = _sanitize_youtube_text(pinned, max_bytes=YOUTUBE_DESC_MAX_BYTES)
                service.commentThreads().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "videoId": video_id,
                            "topLevelComment": {"snippet": {"textOriginal": pinned}},
                        }
                    },
                ).execute()
            except Exception:
                pass

        return {"status": "success", "platform": "youtube", "post_id": video_id, "url": url}
