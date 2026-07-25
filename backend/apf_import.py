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

_COMMISSION_PROMOTING_RE = re.compile(
    r"(?i)^earn\s+\d+%?\s*commission\s+promoting\s+(.+?)(?:\s+-\s+\w+)?$"
)
_JUNK_VENDOR_TITLE_RE = re.compile(
    r"(?i)^(compliance guidelines|banners|faq|privacy policy|terms|legal notice|homepage|dashboard|settings|reports)$"
)
_AFFILIATE_PRICE_MARKERS = (
    "epc",
    "commission",
    "conversion rate",
    "affiliates are seeing",
    "avg payout",
    "per sale",
    "/sale",
)
_SOURCE_TYPE_PRIORITY = {
    "offer_page": 0,
    "order_page": 1,
    "sales_page": 2,
}
_DIGISTORE_CHROME_RE = re.compile(
    r"(?i)dashboard\s+marketplace\s+analytics|skip to content digistore"
)


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
    except (TypeError, ValueError):
        text = _clean(value)
        return text or fallback
    return f"${number:.2f}"


def _infer_style_from_angles(angles):
    text = " ".join(_clean(a).lower() for a in (angles or []))
    for patterns, style in STYLE_FROM_ANGLE:
        if any(pattern in text for pattern in patterns):
            return style
    return "honest_review"


_AFFILIATE_META_MARKERS = (
    "commission rate",
    "affiliate opportunity",
    "earn significant income promoting",
    "hop conversion",
    "epc signal",
    "marketplace rank",
    "hidden gem score",
    "check your transactions",
    "generate discount codes",
    "lucrative for affiliates",
    "promoting this",
)


def _sanitize_product_name(name: str) -> str:
    text = _clean(name)
    if not text:
        return ""

    text = re.sub(
        r"(?i)^earn\s+\d+%?\s*commission\s+promoting\s+",
        "",
        text,
    )
    text = re.sub(
        r"(?i)\s*-\s*(health|fitness|digistore\d*|clickbank|marketplace|supplements?)\s*$",
        "",
        text,
    )
    text = re.sub(r"(?i)\s*\(?\d+%\s+commission\)?", "", text)
    text = re.sub(r"(?i)\s*affiliate\s+offer", "", text)
    text = re.sub(r"\s{2,}", " ", text).strip(" -:|")

    if not text:
        fallback = _clean(name).split(" - ")[0].split(" | ")[0]
        return fallback[:120]
    return text[:120]


def _is_marketplace_brand_name(name: str) -> bool:
    return bool(re.match(r"(?i)^(digistore24?|marketplace)$", _clean(name)))


def _is_junk_vendor_title(title: str) -> bool:
    text = _clean(title)
    if not text:
        return True
    if _is_marketplace_brand_name(text):
        return True
    if _JUNK_VENDOR_TITLE_RE.match(text):
        return True
    if re.search(r"(?i)compliance guidelines", text):
        return True
    return False


def _candidate_from_vendor_title(title: str) -> str:
    raw = _clean(title)
    if not raw:
        return ""
    match = _COMMISSION_PROMOTING_RE.match(raw)
    if match:
        return _sanitize_product_name(match.group(1))
    if _is_junk_vendor_title(raw):
        return ""
    return _sanitize_product_name(raw)


def _resolve_product_name(product: dict, vendor_materials, shadowcast_import: dict) -> str:
    candidates = [
        _clean(_pick(shadowcast_import, ["product_name", "productName", "name"])),
        _clean(_pick(product, ["name", "product_name", "productName", "title"])),
    ]
    for candidate in candidates:
        sanitized = _sanitize_product_name(candidate) or candidate
        if sanitized and not _is_marketplace_brand_name(sanitized):
            return sanitized[:120]

    materials = list(vendor_materials or [])
    for material in materials:
        if not isinstance(material, dict):
            continue
        raw = _clean(material.get("title"))
        match = _COMMISSION_PROMOTING_RE.match(raw)
        if not match:
            continue
        sanitized = _sanitize_product_name(match.group(1))
        if sanitized and not _is_marketplace_brand_name(sanitized):
            return sanitized[:120]

    materials.sort(
        key=lambda m: _SOURCE_TYPE_PRIORITY.get(
            _clean((m or {}).get("source_type")).lower(), 9
        )
        if isinstance(m, dict)
        else 9
    )
    for material in materials:
        if not isinstance(material, dict):
            continue
        candidate = _candidate_from_vendor_title(material.get("title"))
        if candidate and not _is_marketplace_brand_name(candidate):
            return candidate[:120]

    platform_id = _clean(
        _pick(product, ["platform_product_id", "platformProductId", "source_product_id"])
    )
    return f"Digistore24 Product {platform_id or 'unknown'}"[:120]


def _sanitize_buyer_price(value, cart_value=None, fallback="See official offer page") -> str:
    text = _clean(value)
    lowered = text.lower()
    looks_affiliate = any(marker in lowered for marker in _AFFILIATE_PRICE_MARKERS)
    sentence_count = len(re.findall(r"[.!?]", text))
    looks_marketing = len(text) > 40 or sentence_count > 0

    is_short_buyer_price = bool(
        re.match(
            r"(?i)^(free|varies|see official offer page|\$?\d{1,6}(?:[.,]\d{1,2})?(?:\s*(?:usd|eur|gbp))?)$",
            text,
        )
        or re.match(r"(?i)^from\s+\$?\d{1,6}(?:[.,]\d{1,2})?$", text)
        or re.match(
            r"(?i)^\$?\d{1,6}(?:[.,]\d{1,2})?\s*[-–]\s*\$?\d{1,6}(?:[.,]\d{1,2})?$",
            text,
        )
    )

    if text and is_short_buyer_price and not looks_affiliate:
        if re.match(r"^\d", text) and not text.startswith("$"):
            try:
                return f"${float(text.replace(',', '.')):.2f}"
            except ValueError:
                return text
        return text

    if text and not looks_affiliate and not looks_marketing and len(text) <= 40:
        return text

    try:
        cart = float(cart_value)
    except (TypeError, ValueError):
        cart = None
    if cart is not None and cart > 0:
        return f"${cart:.2f}"

    return fallback


def _buyer_discount_info(product, brief, shadowcast_import=None):
    """Buyer-facing discounts only — never affiliate commission."""
    sc = shadowcast_import if isinstance(shadowcast_import, dict) else {}
    coupon = _clean(
        sc.get("coupon_code")
        or sc.get("couponCode")
        or brief.get("coupon_code")
        or brief.get("couponCode")
        or _pick(product, ["coupon_code", "couponCode"])
    )
    discount = _clean(
        sc.get("discount_info")
        or sc.get("discountInfo")
        or brief.get("discount_info")
        or brief.get("discountInfo")
        or brief.get("price_discount")
        or _pick(product, ["discount_info", "discountInfo", "sale_price_note"])
    )
    lowered = discount.lower()
    if discount and ("commission" in lowered or "affiliate" in lowered or "epc" in lowered):
        discount = ""

    parts = [part for part in (discount, f"Coupon: {coupon}" if coupon else "") if part]
    return "; ".join(parts)


def _is_affiliate_meta_line(text: str) -> bool:
    lowered = _clean(text).lower()
    if not lowered:
        return True
    if _DIGISTORE_CHROME_RE.search(lowered):
        return True
    if "don't bid on" in lowered or "do not bid on" in lowered:
        return True
    return any(marker in lowered for marker in _AFFILIATE_META_MARKERS)


def _buyer_key_features(brief, product, key_features_text: str, shadowcast_import=None) -> list:
    sc = shadowcast_import if isinstance(shadowcast_import, dict) else {}
    cleaned = []

    sc_features = sc.get("key_features") or sc.get("keyFeatures") or []
    if isinstance(sc_features, str):
        sc_features = [part.strip() for part in sc_features.split("\n") if part.strip()]
    for item in sc_features:
        line = _clean(item)
        if line and not _is_affiliate_meta_line(line):
            cleaned.append(line)

    if cleaned:
        return cleaned[:8]

    lines = [part.strip() for part in key_features_text.split("\n") if part.strip()]
    for line in lines:
        if _is_affiliate_meta_line(line):
            continue
        if line.startswith("Positive signals:") or line.startswith("Common claims:"):
            continue
        cleaned.append(line)

    if cleaned:
        return cleaned[:8]

    claims = brief.get("common_claims") or []
    positives = brief.get("positive_signals") or []
    for item in list(claims) + list(positives):
        line = _clean(item)
        if line and not _is_affiliate_meta_line(line):
            cleaned.append(line)

    description = _clean(_pick(product, ["description", "summary"]))
    if description and not _is_affiliate_meta_line(description):
        cleaned.append(description)

    return cleaned[:8]


def _filter_competitors(candidates, vendor):
    vendor_clean = _clean(vendor).lower()
    result = []
    for item in candidates or []:
        name = _clean(item)
        if not name:
            continue
        if vendor_clean and name.lower() == vendor_clean:
            continue
        if re.match(r"(?i)^(top|popular|budget)\s+.+\s+(alternative|competitor|option)$", name):
            continue
        if name not in result:
            result.append(name)
    return result


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    text = _clean(value)
    if not text:
        return []
    return [part.strip() for part in re.split(r"[\n;]", text) if part.strip()]


def extract_apf_product_payloads(payload) -> list:
    """Return a list of single-product APF payloads from single or batch input."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, (dict, list))]
    if not isinstance(payload, dict):
        return []
    if payload.get("batch") and isinstance(payload.get("products"), list):
        return [item for item in payload["products"] if isinstance(item, (dict, list))]
    if isinstance(payload.get("products"), list) and payload.get("products") and all(
        isinstance(item, dict) and (
            "product" in item or "review_brief" in item or "shadowcast_import" in item
            or "schema_version" in item
        )
        for item in payload["products"]
    ):
        return list(payload["products"])
    return [payload]


def normalize_apf_payload(payload: dict) -> dict:
    """Return normalized ProductInfo fields and recommended_content_style."""
    raw = payload.get("payload") if isinstance(payload, dict) and isinstance(payload.get("payload"), dict) else payload
    product = _first_product(raw)

    brief = {}
    shadowcast_import = {}
    vendor_materials = []
    if isinstance(raw, dict):
        brief = raw.get("review_brief") or raw.get("reviewBrief") or {}
        shadowcast_import = raw.get("shadowcast_import") or raw.get("shadowcastImport") or {}
        vendor_materials = raw.get("vendor_materials") or raw.get("vendorMaterials") or []
    if not isinstance(brief, dict):
        brief = {}
    if not isinstance(shadowcast_import, dict):
        shadowcast_import = {}
    if not isinstance(vendor_materials, list):
        vendor_materials = []

    review_sources = []
    if isinstance(raw, dict) and isinstance(raw.get("review_sources"), list):
        review_sources = raw["review_sources"]

    product_name = _resolve_product_name(product, vendor_materials, shadowcast_import)
    vendor = _clean(
        _pick(shadowcast_import, ["vendor"])
        or _pick(product, ["vendor", "vendor_name", "seller", "brand"])
    )
    niche = (
        _clean(_pick(shadowcast_import, ["niche", "product_category", "productCategory"]))
        or _clean(_pick(product, ["category", "niche", "product_category"]))
        or "ClickBank"
    )
    affiliate_link = _clean(
        _pick(shadowcast_import, ["affiliate_link", "affiliateLink"])
        or _pick(product, [
            "affiliate_url", "affiliateLink", "affiliate_link", "hoplink", "product_url", "url"
        ])
    )

    positives = (
        _as_list(shadowcast_import.get("common_praises") or shadowcast_import.get("commonPraises"))
        or brief.get("positive_signals")
        or []
    )
    negatives = brief.get("negative_signals") or []
    claims = brief.get("common_claims") or []
    complaints = (
        _as_list(shadowcast_import.get("common_complaints") or shadowcast_import.get("commonComplaints"))
        or brief.get("common_complaints")
        or []
    )
    angles = brief.get("best_video_angles") or []

    recommended_style = normalize_content_style(
        shadowcast_import.get("content_style")
        or shadowcast_import.get("contentStyle")
        or brief.get("recommended_content_style")
        or brief.get("recommendedContentStyle")
        or _infer_style_from_angles(angles)
    )

    suggested = (
        shadowcast_import.get("competitors")
        or brief.get("suggested_competitors")
        or brief.get("suggestedCompetitors")
        or []
    )
    if isinstance(suggested, str):
        suggested = [s.strip() for s in re.split(r"[,;]", suggested) if s.strip()]
    competitors = _filter_competitors(suggested, vendor)

    raw_price = (
        _clean(_pick(shadowcast_import, ["price"]))
        or _clean(brief.get("price_display") or brief.get("priceDisplay"))
    )
    apv = _pick(product, ["apv", "average_purchase_value", "average_payout", "avg_order_value", "cart_value", "cartValue"])
    if raw_price:
        price = _sanitize_buyer_price(raw_price, apv, fallback="See official offer page")
    elif apv:
        price = _sanitize_buyer_price("", apv, fallback="Varies")
        if price == "See official offer page":
            price = _money_label(apv, fallback="Varies")
    else:
        price = "Varies"

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

    series_name = (
        _clean(_pick(shadowcast_import, ["series_name", "seriesName"]))
        or series_name_for_style(recommended_style)
    )
    discount_info = _buyer_discount_info(product, brief, shadowcast_import)
    key_features_list = _buyer_key_features(brief, product, key_features_text, shadowcast_import)
    key_features_joined = "\n".join(key_features_list)

    target_audience = _clean(
        _pick(shadowcast_import, ["target_audience", "targetAudience"])
        or brief.get("target_audience")
        or brief.get("who_it_may_help")
    )
    usp = _clean(
        _pick(shadowcast_import, ["unique_selling_point", "uniqueSellingPoint"])
        or (angles[0] if isinstance(angles, list) and angles else "")
        or brief.get("review_summary")
    )
    who_not_for = _clean(
        _pick(shadowcast_import, ["who_not_for", "whoNotFor"])
        or brief.get("who_should_skip_it")
    )
    keywords = _clean(_pick(shadowcast_import, ["keywords"])) or _clean(
        _pick(product, ["keywords", "tags"])
    ) or ", ".join(
        [v for v in [product_name, niche, "review", "pros and cons", "worth it", "before you buy"] if v]
    )
    if isinstance(shadowcast_import.get("keywords"), list):
        keywords = ", ".join(
            [_clean(k) for k in shadowcast_import.get("keywords") if _clean(k)]
        ) or keywords

    price_comparison = _clean(
        _pick(shadowcast_import, ["price_comparison", "priceComparison"])
        or brief.get("price_comparison")
        or brief.get("priceComparison")
    )

    normalized = {
        "productName": product_name,
        "product_name": product_name,
        "niche": niche,
        "keyFeatures": key_features_joined,
        "key_features": key_features_list,
        "price": price,
        "affiliateLink": affiliate_link,
        "affiliate_link": affiliate_link,
        "keywords": keywords,
        "targetAudience": target_audience,
        "target_audience": target_audience,
        "uniqueSellingPoint": usp,
        "unique_selling_point": usp,
        "commonPraises": _clean(positives),
        "common_praises": _clean(positives),
        "commonComplaints": common_complaints,
        "common_complaints": common_complaints,
        "whoNotFor": who_not_for,
        "who_not_for": who_not_for,
        "competitors": competitors,
        "content_style": recommended_style,
        "contentStyle": recommended_style,
        "series_name": series_name,
        "seriesName": series_name,
        "discount_info": discount_info,
        "discountInfo": discount_info,
        "price_comparison": price_comparison,
        "priceComparison": price_comparison,
        "cta": _clean(
            _pick(shadowcast_import, ["buyer_cta", "cta"])
            or brief.get("cta_guidance")
        ),
        "reviewBrief": brief,
        "reviewSources": review_sources,
        "apfProduct": product,
    }

    return {
        "normalized": normalized,
        "recommended_content_style": recommended_style,
    }
