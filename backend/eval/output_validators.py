"""Property-based validators for ShadowCast LLM outputs."""

import re
from typing import Any

from video_claims import (
    MIN_LONG_FORM_SPOKEN_WORDS,
    REQUIRED_LAYOUTS_BY_STYLE,
    SUPPORTED_ANIMATION_TOKENS,
    SUPPORTED_TRANSITION_TOKENS,
    count_spoken_words,
    sum_segment_durations,
)

AFFILIATE_BANNED = re.compile(
    r"\b(commission\s+rate|epc|hop\s+conversion|affiliate\s+marketer|"
    r"promoting\s+as\s+an\s+affiliate|earn\s+as\s+an\s+affiliate)\b",
    re.I,
)

LONG_FORM_LENGTH_ERROR_PREFIX = "long_form runtime:"

CON_SIGNAL = re.compile(
    r"\b(con|cons|downside|drawback|limitation|trade[- ]?off|not for|avoid)\b",
    re.I,
)


def _iter_segments(script: dict):
    if "chapters" in script:
        for chapter in script.get("chapters", []):
            for seg in chapter.get("segments", []):
                if isinstance(seg, dict):
                    yield seg
    else:
        for seg in script.get("segments", []):
            if isinstance(seg, dict):
                yield seg


def _text_blob(obj: Any) -> str:
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return " ".join(_text_blob(v) for v in obj.values())
    if isinstance(obj, list):
        return " ".join(_text_blob(v) for v in obj)
    return ""


def check_buyer_language(text: str) -> list[str]:
    errors = []
    if AFFILIATE_BANNED.search(text):
        errors.append("contains banned affiliate-marketer language")
    return errors


def _check_duration_contract(script: dict, fmt: str, errors: list[str]) -> None:
    declared = script.get("total_duration_seconds")
    if declared is not None:
        try:
            float(declared)
        except (TypeError, ValueError):
            errors.append("total_duration_seconds must be a number")
            return
    segments = list(_iter_segments(script))
    if not segments:
        return
    if any(seg.get("duration") is None for seg in segments):
        return
    # Segment durations are the contract (TTS re-times later). LLMs often stamp a
    # target runtime (e.g. 240) instead of sum(duration) — rewrite, don't hard-fail.
    summed = sum_segment_durations(script, fmt)
    script["total_duration_seconds"] = round(float(summed), 3)
    # Scaling durations cannot lengthen a TTS render; only more narration can.
    if fmt == "long_form":
        words = count_spoken_words(script, fmt)
        if words < MIN_LONG_FORM_SPOKEN_WORDS:
            errors.append(
                f"{LONG_FORM_LENGTH_ERROR_PREFIX} needs at least "
                f"{MIN_LONG_FORM_SPOKEN_WORDS} spoken words to clear the 120s floor (got {words})"
            )


def _check_animation_transition_tokens(script: dict, errors: list[str]) -> None:
    for seg in _iter_segments(script):
        anim = str(seg.get("animation", "")).strip().lower()
        if anim and anim not in SUPPORTED_ANIMATION_TOKENS:
            errors.append(f"unsupported animation token: {anim}")
        trans = str(seg.get("transition_to_next", "")).strip().lower()
        if trans and trans not in SUPPORTED_TRANSITION_TOKENS:
            errors.append(f"unsupported transition token: {trans}")


def validate_script_output(script: dict, content_style: str, fmt: str) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(script, dict):
        return False, ["output is not a dict"]
    if "__raw" in script and len(script) == 1:
        return False, ["JSON parse failed (__raw only)"]

    errors.extend(check_buyer_language(_text_blob(script)))

    if fmt == "short_form":
        segments = script.get("segments")
        if not isinstance(segments, list) or len(segments) < 3:
            errors.append("short_form requires segments list with at least 3 items")
        elif len(segments) > 25:
            errors.append(f"short_form segment count {len(segments)} exceeds 25")
        for key in ("hook_type", "content_style", "format", "title_suggestion"):
            if key not in script:
                errors.append(f"missing required key: {key}")
    elif fmt == "long_form":
        chapters = script.get("chapters")
        if not isinstance(chapters, list) or len(chapters) < 3:
            errors.append("long_form requires chapters list with at least 3 items")
        for key in ("hook_type", "content_style", "format", "title_suggestion"):
            if key not in script:
                errors.append(f"missing required key: {key}")
    else:
        errors.append(f"unknown format: {fmt}")

    segments = list(_iter_segments(script))
    styles = {str(s.get("text_style", "")).lower() for s in segments}
    layouts = {str(s.get("layout")) for s in segments if s.get("layout")}

    if content_style == "honest_review":
        has_cons = "cons" in styles or "con_point" in styles or any(
            CON_SIGNAL.search(str(s.get("text", ""))) for s in segments
        )
        if not has_cons:
            errors.append("honest_review requires at least one con/limitation segment")

    if content_style == "elimination":
        if "elimination" not in styles and "winner_reveal" not in layouts:
            errors.append("elimination style requires elimination text_style or winner_reveal layout")

    required_layouts = REQUIRED_LAYOUTS_BY_STYLE.get(content_style, set())
    missing_layouts = required_layouts - layouts
    if missing_layouts:
        errors.append(
            f"{content_style} requires layouts {sorted(required_layouts)}; missing {sorted(missing_layouts)}"
        )

    if content_style == "worth_it_or_waste":
        if "verdict" not in styles:
            errors.append("worth_it_or_waste requires verdict text_style")

    _check_duration_contract(script, fmt, errors)
    _check_animation_transition_tokens(script, errors)

    # Deduplicate while preserving order
    deduped: list[str] = []
    seen = set()
    for err in errors:
        if err not in seen:
            deduped.append(err)
            seen.add(err)
    return len(deduped) == 0, deduped


def validate_youtube_assets(
    assets: dict,
    affiliate_link: str = "",
    product_info: dict | None = None,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(assets, dict):
        return False, ["output is not a dict"]
    if "__raw" in assets and len(assets) == 1:
        return False, ["JSON parse failed (__raw only)"]

    title = str(assets.get("seo_title", ""))
    if not title:
        errors.append("missing seo_title")
    elif len(title) > 70:
        errors.append(f"seo_title length {len(title)} exceeds 70 chars")

    tags = assets.get("tags")
    if not isinstance(tags, list) or len(tags) < 5:
        errors.append("tags must be a list with at least 5 items")
    elif product_info:
        yt = product_info.get("_youtube_research") or {}
        research_tags = [str(tag).lower() for tag in (yt.get("recommended_tags") or [])[:12]]
        if research_tags:
            asset_tags = {str(tag).lower() for tag in tags}
            if not asset_tags.intersection(research_tags):
                errors.append("tags should intersect YouTube research recommendations")

    errors.extend(check_buyer_language(_text_blob(assets)))

    pinned = str(assets.get("pinned_comment", ""))
    if affiliate_link and affiliate_link not in ("[AFFILIATE_LINK]", ""):
        link_count = pinned.lower().count(affiliate_link.lower())
        if link_count == 0:
            errors.append("pinned_comment must include product link once")
        elif link_count > 2:
            errors.append(f"pinned_comment includes link {link_count} times (max 2)")

    return len(errors) == 0, errors
