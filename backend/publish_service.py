"""Orchestrate publishing from ShadowCast job output + posting packages."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from posting_package_adapter import build, select_video_format
from publishers.meta_publisher import MetaPublisher
from publishers.rumble_publisher import RumblePublisher
from publishers.tiktok_publisher import TikTokPublisher
from publishers.youtube_publisher import YouTubePublisher
from visual_quality import pick_best_contrast_path

OUTPUT_BASE = Path(__file__).parent / "output"
PUBLISH_LOG = OUTPUT_BASE / "publish_log.json"
_VARIANT_RE = re.compile(r"variant_[abc]")


def _swap_thumbnail_variant(path: str | None, variant: str) -> str | None:
    if not path:
        return path
    return _VARIANT_RE.sub(variant, path)


def _best_thumb_fname(base_dir: Path, hook_type: str, preferred: str | None = None) -> str | None:
    matches = sorted(base_dir.glob(f"*_{hook_type}_thumbnail_*.png"))
    if not matches:
        return preferred
    best = pick_best_contrast_path(matches)
    return best.name if best else (preferred or matches[0].name)


def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text.strip("_")[:60] or "product"


def _load_publish_log() -> list[dict[str, Any]]:
    if PUBLISH_LOG.exists():
        try:
            return json.loads(PUBLISH_LOG.read_text())
        except json.JSONDecodeError:
            return []
    return []


def _save_publish_log(entries: list[dict[str, Any]]) -> None:
    PUBLISH_LOG.parent.mkdir(parents=True, exist_ok=True)
    PUBLISH_LOG.write_text(json.dumps(entries[-500:], indent=2))


def _record_publish(entry: dict[str, Any]) -> None:
    log = _load_publish_log()
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    log.append(entry)
    _save_publish_log(log)


def resolve_job_assets(
    job_id: str,
    hook_type: str,
    video_format: str,
    *,
    product_slug: str | None = None,
    jobs: dict | None = None,
) -> dict[str, Any]:
    """Resolve video, posting package, and thumbnail paths for a job."""
    job_dir = OUTPUT_BASE / job_id
    if not job_dir.exists():
        raise FileNotFoundError(f"Job output not found: {job_id}")

    assets_data: dict[str, Any] | None = None
    video_fname: str | None = None
    thumb_fname: str | None = None
    thumbs_map: dict[str, str] = {}
    product_name = product_slug or ""

    if jobs and job_id in jobs:
        job = jobs[job_id]
        if job.get("mode") == "batch" and product_slug:
            for pr in job.get("product_results", []):
                if _slugify(pr.get("product_name", "")) == product_slug:
                    hook = (pr.get("hooks") or {}).get(hook_type, {})
                    assets_data = (hook.get("youtube_assets") or {}).get(video_format)
                    video_fname = (hook.get("videos") or {}).get(video_format)
                    thumbs_map = hook.get("thumbnails") or {}
                    thumb_fname = thumbs_map.get("variant_a") or next(iter(thumbs_map.values()), None)
                    product_name = product_slug
                    break
        else:
            hook = (job.get("results") or {}).get(hook_type, {})
            assets_data = (hook.get("youtube_assets") or {}).get(video_format)
            video_fname = (hook.get("videos") or {}).get(video_format)
            thumbs_map = hook.get("thumbnails") or {}
            thumb_fname = thumbs_map.get("variant_a") or next(iter(thumbs_map.values()), None)

    base_dir = job_dir / product_slug if product_slug else job_dir

    if not video_fname:
        pattern = f"*_{hook_type}_{video_format.replace('short_form', 'short_form').replace('long_form', 'long_form')}.mp4"
        if video_format == "short_form":
            pattern = f"*_{hook_type}_short_form.mp4"
        else:
            pattern = f"*_{hook_type}_long_form.mp4"
        matches = sorted(base_dir.glob(pattern))
        if matches:
            video_fname = matches[0].name

    if not assets_data:
        pkg_pattern = f"*_{hook_type}_{video_format}_youtube_package.json"
        pkg_matches = sorted(base_dir.glob(pkg_pattern))
        if pkg_matches:
            assets_data = json.loads(pkg_matches[0].read_text())

    # Prefer highest-contrast thumbnail among A/B/C (not hard-coded A).
    if thumbs_map:
        candidate_paths = [
            base_dir / name
            for name in thumbs_map.values()
            if name and (base_dir / name).is_file()
        ]
        best = pick_best_contrast_path(candidate_paths) if candidate_paths else None
        if best:
            thumb_fname = best.name
    if not thumb_fname:
        thumb_fname = _best_thumb_fname(base_dir, hook_type)

    if not video_fname or not assets_data:
        raise FileNotFoundError(
            f"Missing assets for job={job_id} hook={hook_type} format={video_format} slug={product_slug}"
        )

    prefix = f"{product_slug}/" if product_slug else ""
    video_path = str(job_dir / prefix / video_fname)
    thumb_path = str(job_dir / prefix / thumb_fname) if thumb_fname else None
    pkg_path = str(base_dir / f"{Path(video_fname).stem.rsplit('_', 2)[0]}_{hook_type}_{video_format}_youtube_package.json")

    return {
        "video_path": video_path,
        "thumbnail_path": thumb_path,
        "posting_package": assets_data,
        "posting_package_path": pkg_path if Path(pkg_path).exists() else None,
        "product_slug": product_slug,
    }


class PublishService:
    def __init__(self, jobs: dict | None = None, analytics=None):
        self.jobs = jobs or {}
        self.analytics = analytics
        self.youtube = YouTubePublisher()
        self.meta = MetaPublisher()
        self.tiktok = TikTokPublisher()
        self.rumble = RumblePublisher()

    @staticmethod
    def _relative_media_path(job_id: str, file_path: str | None, product_slug: str | None) -> str | None:
        if not file_path:
            return None
        base = OUTPUT_BASE / job_id
        try:
            rel = Path(file_path).resolve().relative_to(base.resolve())
            return str(rel).replace("\\", "/")
        except ValueError:
            return file_path

    def publish(
        self,
        job_id: str,
        hook_type: str,
        video_format: str,
        platform: str,
        *,
        product_slug: str | None = None,
        dry_run: bool = False,
        thumbnail_variant: str = "variant_a",
        target_page_id: str | None = None,
    ) -> dict[str, Any]:
        effective_format = select_video_format(platform, video_format)
        resolved = resolve_job_assets(
            job_id, hook_type, effective_format,
            product_slug=product_slug, jobs=self.jobs,
        )

        if thumbnail_variant in ("variant_b", "variant_c"):
            resolved["thumbnail_path"] = _swap_thumbnail_variant(
                resolved.get("thumbnail_path"), thumbnail_variant
            )

        payload = build(platform, resolved["posting_package"], {"format": effective_format})
        video_path = resolved["video_path"]
        thumb_path = resolved.get("thumbnail_path")

        if not dry_run:
            allow_gtts = os.getenv("ALLOW_GTTS_PUBLISH", "").strip() in ("1", "true", "True")
            try:
                from tts_generator import get_best_provider as get_best_tts
                best = get_best_tts()
            except Exception:
                best = "gtts"
            if best not in ("kokoro", "openai", "piper") and not allow_gtts:
                raise RuntimeError(
                    "Live publish blocked: only gTTS (or no quality TTS) is available. "
                    "Install Kokoro/Piper or configure OpenAI TTS, or set ALLOW_GTTS_PUBLISH=1."
                )

        rel_video = self._relative_media_path(job_id, video_path, product_slug)
        rel_thumb = self._relative_media_path(job_id, thumb_path, product_slug) if thumb_path else None
        media_video = f"{job_id}/{rel_video}" if rel_video else video_path
        media_thumb = f"{job_id}/{rel_thumb}" if rel_thumb else thumb_path

        if platform == "youtube":
            result = self.youtube.publish(video_path, payload, thumbnail_path=thumb_path, dry_run=dry_run)
        elif platform == "instagram":
            result = self.meta.publish_instagram(media_video, payload, cover_path=media_thumb, dry_run=dry_run)
        elif platform == "facebook":
            result = self.meta.publish_facebook(video_path, payload, page_id=target_page_id, dry_run=dry_run)
        elif platform == "tiktok":
            result = self.tiktok.publish(video_path, payload, dry_run=dry_run)
        elif platform == "rumble":
            result = self.rumble.publish(video_path, payload, dry_run=dry_run)
        else:
            raise ValueError(f"Unknown platform: {platform}")

        entry = {
            "job_id": job_id,
            "hook_type": hook_type,
            "video_format": effective_format,
            "platform": platform,
            "product_slug": product_slug,
            "result": result,
            "dry_run": dry_run,
        }
        _record_publish(entry)

        if not dry_run and self.analytics and result.get("status") == "success":
            try:
                self.analytics.track_video(
                    product_name=product_slug or job_id,
                    hook_type=hook_type,
                    format_type=effective_format,
                    video_path=video_path,
                    youtube_url=result.get("url") if platform == "youtube" else None,
                    youtube_video_id=result.get("post_id") if platform == "youtube" else None,
                )
            except Exception:
                pass

        return result

    def publish_batch(
        self,
        job_id: str,
        hook_type: str,
        video_format: str,
        platforms: list[str],
        **kwargs,
    ) -> list[dict[str, Any]]:
        results = []
        for platform in platforms:
            try:
                results.append(self.publish(job_id, hook_type, video_format, platform, **kwargs))
            except Exception as exc:
                results.append({"status": "error", "platform": platform, "message": str(exc)})
        return results
