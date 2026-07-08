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
    if _has_layout(script):
        return

    product_name = product_info.get("product_name", "Our Pick")
    competitors = _as_list(product_info.get("competitors"))
    competitor = competitors[0] if competitors else "Top Alternative"
    features = _as_list(product_info.get("key_features"))
    price = product_info.get("price", "N/A")
    price_notes = product_info.get("price_comparison", "")

    segments = _target_segments(script)
    if not segments:
        return

    sid = _next_segment_id(script)
    injected = [
        _layout_segment(
            sid,
            2.5,
            "vs_split",
            product_a=product_name,
            product_b=competitor,
            text=f"{product_name} vs {competitor}",
            text_style="comparison",
        ),
    ]
    sid += 1

    spec_pairs = []
    if price_notes:
        spec_pairs.append(("Price / Value", price, "See competitor", "a"))
    spec_pairs.append(("Price", price, "Varies", "a"))
    for idx, feature in enumerate(features[:2]):
        spec_pairs.append((f"Feature {idx + 1}", feature, "Comparable", "a"))

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

    injected.append(
        _layout_segment(
            sid,
            2.5,
            "scorecard",
            product_a=product_name,
            product_b=competitor,
            scores=[
                {"category": "Value", "winner": "a"},
                {"category": "Features", "winner": "a"},
                {"category": "Reviews", "winner": "b"},
            ],
            text="Final Scorecard",
            text_style="scorecard",
        )
    )
    sid += 1

    injected.append(
        _layout_segment(
            sid,
            2.5,
            "winner_reveal",
            winner_name=product_name,
            text=f"Winner: {product_name}",
            text_style="verdict",
        )
    )

    insert_at = min(1, len(segments))
    segments[insert_at:insert_at] = injected


def _inject_elimination(script: dict, product_info: dict) -> None:
    product_name = product_info.get("product_name", "Our Pick")
    competitors = _as_list(product_info.get("competitors")) or ["Overhyped Option", "Overpriced Pick"]

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
    price = product_info.get("price", "N/A")
    competitors = _as_list(product_info.get("competitors"))

    price_products = [{"name": product_name, "price": price, "highlight": True}]
    for comp in competitors[:3]:
        price_products.append({"name": comp, "price": "Budget option", "highlight": False})
    if len(price_products) < 2:
        price_products.append({"name": "Generic Alternative", "price": "Lower", "highlight": False})

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

    return enriched
