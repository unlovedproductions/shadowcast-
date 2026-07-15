"""YouTube Analytics + Data API stats sync using OAuth credentials."""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse

from credentials_store import CredentialsStore
from oauth_manager import OAuthManager


def extract_youtube_video_id(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host == "youtu.be":
        vid = parsed.path.lstrip("/").split("/")[0]
        return vid or None
    if host in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        parts = [p for p in parsed.path.split("/") if p]
        if parts and parts[0] == "shorts" and len(parts) > 1:
            return parts[1]
        qs = parse_qs(parsed.query)
        if "v" in qs:
            return qs["v"][0]
    return None


class YouTubeAnalyticsClient:
    def __init__(self, store: CredentialsStore | None = None):
        self.store = store or CredentialsStore()
        self.oauth = OAuthManager(self.store)

    def _credentials(self):
        from google.oauth2.credentials import Credentials

        creds_data = self.oauth.get_credentials("youtube")
        if not creds_data or not creds_data.get("access_token"):
            raise ValueError("YouTube not connected — complete OAuth first")
        return Credentials(
            token=creds_data.get("access_token"),
            refresh_token=creds_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        )

    def fetch_video_stats(self, youtube_video_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not youtube_video_ids:
            return {}

        wanted = {vid for vid in youtube_video_ids if vid}
        creds = self._credentials()
        from googleapiclient.discovery import build

        stats_by_id: dict[str, dict[str, Any]] = {}
        end = date.today()
        start = end - timedelta(days=365)

        try:
            analytics = build("youtubeAnalytics", "v2", credentials=creds)
            response = analytics.reports().query(
                ids="channel==MINE",
                startDate=start.isoformat(),
                endDate=end.isoformat(),
                metrics="views,estimatedMinutesWatched,averageViewDuration,likes,comments,shares,subscribersGained",
                dimensions="video",
                sort="-views",
                maxResults=200,
            ).execute()
            headers = [h["name"] for h in response.get("columnHeaders", [])]
            for row in response.get("rows", []):
                data = dict(zip(headers, row))
                vid = str(data.get("video", ""))
                if vid not in wanted:
                    continue
                stats_by_id[vid] = {
                    "views": int(data.get("views", 0) or 0),
                    "estimated_minutes_watched": float(data.get("estimatedMinutesWatched", 0) or 0),
                    "average_view_duration": float(data.get("averageViewDuration", 0) or 0),
                    "likes": int(data.get("likes", 0) or 0),
                    "comments": int(data.get("comments", 0) or 0),
                    "shares": int(data.get("shares", 0) or 0),
                    "subscribers_gained": int(data.get("subscribersGained", 0) or 0),
                }
        except Exception:
            pass

        missing = [vid for vid in wanted if vid not in stats_by_id]
        if missing:
            yt_data = build("youtube", "v3", credentials=creds)
            resp = yt_data.videos().list(part="statistics", id=",".join(missing[:50])).execute()
            for item in resp.get("items", []):
                vid = item["id"]
                s = item.get("statistics", {})
                stats_by_id[vid] = {
                    "views": int(s.get("viewCount", 0) or 0),
                    "likes": int(s.get("likeCount", 0) or 0),
                    "comments": int(s.get("commentCount", 0) or 0),
                    "estimated_minutes_watched": stats_by_id.get(vid, {}).get("estimated_minutes_watched", 0),
                    "average_view_duration": stats_by_id.get(vid, {}).get("average_view_duration", 0),
                    "shares": stats_by_id.get(vid, {}).get("shares", 0),
                    "subscribers_gained": stats_by_id.get(vid, {}).get("subscribers_gained", 0),
                }

        return stats_by_id
