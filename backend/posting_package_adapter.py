"""Map ShadowCast posting packages to platform-specific publish payloads."""

from __future__ import annotations

from typing import Any

PLATFORMS = ("youtube", "instagram", "facebook", "tiktok", "rumble")
VERTICAL_PLATFORMS = frozenset({"instagram", "tiktok", "rumble"})

YOUTUBE_TAG_MAX_CHARS = 500
YOUTUBE_DESC_MAX_BYTES = 5000
YOUTUBE_TITLE_MAX = 100
INSTAGRAM_CAPTION_MAX = 2200
TIKTOK_TITLE_MAX = 150
TIKTOK_HASHTAG_MAX = 5
RUMBLE_TAG_MAX = 10

# TikTok Content Posting API privacy_level values
TIKTOK_PRIVACY_LEVELS = frozenset(
    {
        "PUBLIC_TO_EVERYONE",
        "MUTUAL_FOLLOW_FRIENDS",
        "FOLLOWER_OF_CREATOR",
        "SELF_ONLY",
    }
)


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


def _sanitize_youtube_text(text: str, *, max_bytes: int | None = None) -> str:
    """YouTube rejects < and > in snippet text; descriptions are limited to 5000 bytes."""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    text = "".join(ch for ch in text if ch in "\n\r\t" or ord(ch) >= 32)
    text = text.replace("<", "(").replace(">", ")").strip()
    if not max_bytes:
        return text
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    trimmed = encoded[:max_bytes].decode("utf-8", errors="ignore").rstrip()
    if len(trimmed) > 3:
        return trimmed[:-3].rstrip() + "..."
    return trimmed


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


def _bool_meta(script_meta: dict[str, Any], key: str, default: bool) -> bool:
    if key not in script_meta:
        return default
    val = script_meta[key]
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    return str(val).strip().lower() in ("1", "true", "yes", "on")


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
        desc = _sanitize_youtube_text(description, max_bytes=YOUTUBE_DESC_MAX_BYTES)
        if fmt == "short_form" and "#shorts" not in desc.lower():
            desc = _sanitize_youtube_text(f"{desc}\n\n#Shorts", max_bytes=YOUTUBE_DESC_MAX_BYTES)
        if not desc:
            desc = _sanitize_youtube_text(title, max_bytes=YOUTUBE_DESC_MAX_BYTES) or "Video description."
        safe_title = _truncate(_sanitize_youtube_text(title), YOUTUBE_TITLE_MAX)
        safe_pinned = _sanitize_youtube_text(pinned, max_bytes=YOUTUBE_DESC_MAX_BYTES)
        return {
            "platform": "youtube",
            "title": safe_title,
            "description": desc,
            "tags": yt_tags,
            "pinned_comment": safe_pinned,
            "is_short": fmt == "short_form",
            "privacy": "public",
        }

    if platform == "instagram":
        hashtag_text = _format_hashtags(hashtags)
        room = INSTAGRAM_CAPTION_MAX - (len(hashtag_text) + 2 if hashtag_text else 0)
        caption = _truncate(pinned, max(room, 0))
        if hashtag_text:
            caption = f"{caption}\n\n{hashtag_text}".strip()
        clean_tags = [_strip_hashtag_prefix(h) for h in hashtags][:30]
        # Graph API Reels fields used by meta_publisher.publish_instagram
        return {
            "platform": "instagram",
            "caption": _truncate(caption, INSTAGRAM_CAPTION_MAX),
            "hashtags": clean_tags,
            "media_type": "REELS",
            "share_to_feed": _bool_meta(script_meta, "share_to_feed", True),
            "cover_url": script_meta.get("cover_url") or assets.get("thumbnail_url"),
            "location_id": script_meta.get("location_id"),
            "collaborators": script_meta.get("collaborators") or [],
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
        privacy = str(script_meta.get("privacy_level") or "PUBLIC_TO_EVERYONE").strip().upper()
        if privacy not in TIKTOK_PRIVACY_LEVELS:
            privacy = "PUBLIC_TO_EVERYONE"
        cover_ts = script_meta.get("video_cover_timestamp_ms")
        try:
            cover_ts_int = int(cover_ts) if cover_ts is not None else 1000
        except (TypeError, ValueError):
            cover_ts_int = 1000
        # post_info fields for TikTok Content Posting API /post/publish/video/init/
        return {
            "platform": "tiktok",
            "title": _truncate(title, TIKTOK_TITLE_MAX),
            "description": _truncate(caption, 2200),
            "hashtags": [_strip_hashtag_prefix(h) for h in hashtags][:TIKTOK_HASHTAG_MAX],
            "privacy_level": privacy,
            "disable_comment": _bool_meta(script_meta, "disable_comment", False),
            "disable_duet": _bool_meta(script_meta, "disable_duet", False),
            "disable_stitch": _bool_meta(script_meta, "disable_stitch", False),
            "video_cover_timestamp_ms": max(0, cover_ts_int),
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
