"""Property-based validators for ShadowCast LLM outputs."""

import re
from typing import Any

AFFILIATE_BANNED = re.compile(
    r"\b(commission\s+rate|epc|hop\s+conversion|affiliate\s+marketer|"
    r"promoting\s+as\s+an\s+affiliate|earn\s+as\s+an\s+affiliate)\b",
    re.I,
)

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
    layouts = {s.get("layout") for s in segments if s.get("layout")}

    if content_style == "honest_review":
        has_cons = "cons" in styles or "con_point" in styles or any(
            CON_SIGNAL.search(str(s.get("text", ""))) for s in segments
        )
        if not has_cons:
            errors.append("honest_review requires at least one con/limitation segment")

    if content_style == "elimination":
        if "elimination" not in styles and "winner_reveal" not in layouts:
            errors.append("elimination style requires elimination text_style or winner_reveal layout")

    if content_style == "vs_battle":
        if "vs_split" not in layouts and "scorecard" not in layouts:
            errors.append("vs_battle requires vs_split or scorecard layout segment")

    if content_style == "budget_challenge":
        if "price_compare" not in layouts:
            errors.append("budget_challenge requires price_compare layout segment")

    if content_style == "worth_it_or_waste":
        if "verdict" not in styles:
            errors.append("worth_it_or_waste requires verdict text_style")

    return len(errors) == 0, errors


def validate_youtube_assets(assets: dict, affiliate_link: str = "") -> tuple[bool, list[str]]:
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

    errors.extend(check_buyer_language(_text_blob(assets)))

    pinned = str(assets.get("pinned_comment", ""))
    if affiliate_link and affiliate_link not in ("[AFFILIATE_LINK]", ""):
        link_count = pinned.lower().count(affiliate_link.lower())
        if link_count == 0:
            errors.append("pinned_comment must include product link once")
        elif link_count > 2:
            errors.append(f"pinned_comment includes link {link_count} times (max 2)")

    return len(errors) == 0, errors
