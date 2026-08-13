"""Deterministic script enrichment after LLM generation."""

import copy
import re

from content_styles import normalize_content_style

TEXT_STYLE_ALIASES = {
    "pro_point": "pros",
    "con_point": "cons",
}


def _as_list(value):
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return []


def _clean_comparison_value(value) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.lower() in {"n/a", "na", "none", "unknown", "tbd", "varies", "comparable"}:
        return ""
    return text


def _clean_competitors(product_info: dict, limit: int = None) -> list:
    cleaned = []
    for comp in _as_list(product_info.get("competitors")):
        cc = _clean_comparison_value(comp)
        if cc:
            cleaned.append(cc)
    if limit is not None:
        return cleaned[:limit]
    return cleaned


def _normalize_segment(seg: dict) -> dict:
    style = seg.get("text_style", "")
    if style in TEXT_STYLE_ALIASES:
        seg["text_style"] = TEXT_STYLE_ALIASES[style]
    return seg


def _iter_segment_lists(script: dict):
    if "segments" in script:
        yield script["segments"]
    for chapter in script.get("chapters", []):
        if "segments" in chapter:
            yield chapter["segments"]


def _has_layout(script: dict, layout_name: str = None) -> bool:
    for segments in _iter_segment_lists(script):
        for seg in segments:
            layout = seg.get("layout")
            if not layout:
                continue
            if layout_name is None or layout == layout_name:
                return True
    return False


def _next_segment_id(script: dict) -> int:
    max_id = 0
    for segments in _iter_segment_lists(script):
        for seg in segments:
            max_id = max(max_id, int(seg.get("segment_id", 0) or 0))
    return max_id + 1


def _target_segments(script: dict) -> list:
    if "segments" in script:
        return script["segments"]
    chapters = script.get("chapters", [])
    if not chapters:
        return []
    for chapter in chapters:
        name = chapter.get("chapter_name", "").lower()
        if any(word in name for word in ("vs", "compar", "battle", "score", "winner")):
            return chapter.setdefault("segments", [])
    return chapters[-1].setdefault("segments", [])


def _layout_segment(segment_id: int, duration: float, layout: str, **extra) -> dict:
    seg = {
        "segment_id": segment_id,
        "duration": duration,
        "text": extra.pop("text", ""),
        "text_style": extra.pop("text_style", "comparison"),
        "layout": layout,
        "animation": "fade_in",
        "transition_to_next": "fade",
    }
    seg.update(extra)
    return seg


def _inject_vs_battle(script: dict, product_info: dict) -> None:
    """Inject any missing required vs_battle layouts (partial LLM layouts still get filled)."""
    has_vs = _has_layout(script, "vs_split")
    has_scorecard = _has_layout(script, "scorecard")
    has_winner = _has_layout(script, "winner_reveal")
    if has_vs and has_scorecard and has_winner:
        return

    product_name = product_info.get("product_name", "Our Pick")
    competitors = _as_list(product_info.get("competitors"))
    competitor = _clean_comparison_value(competitors[0]) if competitors else ""
    if not competitor:
        return
    price = _clean_comparison_value(product_info.get("price", ""))
    price_notes = _clean_comparison_value(product_info.get("price_comparison", ""))

    segments = _target_segments(script)
    if not segments:
        return

    sid = _next_segment_id(script)
    injected = []

    if not has_vs:
        injected.append(
            _layout_segment(
                sid,
                2.5,
                "vs_split",
                product_a=product_name,
                product_b=competitor,
                text=f"{product_name} vs {competitor}",
                text_style="comparison",
            )
        )
        sid += 1

    spec_pairs = []
    if price and price_notes:
        spec_pairs.append(("Price / Value", price, price_notes, "none"))

    for row in product_info.get("comparison_specs", []) or []:
        if not isinstance(row, dict):
            continue
        spec_name = _clean_comparison_value(row.get("spec_name") or row.get("name"))
        value_a = _clean_comparison_value(row.get("value_a"))
        value_b = _clean_comparison_value(row.get("value_b"))
        winner = str(row.get("winner", "none")).strip().lower()
        if winner not in {"a", "b", "none"}:
            winner = "none"
        if spec_name and value_a and value_b:
            spec_pairs.append((spec_name, value_a, value_b, winner))

    if not _has_layout(script, "spec_compare"):
        for spec_name, value_a, value_b, winner in spec_pairs[:3]:
            injected.append(
                _layout_segment(
                    sid,
                    2.0,
                    "spec_compare",
                    spec_name=spec_name,
                    value_a=value_a,
                    value_b=value_b,
                    winner=winner,
                    text=spec_name,
                    text_style="comparison",
                )
            )
            sid += 1

    winners = [winner for _, _, _, winner in spec_pairs if winner in {"a", "b"}]
    if not winners:
        winners = ["a"]

    if not has_scorecard:
        score_rows = [
            {"category": f"Round {idx + 1}", "winner": winner}
            for idx, winner in enumerate(winners[:3])
        ]
        injected.append(
            _layout_segment(
                sid,
                2.5,
                "scorecard",
                product_a=product_name,
                product_b=competitor,
                scores=score_rows,
                text="Final Scorecard",
                text_style="scorecard",
            )
        )
        sid += 1

    if not has_winner:
        a_wins = winners.count("a")
        b_wins = winners.count("b")
        winner_name = product_name if a_wins >= b_wins else competitor
        injected.append(
            _layout_segment(
                sid,
                2.5,
                "winner_reveal",
                winner_name=winner_name,
                text=f"Winner: {winner_name}",
                text_style="verdict",
            )
        )

    if injected:
        insert_at = min(1, len(segments))
        segments[insert_at:insert_at] = injected

    if len(segments) < 3:
        sid = _next_segment_id(script)
        while len(segments) < 3:
            segments.append(
                {
                    "segment_id": sid,
                    "duration": 2.0,
                    "text": f"Why {product_name} matters in this comparison",
                    "text_style": "comparison",
                    "animation": "fade_in",
                    "transition_to_next": "fade",
                }
            )
            sid += 1


def _inject_elimination(script: dict, product_info: dict) -> None:
    product_name = product_info.get("product_name", "Our Pick")
    competitors = _clean_competitors(product_info, limit=2)
    if not competitors:
        return

    for segments in _iter_segment_lists(script):
        for seg in segments:
            text = seg.get("text", "").lower()
            if any(word in text for word in ("reject", "eliminate", "skip", "avoid", "pass on")):
                seg["text_style"] = "elimination"

    if _has_layout(script, "winner_reveal"):
        return

    segments = _target_segments(script)
    if not segments:
        return

    sid = _next_segment_id(script)
    for comp in competitors[:2]:
        segments.insert(
            0,
            {
                "segment_id": sid,
                "duration": 1.8,
                "text": f"Eliminated: {comp}",
                "text_style": "elimination",
                "animation": "shake",
                "transition_to_next": "cut",
            },
        )
        sid += 1

    winner_seg = _layout_segment(
        sid,
        2.5,
        "winner_reveal",
        winner_name=product_name,
        text=f"Winner: {product_name}",
        text_style="verdict",
    )
    segments.insert(max(len(segments) - 1, 0), winner_seg)


def _inject_budget_challenge(script: dict, product_info: dict) -> None:
    if _has_layout(script, "price_compare"):
        return

    product_name = product_info.get("product_name", "Our Pick")
    price = _clean_comparison_value(product_info.get("price")) or "Check current listing"
    competitors = _clean_competitors(product_info, limit=3)
    if not competitors:
        return

    price_products = [{"name": product_name, "price": price, "highlight": True}]
    for comp in competitors:
        price_products.append({"name": comp, "price": "Check current listing", "highlight": False})

    segments = _target_segments(script)
    if not segments:
        return

    sid = _next_segment_id(script)
    segments.insert(
        min(2, len(segments)),
        _layout_segment(
            sid,
            2.5,
            "price_compare",
            price_products=price_products,
            text="Budget Comparison",
            text_style="comparison",
        ),
    )


def _ensure_verdict_styling(script: dict) -> None:
    for chapter in script.get("chapters", []):
        chapter_name = chapter.get("chapter_name", "").lower()
        if "verdict" in chapter_name:
            for seg in chapter.get("segments", []):
                seg["text_style"] = "verdict"

    for segments in _iter_segment_lists(script):
        for seg in segments:
            text = seg.get("text", "").lower()
            if re.search(r"\b(worth it|waste|verdict)\b", text):
                seg["text_style"] = "verdict"


def _ensure_honest_review_balance(script: dict, product_info: dict) -> None:
    has_pro = False
    has_con = False
    con_re = re.compile(r"\b(con|cons|downside|drawback|limitation|trade[- ]?off|not for)\b")

    for segments in _iter_segment_lists(script):
        for seg in segments:
            style = str(seg.get("text_style", "")).strip().lower()
            text = str(seg.get("text", "")).strip().lower()
            if style in {"pros", "pro_point"}:
                has_pro = True
            if style in {"cons", "con_point", "elimination"} or con_re.search(text):
                has_con = True
            if has_pro and has_con:
                return

    segments = _target_segments(script)
    if not segments:
        script.setdefault("segments", [])
        segments = script["segments"]

    sid = _next_segment_id(script)
    product_name = product_info.get("product_name", "This product")

    if not has_pro:
        segments.append(
            {
                "segment_id": sid,
                "duration": 2.4,
                "text": f"Based on available specs and buyer feedback, {product_name} shows practical strengths for the right use case.",
                "text_style": "pros",
                "animation": "fade_in",
                "transition_to_next": "fade",
            }
        )
        sid += 1

    if not has_con:
        segments.append(
            {
                "segment_id": sid,
                "duration": 2.6,
                "text": "Limitations: fit and expectations vary by use case, so check recent buyer feedback before purchasing.",
                "text_style": "cons",
                "animation": "fade_in",
                "transition_to_next": "fade",
            }
        )


def _clamp_overlay_text(text: str, max_words: int) -> str:
    words = [w for w in str(text or "").split() if w.strip()]
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words])


def _apply_kinetic_presets(script: dict) -> None:
    """Short-form retention presets: tight overlays, beat cadence, strong first frame."""
    fmt = str(script.get("format") or "").strip()
    is_short = fmt == "short_form" or ("segments" in script and "chapters" not in script)
    max_words = 6 if is_short else 12
    min_dur = 1.0 if is_short else 3.0
    max_dur = 1.5 if is_short else 5.0

    first = True
    for segments in _iter_segment_lists(script):
        for seg in segments:
            if not isinstance(seg, dict):
                continue
            text = str(seg.get("text") or "").strip()
            if text and not seg.get("layout"):
                clamped = _clamp_overlay_text(text, max_words)
                if clamped != text:
                    seg["text"] = clamped
            try:
                dur = float(seg.get("duration") or 0)
            except (TypeError, ValueError):
                dur = 0.0
            if dur > 0:
                seg["duration"] = max(min_dur, min(max_dur, dur))
            if first and not seg.get("layout"):
                style = str(seg.get("text_style") or "").strip()
                if style not in (
                    "headline_bold",
                    "question",
                    "stat_number",
                    "accent_pop",
                    "verdict",
                    "cta_button",
                ):
                    seg["text_style"] = "headline_bold"
                anim = str(seg.get("animation") or "").strip()
                if anim not in ("impact_scale", "pop_in", "zoom_in"):
                    seg["animation"] = "impact_scale"
                first = False

    # Keep total_duration_seconds honest after clamps
    total = 0.0
    for segments in _iter_segment_lists(script):
        for seg in segments:
            try:
                total += float(seg.get("duration") or 0)
            except (TypeError, ValueError):
                pass
    if total > 0:
        script["total_duration_seconds"] = round(total, 2)


def enrich_script(script: dict, product_info: dict, content_style: str) -> dict:
    """Inject layout segments and fix text_style aliases after LLM generation."""
    enriched = copy.deepcopy(script)
    style = normalize_content_style(content_style)

    for segments in _iter_segment_lists(enriched):
        for idx, seg in enumerate(segments):
            segments[idx] = _normalize_segment(seg)

    if style == "vs_battle":
        _inject_vs_battle(enriched, product_info)
    elif style == "elimination":
        _inject_elimination(enriched, product_info)
    elif style == "budget_challenge":
        _inject_budget_challenge(enriched, product_info)
    elif style == "worth_it_or_waste":
        _ensure_verdict_styling(enriched)
    elif style == "honest_review":
        _ensure_honest_review_balance(enriched, product_info)

    _apply_kinetic_presets(enriched)
    return enriched
