"""
ShadowCast YouTube Assets Generator — by Unloved Productions
Generates complete YouTube posting packages optimized for trust,
engagement, and affiliate conversions.
"""

import re

from eval.output_validators import validate_youtube_assets
from llm_client import chat_completion_json
from prompts import YOUTUBE_ASSETS_SYSTEM_PROMPT, build_youtube_assets_user_prompt


def _iter_script_segments(script: dict):
    if "chapters" in script:
        for chapter in script.get("chapters", []):
            for seg in chapter.get("segments", []):
                if isinstance(seg, dict):
                    yield seg
    else:
        for seg in script.get("segments", []):
            if isinstance(seg, dict):
                yield seg


def _collect_script_context(script: dict) -> str:
    parts = []
    if "chapters" in script:
        for chapter in script.get("chapters", []):
            chapter_name = str(chapter.get("chapter_name", "")).strip()
            if chapter_name:
                parts.append(f"[{chapter_name}]")
            for seg in chapter.get("segments", []):
                text = str(seg.get("text", "")).strip()
                if text:
                    parts.append(text)
    else:
        for seg in script.get("segments", []):
            text = str(seg.get("text", "")).strip()
            if text:
                parts.append(text)
    return " | ".join(parts)


def _fit_script_context(context: str, max_chars: int = 3600) -> str:
    if len(context) <= max_chars:
        return context
    head = max_chars // 2
    tail = max_chars - head
    return f"{context[:head]} | ... | {context[-tail:]}"


def _extract_signal_lines(script: dict, max_each: int = 4) -> dict:
    cons = []
    ctas = []
    verdicts = []
    con_re = re.compile(r"\b(con|cons|downside|drawback|limitation|trade[- ]?off|not for|avoid)\b", re.I)
    cta_re = re.compile(r"\b(link|description|check (the )?(price|details)|availability|fit for you|if this sounds)\b", re.I)
    verdict_re = re.compile(r"\b(verdict|worth it|waste|bottom line|winner)\b", re.I)

    for seg in _iter_script_segments(script):
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        style = str(seg.get("text_style", "")).strip().lower()
        lowered = text.lower()

        if style in {"cons", "con_point", "elimination"} or con_re.search(lowered):
            cons.append(text)
        if cta_re.search(lowered):
            ctas.append(text)
        if style in {"verdict", "scorecard"} or verdict_re.search(lowered):
            verdicts.append(text)

    def _dedupe_limit(lines):
        seen = set()
        out = []
        for line in lines:
            key = line.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(line)
            if len(out) >= max_each:
                break
        return out

    return {
        "cons": _dedupe_limit(cons),
        "ctas": _dedupe_limit(ctas),
        "verdicts": _dedupe_limit(verdicts),
    }


def generate_youtube_assets(product_info: dict, script: dict, video_format: str) -> dict:
    title_suggestion = script.get("title_suggestion", "")

    all_text = _fit_script_context(_collect_script_context(script))
    signals = _extract_signal_lines(script)
    cons_lines = _fit_script_context(" | ".join(signals["cons"]), max_chars=900) if signals["cons"] else "N/A"
    cta_lines = _fit_script_context(" | ".join(signals["ctas"]), max_chars=900) if signals["ctas"] else "N/A"
    verdict_lines = _fit_script_context(" | ".join(signals["verdicts"]), max_chars=900) if signals["verdicts"] else "N/A"

    user_prompt = build_youtube_assets_user_prompt(
        product_info,
        script,
        video_format,
        script_context=all_text,
        cons_lines=cons_lines,
        cta_lines=cta_lines,
        verdict_lines=verdict_lines,
    )

    parsed = chat_completion_json(
        YOUTUBE_ASSETS_SYSTEM_PROMPT,
        user_prompt,
        required_keys=["seo_title"],
        validate_fn=lambda payload: validate_youtube_assets(
            payload, str(product_info.get("affiliate_link", ""))
        )[0],
    )

    if not isinstance(parsed, dict) or "seo_title" not in parsed:
        fallback = {
            "seo_title": title_suggestion or f"{product_info['product_name']} - Honest Review",
            "seo_title_alternatives": [],
            "seo_description": f"Auto-generated posting package for {product_info['product_name']}.",
            "tags": product_info.get("keywords", [])[:20],
            "hashtags": [],
            "pinned_comment": "",
            "thumbnail_text_primary": product_info['product_name'],
            "_shadowcast_fallback": True,
        }
        if isinstance(parsed, dict):
            fallback.update(parsed)
        return fallback

    parsed["_shadowcast_fallback"] = False
    return parsed


def save_posting_package_readable(package: dict, product_info: dict, output_path: str):
    with open(output_path, "w") as f:
        f.write("=" * 70 + "\n")
        f.write("  YOUTUBE POSTING PACKAGE — Generated by ShadowCast\n")
        f.write(f"  Product: {product_info['product_name']}\n")
        if product_info.get('series_name'):
            f.write(f"  Series: {product_info['series_name']}\n")
        f.write("=" * 70 + "\n\n")

        for hook_type, formats in package.items():
            hook_name = hook_type.replace("_", " ").upper()
            for fmt_key, assets in formats.items():
                fmt_name = "SHORT-FORM (YouTube Shorts)" if fmt_key == "short_form" else "LONG-FORM (YouTube)"
                f.write("\n" + "━" * 70 + "\n")
                f.write(f"  HOOK: {hook_name} | FORMAT: {fmt_name}\n")
                f.write("━" * 70 + "\n\n")

                f.write(f"SEO TITLE:\n{assets.get('seo_title', 'N/A')}\n\n")
                f.write("Alternative Titles (A/B Test These):\n")
                for i, alt in enumerate(assets.get("seo_title_alternatives", []), 1):
                    f.write(f"  {i}. {alt}\n")

                f.write(f"\nSEO DESCRIPTION:\n{'-'*50}\n{assets.get('seo_description', 'N/A')}\n{'-'*50}\n\n")
                f.write(f"TAGS:\n{', '.join(assets.get('tags', []))}\n\n")
                f.write(f"HASHTAGS:\n{' '.join(assets.get('hashtags', []))}\n\n")

                f.write(f"PINNED COMMENT (Trust-Optimized):\n{'-'*50}\n{assets.get('pinned_comment', 'N/A')}\n{'-'*50}\n\n")
                f.write("Alternative Pinned Comments:\n")
                for i, alt in enumerate(assets.get("pinned_comment_alternatives", []), 1):
                    f.write(f"  {i}. {alt}\n")

                f.write(f"\nTHUMBNAIL (A/B Test Negative vs Positive Framing):\n")
                f.write(f"  Primary: {assets.get('thumbnail_text_primary', 'N/A')}\n")
                f.write(f"  Secondary: {assets.get('thumbnail_text_secondary', 'N/A')}\n")
                f.write(f"  Colors: {assets.get('thumbnail_color_scheme', 'N/A')}\n")
                f.write(f"  Tips: {assets.get('thumbnail_tips', 'N/A')}\n\n")

                f.write(f"END SCREEN: {assets.get('end_screen_strategy', 'N/A')}\n\n")
                f.write(f"CARDS: {assets.get('cards_strategy', 'N/A')}\n\n")
                f.write(f"COMMUNITY POST:\n{'-'*50}\n{assets.get('community_post_template', 'N/A')}\n{'-'*50}\n\n")
                f.write(f"POSTING TIME: {assets.get('best_posting_time', 'N/A')}\n")
                f.write(f"FREQUENCY: {assets.get('posting_frequency_tip', 'N/A')}\n\n")

                f.write("ENGAGEMENT BOOSTERS:\n")
                for i, t in enumerate(assets.get("engagement_boosters", []), 1):
                    f.write(f"  {i}. {t}\n")
                f.write("\nCROSS-PROMOTION:\n")
                for i, t in enumerate(assets.get("cross_promotion_ideas", []), 1):
                    f.write(f"  {i}. {t}\n")

                replies = assets.get("reply_templates", {})
                f.write(f"\nREPLY TEMPLATES:\n")
                f.write(f"  Positive: {replies.get('positive_comment','')}\n")
                f.write(f"  Question: {replies.get('question_about_product','')}\n")
                f.write(f"  Comparison: {replies.get('comparison_question','')}\n")
                f.write(f"  Negative: {replies.get('negative_comment','')}\n")
                f.write(f"  Where to Buy: {replies.get('where_to_buy','')}\n")

                series = assets.get("series_suggestions", [])
                if series:
                    f.write("\nNEXT VIDEO IDEAS:\n")
                    for i, s in enumerate(series, 1):
                        f.write(f"  {i}. {s}\n")
                f.write("\n")

        f.write("=" * 70 + "\n  END OF POSTING PACKAGE\n" + "=" * 70 + "\n")
    return output_path
