"""APF payload normalization for ShadowCast ProductInfo."""

import json
import re

from content_styles import normalize_content_style, series_name_for_style

STYLE_FROM_ANGLE = [
    (("worth it", "hype", "waste"), "worth_it_or_waste"),
    (("vs", "compare", "better than"), "vs_battle"),
    (("budget", "under $", "cheapest"), "budget_challenge"),
    (("eliminate", "rejected", "skip these"), "elimination"),
    (("honest", "pros and cons", "red flags"), "honest_review"),
]


def _clean(value):
    if value is None:
        return ""
    if isinstance(value, list):
        return "; ".join([_clean(v) for v in value if _clean(v)])
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def _pick(obj, keys):
    if not isinstance(obj, dict):
        return ""
    lowered = {str(k).lower(): k for k in obj.keys()}
    for key in keys:
        if key in obj and _clean(obj[key]):
            return obj[key]
        real = lowered.get(str(key).lower())
        if real and _clean(obj[real]):
            return obj[real]
    return ""


def _first_product(payload):
    if isinstance(payload, list):
        return payload[0] if payload else {}
    if not isinstance(payload, dict):
        return {}
    if isinstance(payload.get("product"), dict):
        return payload["product"]
    for key in ["selectedProduct", "apfProduct", "item", "offer"]:
        if isinstance(payload.get(key), dict):
            return payload[key]
    for key in ["products", "items", "data", "results", "offers"]:
        if isinstance(payload.get(key), list) and payload[key]:
            return _first_product(payload[key])
    return payload


def _money_label(value, fallback="Varies"):
    raw = _clean(value).replace("$", "").replace(",", "")
    try:
        number = float(raw)
        return f"${number:.2f}"
    except (TypeError, ValueError):
        text = _clean(value)
        return text or fallback


def _infer_style_from_angles(angles):
    text = " ".join(_clean(a).lower() for a in (angles or []))
    for patterns, style in STYLE_FROM_ANGLE:
        if any(pattern in text for pattern in patterns):
            return style
    return "honest_review"


def _commission_discount(product, brief):
    rate = _pick(product, ["commission_rate", "commissionRate", "commission"])
    if not rate:
        rate = brief.get("commission_rate") or brief.get("commissionRate")
    rate_text = _clean(rate)
    if not rate_text:
        return ""
    if "%" in rate_text:
        return f"Affiliate commission: {rate_text}"
    try:
        pct = float(rate_text)
        return f"Affiliate commission: {pct:g}%"
    except ValueError:
        return f"Affiliate commission: {rate_text}"


def _filter_competitors(candidates, vendor):
    vendor_clean = _clean(vendor).lower()
    result = []
    for item in candidates or []:
        name = _clean(item)
        if not name:
            continue
        if vendor_clean and name.lower() == vendor_clean:
            continue
        if name not in result:
            result.append(name)
    return result


def normalize_apf_payload(payload: dict) -> dict:
    """Return normalized ProductInfo fields and recommended_content_style."""
    raw = payload.get("payload") if isinstance(payload, dict) and isinstance(payload.get("payload"), dict) else payload
    product = _first_product(raw)

    brief = {}
    if isinstance(raw, dict):
        brief = raw.get("review_brief") or raw.get("reviewBrief") or {}
    if not isinstance(brief, dict):
        brief = {}

    review_sources = []
    if isinstance(raw, dict) and isinstance(raw.get("review_sources"), list):
        review_sources = raw["review_sources"]

    product_name = _clean(_pick(product, ["name", "product_name", "productName", "title"]))
    vendor = _clean(_pick(product, ["vendor", "vendor_name", "seller", "brand"]))
    niche = _clean(_pick(product, ["category", "niche", "product_category"])) or "ClickBank"
    affiliate_link = _clean(_pick(product, [
        "affiliate_url", "affiliateLink", "affiliate_link", "hoplink", "product_url", "url"
    ]))

    positives = brief.get("positive_signals") or []
    negatives = brief.get("negative_signals") or []
    claims = brief.get("common_claims") or []
    complaints = brief.get("common_complaints") or []
    angles = brief.get("best_video_angles") or []

    recommended_style = normalize_content_style(
        brief.get("recommended_content_style")
        or brief.get("recommendedContentStyle")
        or _infer_style_from_angles(angles)
    )

    suggested = brief.get("suggested_competitors") or brief.get("suggestedCompetitors") or []
    if isinstance(suggested, str):
        suggested = [s.strip() for s in re.split(r"[,;]", suggested) if s.strip()]
    competitors = _filter_competitors(suggested, vendor)

    price = _clean(brief.get("price_display") or brief.get("priceDisplay"))
    if not price:
        apv = _pick(product, ["apv", "average_purchase_value", "average_payout", "avg_order_value"])
        price = _money_label(apv) if apv else "Varies"

    key_features_text = "\n".join([
        part for part in [
            _clean(brief.get("review_summary")),
            "Positive signals: " + _clean(positives) if positives else "",
            "Common claims: " + _clean(claims) if claims else "",
            _clean(_pick(product, ["description", "summary", "keyFeatures", "key_features"]))
        ] if part
    ])

    common_complaints = "\n".join([
        part for part in [
            "Negative signals: " + _clean(negatives) if negatives else "",
            "Common complaints: " + _clean(complaints) if complaints else ""
        ] if part
    ])

    series_name = series_name_for_style(recommended_style)
    discount_info = _commission_discount(product, brief)

    normalized = {
        "productName": product_name,
        "product_name": product_name,
        "niche": niche,
        "keyFeatures": key_features_text,
        "key_features": [part.strip() for part in key_features_text.split("\n") if part.strip()],
        "price": price,
        "affiliateLink": affiliate_link,
        "affiliate_link": affiliate_link,
        "keywords": _clean(_pick(product, ["keywords", "tags"])) or ", ".join(
            [v for v in [product_name, niche, "review", "complaints", "pros and cons", "worth it", "ClickBank"] if v]
        ),
        "targetAudience": _clean(brief.get("target_audience") or brief.get("who_it_may_help")),
        "target_audience": _clean(brief.get("target_audience") or brief.get("who_it_may_help")),
        "uniqueSellingPoint": _clean((angles[0] if isinstance(angles, list) and angles else "") or brief.get("review_summary")),
        "unique_selling_point": _clean((angles[0] if isinstance(angles, list) and angles else "") or brief.get("review_summary")),
        "commonPraises": _clean(positives),
        "common_praises": _clean(positives),
        "commonComplaints": common_complaints,
        "common_complaints": common_complaints,
        "whoNotFor": _clean(brief.get("who_should_skip_it")),
        "who_not_for": _clean(brief.get("who_should_skip_it")),
        "competitors": competitors,
        "content_style": recommended_style,
        "contentStyle": recommended_style,
        "series_name": series_name,
        "seriesName": series_name,
        "discount_info": discount_info,
        "discountInfo": discount_info,
        "price_comparison": _clean(brief.get("price_comparison") or brief.get("priceComparison")),
        "priceComparison": _clean(brief.get("price_comparison") or brief.get("priceComparison")),
        "cta": _clean(brief.get("cta_guidance")),
        "reviewBrief": brief,
        "reviewSources": review_sources,
        "apfProduct": product,
    }

    return {
        "normalized": normalized,
        "recommended_content_style": recommended_style,
    }
