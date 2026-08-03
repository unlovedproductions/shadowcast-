
import json
import os
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from oauth_manager import OAuthManager

PLATFORMS = ("youtube", "instagram", "facebook", "tiktok", "rumble")
MAX_QUEUE_ATTEMPTS = 5


class SocialPoster:
    def __init__(self, config_path=None):
        self.config = {}
        self.load_credentials(config_path)
        self.queue_file = str(Path(__file__).parent / "output" / "posting_queue.json")
        os.makedirs(os.path.dirname(self.queue_file), exist_ok=True)
        self.load_queue()
        self.oauth = OAuthManager()

    def load_credentials(self, config_path):
        self.config["instagram_access_token"] = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        self.config["tiktok_client_key"] = os.getenv("TIKTOK_CLIENT_KEY")
        self.config["tiktok_client_secret"] = os.getenv("TIKTOK_CLIENT_SECRET")
        self.config["tiktok_access_token"] = os.getenv("TIKTOK_ACCESS_TOKEN")

    def _check_credentials(self):
        oauth_status = self.oauth.status()
        return {
            "youtube": oauth_status.get("youtube", {}).get("connected", False),
            "instagram": oauth_status.get("instagram", {}).get("connected", False) or bool(self.config.get("instagram_access_token")),
            "facebook": oauth_status.get("facebook", {}).get("connected", False),
            "tiktok": oauth_status.get("tiktok", {}).get("connected", False) or bool(
                self.config.get("tiktok_client_key") and self.config.get("tiktok_access_token")
            ),
            "rumble": oauth_status.get("rumble", {}).get("connected", False),
        }

    def post_to_instagram(self, video_path, caption, hashtags=None, cover_image=None, dry_run=False):
        hashtags = hashtags or []
        if dry_run:
            return {"post_id": "dry_run_instagram_123", "status": "success", "dry_run": True}

        from publishers.meta_publisher import MetaPublisher
        publisher = MetaPublisher()
        return publisher.publish_instagram(
            video_path,
            {"caption": f"{caption} {' '.join('#' + h.lstrip('#') for h in hashtags)}".strip()},
            cover_path=cover_image,
            dry_run=False,
        )

    def post_to_tiktok(self, video_path, title, hashtags=None, cover_image=None, dry_run=False):
        hashtags = hashtags or []
        if dry_run:
            return {"post_id": "dry_run_tiktok_456", "status": "success", "dry_run": True}

        from publishers.tiktok_publisher import TikTokPublisher
        publisher = TikTokPublisher()
        return publisher.publish(
            video_path,
            {"title": title, "description": title, "hashtags": hashtags},
            dry_run=False,
        )

    def load_queue(self):
        if os.path.exists(self.queue_file):
            with open(self.queue_file, "r") as f:
                self.queue = json.load(f)
        else:
            self.queue = []
        for post in self.queue:
            post.setdefault("attempts", 0)
            post.setdefault("failed", False)
            post.setdefault("last_error", "")

    def save_queue(self):
        with open(self.queue_file, "w") as f:
            json.dump(self.queue, f, indent=4)

    def schedule_post(
        self, platform, video_path, caption, hashtags, scheduled_time,
        job_id=None, hook_type=None, video_format=None, product_slug=None,
    ):
        post = {
            "platform": platform,
            "video_path": video_path,
            "caption": caption,
            "hashtags": hashtags,
            "scheduled_time": scheduled_time,
            "posted": False,
            "failed": False,
            "attempts": 0,
            "last_error": "",
            "job_id": job_id,
            "hook_type": hook_type,
            "video_format": video_format,
            "product_slug": product_slug,
        }
        self.queue.append(post)
        self.save_queue()
        return {"status": "scheduled", "platform": platform, "scheduled_time": scheduled_time}

    def get_queue(self):
        return [post for post in self.queue if not post["posted"] and not post.get("failed")]

    def process_queue(self, dry_run=False, publish_service=None, jobs=None):
        now = datetime.now()
        processed = 0
        for post in self.queue:
            if post["posted"] or post.get("failed"):
                continue
            if datetime.fromisoformat(post["scheduled_time"]) > now:
                continue

            attempts = int(post.get("attempts") or 0)
            if attempts >= MAX_QUEUE_ATTEMPTS:
                post["failed"] = True
                post["last_error"] = post.get("last_error") or "Max retry attempts exceeded"
                continue

            post["attempts"] = attempts + 1

            if publish_service and post.get("job_id") and post.get("hook_type"):
                result = publish_service.publish(
                    post["job_id"],
                    post["hook_type"],
                    post.get("video_format") or "short_form",
                    post["platform"],
                    product_slug=post.get("product_slug"),
                    dry_run=dry_run,
                )
            elif post["platform"] == "instagram":
                result = self.post_to_instagram(
                    post["video_path"], post["caption"], post["hashtags"], dry_run=dry_run
                )
            elif post["platform"] == "tiktok":
                result = self.post_to_tiktok(
                    post["video_path"], post["caption"], post["hashtags"], dry_run=dry_run
                )
            elif publish_service and post["platform"] in PLATFORMS:
                result = {"status": "error", "message": "Scheduled post missing job_id/hook_type"}
            else:
                result = {"status": "error", "message": f"Unknown platform: {post['platform']}"}

            if result.get("status") == "success":
                post["posted"] = True
                post["last_error"] = ""
                processed += 1
            else:
                post["last_error"] = str(result.get("message") or result)
                if post["attempts"] >= MAX_QUEUE_ATTEMPTS:
                    post["failed"] = True
        self.save_queue()
        return processed

    def repurpose_for_platform(self, video_path, platform, output_path=None):
        if not output_path:
            base, ext = os.path.splitext(video_path)
            output_path = f"{base}_{platform}{ext}"

        if subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0:
            return video_path

        if platform in ("instagram", "tiktok", "rumble"):
            ffmpeg_cmd = [
                "ffmpeg", "-i", video_path,
                "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1",
                "-t", "90" if platform == "instagram" else "180",
                output_path,
            ]
        else:
            return video_path

        try:
            subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
            return output_path
        except subprocess.CalledProcessError:
            return video_path


def get_platform_status():
    poster_instance = SocialPoster()
    credentials_status = poster_instance._check_credentials()
    labels = {True: "Configured", False: "Not Configured"}
    return {p: labels[credentials_status.get(p, False)] for p in PLATFORMS}
