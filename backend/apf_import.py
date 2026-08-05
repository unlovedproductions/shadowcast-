"""APF payload normalization for ShadowCast ProductInfo."""

import json
import os
import re

from content_styles import normalize_content_style, series_name_for_style, style_requires_competitors

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
_MARKETPLACE_NICHE_RE = re.compile(
    r"(?i)^(digistore24?\s*marketplace|clickbank(\s*marketplace)?|"
    r"jvzoo|warrior\+?plus|marketplace|affiliate\s*marketplace)$"
)
_VENDOR_SLOGAN_RE = re.compile(r"(?i)^(trust us[,']?\s*|for everyone'?s benefit)")
_PRIMARY_PRICE_RE = re.compile(r"\$\s*\d{1,6}(?:[.,]\d{1,2})?")
_IMAGE_URL_RE = re.compile(
    r"https?://[^\s\"'<>]+?\.(?:jpe?g|png|webp|gif)(?:\?[^\s\"'<>]*)?",
    re.I,
)
_META_OG_IMAGE_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)["\']'
    r'|<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\']',
    re.I,
)
_IMG_SRC_RE = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.I)
_JUNK_IMAGE_HINTS = (
    "logo",
    "icon",
    "favicon",
    "sprite",
    "pixel",
    "1x1",
    "tracking",
    "badge",
    "facebook",
    "twitter",
    "linkedin",
    "pinterest",
    "whatsapp",
    "gravatar",
    "avatar",
    "placeholder",
    "spinner",
    "digistore24.com/assets",
)
_IMAGE_SOURCE_PRIORITY = {
    "sales_page": 0,
    "offer_page": 1,
    "order_page": 2,
}


def _looks_like_product_image(url: str) -> bool:
    token = (url or "").strip().lower()
    if not token.startswith("http"):
        return False
    if any(hint in token for hint in _JUNK_IMAGE_HINTS):
        return False
    if not re.search(r"\.(?:jpe?g|png|webp|gif)(?:\?|$)", token):
        # CDN paths often omit extensions — allow if clearly media-ish
        if not any(x in token for x in ("/image", "/images/", "/media/", "/cdn/", "cloudfront", "wp-content")):
            return False
    return True


def _image_urls_from_text(text: str) -> list[str]:
    if not text:
        return []
    found: list[str] = []
    for match in _IMAGE_URL_RE.findall(text):
        url = match.rstrip(").,;'\"")
        if _looks_like_product_image(url) and url not in found:
            found.append(url)
    return found


def _absolute_url(base: str, maybe_relative: str) -> str:
    from urllib.parse import urljoin

    return urljoin(base, (maybe_relative or "").strip())


def _image_urls_from_html(html: str, base_url: str = "") -> list[str]:
    if not html:
        return []
    found: list[str] = []
    for match in _META_OG_IMAGE_RE.finditer(html):
        url = _absolute_url(base_url, match.group(1) or match.group(2) or "")
        if _looks_like_product_image(url) and url not in found:
            found.append(url)
    for match in _IMG_SRC_RE.finditer(html):
        url = _absolute_url(base_url, match.group(1))
        if _looks_like_product_image(url) and url not in found:
            found.append(url)
    found.extend(u for u in _image_urls_from_text(html) if u not in found)
    return found


def _vendor_material_page_url(material: dict) -> str:
    return _clean(_pick(material, ["url", "source_url", "sourceUrl", "href", "page_url", "pageUrl"]))


def _fetch_page_html(url: str, *, timeout: float = 8.0) -> str:
    """Best-effort GET of vendor sales/offer HTML. Soft-fail → empty string."""
    if not url or not re.match(r"^https?://", url, re.I):
        return ""
    if os.getenv("SHADOWCAST_FETCH_VENDOR_IMAGES", "1").strip() in ("0", "false", "False"):
        return ""
    try:
        import httpx
    except ImportError:
        return ""
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            resp = client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; ShadowCast/1.0; +https://github.com/unlovedproductions/shadowcast-)"
                    ),
                    "Accept": "text/html,application/xhtml+xml",
                },
            )
            if resp.status_code >= 400:
                return ""
            ctype = (resp.headers.get("content-type") or "").lower()
            if "html" not in ctype and "text/" not in ctype and ctype:
                return ""
            return resp.text or ""
    except Exception:
        return ""


def _resolve_product_image_url(
    product: dict,
    vendor_materials,
    shadowcast_import: dict,
    *,
    fetch_pages: bool = True,
) -> str:
    """
    Prefer explicit image fields, then image URLs embedded in vendor materials,
    then og:image / <img> from sales/offer pages (vendor pages almost always have product photos).
    """
    explicit = _clean(
        _pick(shadowcast_import, ["image_url", "imageUrl", "product_image", "productImage", "main_image"])
        or _pick(product, [
            "image_url", "imageUrl", "image", "product_image", "productImage",
            "main_image", "mainImage", "thumbnail_url", "thumbnailUrl", "photo",
        ])
    )
    if explicit and _looks_like_product_image(explicit):
        return explicit

    materials = [m for m in (vendor_materials or []) if isinstance(m, dict)]
    materials_sorted = sorted(
        materials,
        key=lambda m: _IMAGE_SOURCE_PRIORITY.get(str(m.get("source_type") or "").lower(), 50),
    )

    # 1) Embedded URLs in excerpts / structured blocks / content
    for material in materials_sorted:
        title = _clean(material.get("title"))
        if title and _JUNK_VENDOR_TITLE_RE.match(title):
            continue
        blobs = [
            _clean(material.get("excerpt")),
            _clean(material.get("content_text") or material.get("contentText")),
            json.dumps(material.get("structured_blocks") or material.get("structuredBlocks") or {}, ensure_ascii=False),
        ]
        for blob in blobs:
            urls = _image_urls_from_text(blob)
            if urls:
                return urls[0]

    if not fetch_pages:
        return ""

    # 2) Fetch vendor sales/offer HTML for og:image / product <img>
    page_candidates: list[str] = []
    for material in materials_sorted:
        title = _clean(material.get("title"))
        if title and _JUNK_VENDOR_TITLE_RE.match(title):
            continue
        page_url = _vendor_material_page_url(material)
        if page_url and page_url not in page_candidates:
            page_candidates.append(page_url)
    for key in ("product_detail_url", "productDetailUrl", "sales_page_url", "salesPageUrl", "url"):
        extra = _clean(_pick(product, [key]))
        if extra and extra not in page_candidates and re.match(r"^https?://", extra, re.I):
            # Skip obvious marketplace hop trackers without a product path
            if "digistore24.com/redir" in extra.lower() or "clickbank.net" in extra.lower():
                continue
            page_candidates.append(extra)

    for page_url in page_candidates:
        html = _fetch_page_html(page_url)
        if not html:
            continue
        urls = _image_urls_from_html(html, base_url=page_url)
        if urls:
            return urls[0]
    return ""


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


def _sanitize_niche(value: str) -> str:
    text = _clean(value)
    if not text or _MARKETPLACE_NICHE_RE.match(text):
        return ""
    return text[:80]


def _extract_primary_price(text: str) -> str:
    match = _PRIMARY_PRICE_RE.search(_clean(text))
    if not match:
        return ""
    return _money_label(match.group(0).replace(" ", ""), fallback="")


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

    # Long buyer copy like "$49.95 per box … $134.25 bundle" → keep first retail amount.
    # Do not treat "save $15" / discount slogans as retail price.
    if text and not looks_affiliate:
        discountish = bool(
            re.search(r"(?i)\b(save|off|discount|you.?ll save)\b", text)
            and not re.search(r"(?i)\b(per\s+box|bundle|purchase|retail|single)\b", text)
        )
        if not discountish:
            primary = _extract_primary_price(text)
            if primary:
                return primary

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
    if _VENDOR_SLOGAN_RE.search(lowered):
        return True
    if "don't bid on" in lowered or "do not bid on" in lowered:
        return True
    return any(marker in lowered for marker in _AFFILIATE_META_MARKERS)


def _buyer_trust_text(items) -> str:
    lines = []
    for item in items or []:
        line = _clean(item)
        if line and not _is_affiliate_meta_line(line):
            lines.append(line)
    return "\n".join(lines)


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
    niche = _sanitize_niche(
        _clean(_pick(shadowcast_import, ["niche", "product_category", "productCategory"]))
        or _clean(_pick(product, ["niche", "product_category", "productCategory", "category"]))
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
    # Never invent USP from angles / review_summary (titles and slogans ≠ selling point).
    usp = _clean(_pick(shadowcast_import, ["unique_selling_point", "uniqueSellingPoint"]))
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

    image_url = _resolve_product_image_url(product, vendor_materials, shadowcast_import)

    normalized = {
        "productName": product_name,
        "product_name": product_name,
        "niche": niche,
        "keyFeatures": key_features_joined,
        "key_features": key_features_list,
        "price": price,
        "affiliateLink": affiliate_link,
        "affiliate_link": affiliate_link,
        "image_url": image_url,
        "imageUrl": image_url,
        "keywords": keywords,
        "targetAudience": target_audience,
        "target_audience": target_audience,
        "uniqueSellingPoint": usp,
        "unique_selling_point": usp,
        "commonPraises": _buyer_trust_text(positives),
        "common_praises": _buyer_trust_text(positives),
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


_TRUST_SIGNAL_STYLES = frozenset({"honest_review", "elimination", "worth_it_or_waste"})
_WEAK_PRICE_VALUES = frozenset({"", "varies", "see official offer page", "n/a", "na", "tbd"})
_PLACEHOLDER_AFFILIATE = frozenset({"", "[your_affiliate_link]", "your_affiliate_link", "n/a", "na"})

_SNAKE_PRODUCT_KEYS = (
    "product_name",
    "niche",
    "key_features",
    "price",
    "affiliate_link",
    "keywords",
    "target_audience",
    "product_category",
    "competitors",
    "unique_selling_point",
    "discount_info",
    "coupon_code",
    "common_complaints",
    "common_praises",
    "who_not_for",
    "series_name",
    "price_comparison",
    "content_style",
    "amazon_url",
    "image_url",
    "cta",
)


def as_snake_product_info(normalized: dict) -> dict:
    """Canonical ProductInfo-shaped dict (snake_case only) from APF normalize output."""
    if not isinstance(normalized, dict):
        return {}
    out = {}
    aliases = {
        "product_name": ("product_name", "productName"),
        "niche": ("niche",),
        "key_features": ("key_features", "keyFeatures"),
        "price": ("price",),
        "affiliate_link": ("affiliate_link", "affiliateLink"),
        "keywords": ("keywords",),
        "target_audience": ("target_audience", "targetAudience"),
        "product_category": ("product_category", "productCategory", "niche"),
        "competitors": ("competitors",),
        "unique_selling_point": ("unique_selling_point", "uniqueSellingPoint"),
        "discount_info": ("discount_info", "discountInfo"),
        "coupon_code": ("coupon_code", "couponCode"),
        "common_complaints": ("common_complaints", "commonComplaints"),
        "common_praises": ("common_praises", "commonPraises"),
        "who_not_for": ("who_not_for", "whoNotFor"),
        "series_name": ("series_name", "seriesName"),
        "price_comparison": ("price_comparison", "priceComparison"),
        "content_style": ("content_style", "contentStyle"),
        "amazon_url": ("amazon_url", "amazonUrl"),
        "image_url": (
            "image_url",
            "imageUrl",
            "image",
            "product_image",
            "productImage",
            "main_image",
            "mainImage",
            "thumbnail_url",
            "thumbnailUrl",
        ),
        "cta": ("cta",),
    }
    for key in _SNAKE_PRODUCT_KEYS:
        for src in aliases.get(key, (key,)):
            if src in normalized and normalized[src] not in (None,):
                out[key] = normalized[src]
                break
        else:
            out[key] = [] if key in ("key_features", "keywords", "competitors") else ""
    if isinstance(out.get("key_features"), str):
        text = out["key_features"].strip()
        out["key_features"] = [line.strip() for line in text.split("\n") if line.strip()] if text else []
    if isinstance(out.get("keywords"), str):
        out["keywords"] = [k.strip() for k in re.split(r"[,;]", out["keywords"]) if k.strip()]
    if isinstance(out.get("competitors"), str):
        out["competitors"] = [c.strip() for c in re.split(r"[,;]", out["competitors"]) if c.strip()]
    out["content_style"] = normalize_content_style(out.get("content_style") or "honest_review")
    if not out.get("product_category"):
        out["product_category"] = out.get("niche") or "General"
    return out


def _field_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return not str(value).strip()


def assess_product_completeness(product: dict, content_style: str | None = None) -> dict:
    """Return blocking gaps and warnings for generate/import readiness."""
    info = as_snake_product_info(product)
    for k in _SNAKE_PRODUCT_KEYS:
        if k in product and product[k] not in (None,):
            info[k] = product[k]

    style = normalize_content_style(
        content_style or info.get("content_style") or product.get("content_style") or "honest_review"
    )
    blocking: list[str] = []
    warnings: list[str] = []

    name = str(info.get("product_name") or product.get("productName") or "").strip()
    if not name:
        blocking.append("product_name")

    price = str(info.get("price") or "").strip()
    if price.lower() in _WEAK_PRICE_VALUES:
        warnings.append("price")

    affiliate = str(info.get("affiliate_link") or "").strip()
    if affiliate.lower() in _PLACEHOLDER_AFFILIATE:
        warnings.append("affiliate_link")

    praises = info.get("common_praises") or ""
    complaints = info.get("common_complaints") or ""
    if style in _TRUST_SIGNAL_STYLES and _field_blank(praises) and _field_blank(complaints):
        warnings.append("common_praises_or_common_complaints")

    if style_requires_competitors(style) and _field_blank(info.get("competitors")):
        warnings.append("competitors")

    strict = os.getenv("SHADOWCAST_STRICT_PRODUCT_GATE", "").lower() in ("1", "true", "yes")
    if strict:
        promoted = []
        for field in list(warnings):
            if field in ("common_praises_or_common_complaints", "affiliate_link"):
                warnings.remove(field)
                promoted.append(field)
        blocking.extend(promoted)

    return {
        "blocking": blocking,
        "warnings": warnings,
        "content_style": style,
        "product_name": name,
    }


def dedupe_products_by_name(products: list) -> tuple[list, list[str]]:
    """Keep last occurrence per sanitized product name. Returns (deduped, dropped_names)."""
    by_key: dict[str, dict] = {}
    order: list[str] = []
    dropped: list[str] = []
    for raw in products:
        if not isinstance(raw, dict):
            continue
        info = as_snake_product_info(raw)
        name = str(info.get("product_name") or raw.get("product_name") or raw.get("productName") or "").strip()
        if not name:
            continue
        key = _sanitize_product_name(name).lower() or name.lower()
        if key in by_key:
            dropped.append(name)
        else:
            order.append(key)
        merged = {**info, **{k: raw[k] for k in raw if k in _SNAKE_PRODUCT_KEYS}}
        merged["product_name"] = name
        by_key[key] = merged
    return [by_key[k] for k in order if k in by_key], dropped

