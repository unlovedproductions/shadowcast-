"""Map ShadowCast posting packages to platform-specific publish payloads."""

from __future__ import annotations

import re
from typing import Any

PLATFORMS = ("youtube", "instagram", "facebook", "tiktok", "rumble")
VERTICAL_PLATFORMS = frozenset({"instagram", "tiktok", "rumble"})

YOUTUBE_TAG_MAX_CHARS = 500
INSTAGRAM_CAPTION_MAX = 2200
TIKTOK_TITLE_MAX = 150
TIKTOK_HASHTAG_MAX = 5
RUMBLE_TAG_MAX = 10


def _strip_hashtag_prefix(tag: str) -> str:
    return tag.lstrip("#").strip()


def _format_hashtags(tags: list[str], with_hash: bool = True) -> str:
    parts = []
    for tag in tags:
        clean = _strip_hashtag_prefix(str(tag))
        if not clean:
            continue
        parts.append(f"#{clean}" if with_hash else clean)
    return " ".join(parts)


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _truncate_youtube_tags(tags: list[str], max_chars: int = YOUTUBE_TAG_MAX_CHARS) -> list[str]:
    result: list[str] = []
    total = 0
    for tag in tags:
        clean = str(tag).strip()
        if not clean:
            continue
        extra = len(clean) + (1 if result else 0)
        if total + extra > max_chars:
            break
        result.append(clean)
        total += extra
    return result


def select_video_format(platform: str, requested_format: str) -> str:
    """Pick the best rendered format for a target platform."""
    if platform in VERTICAL_PLATFORMS:
        return "short_form"
    if platform == "youtube" and requested_format in ("short_form", "long_form"):
        return requested_format
    if platform == "facebook":
        return requested_format if requested_format in ("short_form", "long_form") else "long_form"
    return requested_format or "short_form"


def build(platform: str, assets: dict[str, Any], script_meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a normalized publish payload from a YouTube posting package."""
    if platform not in PLATFORMS:
        raise ValueError(f"Unsupported platform: {platform}")

    script_meta = script_meta or {}
    title = assets.get("seo_title") or script_meta.get("title_suggestion") or "Video"
    description = assets.get("seo_description") or ""
    pinned = assets.get("pinned_comment") or description
    tags = assets.get("tags") or []
    hashtags = assets.get("hashtags") or []
    hashtag_text = _format_hashtags(hashtags)

    if platform == "youtube":
        fmt = script_meta.get("format", "long_form")
        yt_tags = _truncate_youtube_tags(tags if isinstance(tags, list) else [])
        desc = description
        if fmt == "short_form" and "#shorts" not in desc.lower():
            desc = f"{desc}\n\n#Shorts"
        return {
            "platform": "youtube",
            "title": _truncate(title, 100),
            "description": desc,
            "tags": yt_tags,
            "pinned_comment": pinned,
            "is_short": fmt == "short_form",
            "privacy": "public",
        }

    if platform == "instagram":
        hashtag_text = _format_hashtags(hashtags)
        room = INSTAGRAM_CAPTION_MAX - (len(hashtag_text) + 2 if hashtag_text else 0)
        caption = _truncate(pinned, max(room, 0))
        if hashtag_text:
            caption = f"{caption}\n\n{hashtag_text}".strip()
        return {
            "platform": "instagram",
            "caption": _truncate(caption, INSTAGRAM_CAPTION_MAX),
            "hashtags": [_strip_hashtag_prefix(h) for h in hashtags][:30],
        }

    if platform == "facebook":
        return {
            "platform": "facebook",
            "title": _truncate(title, 100),
            "description": description,
        }

    if platform == "tiktok":
        caption = pinned
        if hashtag_text:
            caption = f"{caption}\n\n{hashtag_text}".strip()
        return {
            "platform": "tiktok",
            "title": _truncate(title, TIKTOK_TITLE_MAX),
            "description": _truncate(caption, 2200),
            "hashtags": [_strip_hashtag_prefix(h) for h in hashtags][:TIKTOK_HASHTAG_MAX],
        }

    if platform == "rumble":
        rumble_tags = tags if isinstance(tags, list) else []
        return {
            "platform": "rumble",
            "title": _truncate(title, 100),
            "description": description,
            "tags": [str(t).strip() for t in rumble_tags][:RUMBLE_TAG_MAX],
            "category": "Entertainment",
        }

    raise ValueError(f"Unhandled platform: {platform}")


def posting_package_filename(slug: str, hook_type: str, video_format: str) -> str:
    fmt = "short_form" if video_format == "short_form" else "long_form"
    return f"{slug}_{hook_type}_{fmt}_youtube_package.json"
