import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from apf_import import (
    as_snake_product_info,
    assess_product_completeness,
    dedupe_products_by_name,
    extract_apf_product_payloads,
    normalize_apf_payload,
)


def test_maps_review_brief_fields():
    payload = {
        "product": {
            "name": "Fat Burn Pro",
            "category": "Health",
            "vendor": "VendorX",
            "affiliate_url": "https://example.com/hop",
            "commission_rate": "75",
        },
        "review_brief": {
            "recommended_content_style": "vs_battle",
            "suggested_competitors": ["Competitor A", "VendorX", "Competitor B"],
            "price_display": "$67.00",
            "positive_signals": ["Strong niche fit"],
            "best_video_angles": ["Honest pros and cons breakdown"],
            "target_audience": "Adults researching weight loss supplements",
        },
    }

    result = normalize_apf_payload(payload)
    normalized = result["normalized"]

    assert result["recommended_content_style"] == "vs_battle"
    assert normalized["productName"] == "Fat Burn Pro"
    assert normalized["price"] == "$67.00"
    assert normalized["competitors"] == ["Competitor A", "Competitor B"]
    assert normalized["content_style"] == "vs_battle"
    assert "Affiliate commission" not in normalized["discountInfo"]
    assert normalized["discountInfo"] == ""
    assert normalized["seriesName"] == "VS Battle"


def test_sanitize_polluted_affiliate_product_title():
    payload = {
        "product": {
            "name": "Earn 60% Commission Promoting Advanced Amino Formula Supplements - health",
            "category": "Health",
            "commission_rate": "60",
        },
        "review_brief": {
            "recommended_content_style": "honest_review",
            "common_claims": ["Supports recovery and daily amino intake"],
            "positive_signals": ["Users report easier post-workout recovery"],
        },
    }

    normalized = normalize_apf_payload(payload)["normalized"]
    assert normalized["productName"] == "Advanced Amino Formula Supplements"
    assert "commission" not in normalized["discountInfo"].lower()
    assert all("commission rate" not in feature.lower() for feature in normalized["key_features"])


def test_buyer_discount_uses_coupon_not_commission():
    payload = {
        "product": {
            "name": "Clean Product",
            "coupon_code": "SAVE10",
        },
        "review_brief": {
            "discount_info": "10% off launch sale",
            "commission_rate": "75",
        },
    }
    normalized = normalize_apf_payload(payload)["normalized"]
    assert "Affiliate commission" not in normalized["discountInfo"]
    assert "10% off launch sale" in normalized["discountInfo"]
    assert "Coupon: SAVE10" in normalized["discountInfo"]


def test_price_fallback_to_apv_then_varies():
    payload = {
        "product": {
            "name": "Mystery Offer",
            "apv": "89.5",
        },
        "review_brief": {},
    }
    normalized = normalize_apf_payload(payload)["normalized"]
    assert normalized["price"] == "$89.50"

    empty_price = normalize_apf_payload({"product": {"name": "No Price"}})["normalized"]
    assert empty_price["price"] == "Varies"


def test_style_inference_from_angles():
    payload = {
        "product": {"name": "Budget Gadget"},
        "review_brief": {
            "best_video_angles": ["Best budget pick under $50"],
        },
    }
    assert normalize_apf_payload(payload)["recommended_content_style"] == "budget_challenge"


def test_shadowcast_import_style_from_enriched_brief():
    """Enriched APF export fields flow through normalization."""
    payload = {
        "product": {"name": "Test Offer", "vendor": "VendorCo", "category": "Health"},
        "review_brief": {
            "recommended_content_style": "elimination",
            "suggested_competitors": ["Alt A", "Alt B"],
            "price_display": "$47.00",
            "best_video_angles": ["Skip these and pick the winner"],
        },
    }
    result = normalize_apf_payload(payload)
    assert result["recommended_content_style"] == "elimination"
    assert result["normalized"]["competitors"] == ["Alt A", "Alt B"]
    assert result["normalized"]["price"] == "$47.00"


def test_extract_apf_product_payloads_batch():
    payloads = extract_apf_product_payloads({
        "batch": True,
        "products": [
            {"product": {"name": "One"}, "review_brief": {}},
            {"product": {"name": "Two"}, "review_brief": {}},
        ],
    })
    assert len(payloads) == 2
    assert payloads[0]["product"]["name"] == "One"

    single = extract_apf_product_payloads({"product": {"name": "Solo"}})
    assert len(single) == 1
    assert single[0]["product"]["name"] == "Solo"


def test_digistore_recovers_name_and_sanitizes_price_from_vendor_materials():
    payload = {
        "product": {
            "name": "Digistore24",
            "category": "Digistore24 Marketplace",
            "platform_product_id": "54669",
            "affiliate_url": "https://www.digistore24-app.com/app/en/affiliate/account/marketplace/all/detail/54669",
            "description": (
                "Dashboard Marketplace Analytics Sales & partners Reports Settings Homepage "
                "About Digistore24 JobsContact FAQCustomers Privacy policy"
            ),
        },
        "review_brief": {
            "recommended_content_style": "vs_battle",
            "price_display": (
                "Joseph's Well Our Affiliates Are Seeing 5%+ Conversion Rates "
                "& Over $2 EPCs On ICE COLD Traffic!"
            ),
            "review_summary": "Trust us, it's for everyone's benefit.",
            "positive_signals": [
                'So don\'t bid on "Joseph\'s Well", "Joseph\'s Well review" or anything similar.',
            ],
            "common_claims": ["Trust us, it's for everyone's benefit."],
            "suggested_competitors": [
                "Top Digistore24 Marketplace alternative",
                "Popular Digistore24 Marketplace competitor",
            ],
        },
        "vendor_materials": [
            {
                "source_type": "sales_page",
                "title": "Compliance Guidelines (Read Before Launch)",
            },
            {
                "source_type": "order_page",
                "title": "Joseph's Well",
            },
            {
                "source_type": "offer_page",
                "title": "Joseph's Well – Blockbuster Offer From Top Diamond Vendor Book (printed)",
            },
        ],
        "shadowcast_import": {
            "product_name": "Digistore24",
            "price": (
                "Joseph's Well Our Affiliates Are Seeing 5%+ Conversion Rates "
                "& Over $2 EPCs On ICE COLD Traffic!"
            ),
            "key_features": [
                "Trust us, it's for everyone's benefit.",
                'Keyword Caution: Don\'t bid on keywords that include our brand name, "Joseph\'s Well".',
            ],
            "competitors": [
                "Top Digistore24 Marketplace alternative",
                "Popular Digistore24 Marketplace competitor",
            ],
            "content_style": "vs_battle",
        },
    }

    result = normalize_apf_payload(payload)
    normalized = result["normalized"]

    assert normalized["productName"].startswith("Joseph")
    assert "Well" in normalized["productName"]
    assert normalized["price"] == "See official offer page"
    assert "EPC" not in normalized["price"]
    assert "Dashboard Marketplace" not in normalized["keyFeatures"]
    assert all("don't bid" not in f.lower() for f in normalized["key_features"])
    assert normalized["competitors"] == []


def test_digistore_commission_title_in_vendor_materials():
    payload = {
        "product": {
            "name": "Digistore24",
            "platform_product_id": "47238",
        },
        "review_brief": {
            "price_display": "You’ll save $15.",
        },
        "vendor_materials": [
            {"source_type": "sales_page", "title": "Compliance Guidelines (Read Before Launch)"},
            {
                "source_type": "offer_page",
                "title": "Earn 60% Commission Promoting CircO2 Nitric Oxide Booster Supplements - health",
            },
        ],
    }
    normalized = normalize_apf_payload(payload)["normalized"]
    assert normalized["productName"] == "CircO2 Nitric Oxide Booster Supplements"
    assert normalized["price"] == "See official offer page"


def test_fill_pipeline_rejects_marketplace_niche_and_junk_usp():
    payload = {
        "product": {
            "name": "Earn 60% Commission Promoting CircO2 Nitric Oxide Booster Supplements - health",
            "category": "Digistore24 Marketplace",
        },
        "review_brief": {
            "price_display": (
                "$49.95 per box (single purchase) - $134.25 for a bundle with multiple boxes"
            ),
            "review_summary": "Trust us, it's for everyone's benefit.",
            "best_video_angles": [
                "CircO2 Nitric Oxide Booster Supplements Review; Boost Your Energy and Health with CircO2"
            ],
            "positive_signals": [
                "Nitric oxide levels increase significantly within minutes of use.",
                'So don\'t bid on "CircO2" brand keywords.',
            ],
            "common_claims": ["Trust us, it's for everyone's benefit."],
        },
    }
    normalized = normalize_apf_payload(payload)["normalized"]
    assert normalized["productName"] == "CircO2 Nitric Oxide Booster Supplements"
    assert normalized["niche"] == ""
    assert normalized["price"] == "$49.95"
    assert normalized["uniqueSellingPoint"] == ""
    assert "Trust us" not in (normalized.get("commonPraises") or "")
    assert "don't bid" not in (normalized.get("commonPraises") or "").lower()
    assert "digistore24 marketplace" not in (normalized.get("keywords") or "").lower()


def test_youtube_research_does_not_fill_usp():
    from research_enrichment import _merge_youtube_research

    product = {"product_name": "CircO2", "unique_selling_point": ""}
    out = _merge_youtube_research(
        product,
        {"recommended_tags": ["nitric oxide"], "recommended_titles": ["CircO2 Review 2026"]},
    )
    assert out["keywords"] == ["nitric oxide"]
    assert not out.get("unique_selling_point")
    assert out["_youtube_research"]["recommended_titles"][0].startswith("CircO2")


def test_enrichment_skips_yt_when_keywords_present(monkeypatch):
    from research_enrichment import enrich_product_research

    called = {"yt": False}

    async def _boom(_query):
        called["yt"] = True
        return {"recommended_tags": ["should-not-run"]}

    monkeypatch.setattr("research_enrichment.research_youtube_keywords", _boom)
    out = enrich_product_research(
        {"product_name": "Widget", "keywords": ["already", "set"], "unique_selling_point": ""},
        research_dir=None,
    )
    assert called["yt"] is False
    assert out["keywords"] == ["already", "set"]


def test_enrichment_records_warning_when_amazon_fails(monkeypatch):
    from research_enrichment import enrich_product_research

    async def _fail(_url):
        return {"error": "timeout"}

    async def _yt(_query):
        return {"recommended_tags": ["tag1"], "recommended_titles": ["Title"]}

    monkeypatch.setattr("research_enrichment.scrape_amazon_product", _fail)
    monkeypatch.setattr("research_enrichment.research_youtube_keywords", _yt)
    out = enrich_product_research(
        {"product_name": "Widget", "amazon_url": "https://amazon.com/dp/B000", "keywords": []},
        research_dir=None,
    )
    assert any("Amazon scrape failed" in w for w in out.get("_research_warnings", []))
    assert out.get("keywords") == ["tag1"]


def test_as_snake_product_info_drops_dual_schema_noise():
    payload = {
        "product": {
            "name": "Clean Offer",
            "affiliate_url": "https://example.com/hop",
        },
        "review_brief": {
            "price_display": "$19.00",
            "positive_signals": ["Works"],
            "recommended_content_style": "honest_review",
        },
    }
    normalized = normalize_apf_payload(payload)["normalized"]
    snake = as_snake_product_info(normalized)
    assert "productName" not in snake
    assert snake["product_name"] == "Clean Offer"
    assert snake["affiliate_link"] == "https://example.com/hop"
    assert snake["price"] == "$19.00"


def test_assess_completeness_warns_on_thin_trust_product():
    assessment = assess_product_completeness(
        {
            "product_name": "Thin Product",
            "content_style": "honest_review",
            "price": "Varies",
            "affiliate_link": "[YOUR_AFFILIATE_LINK]",
        }
    )
    assert assessment["blocking"] == []
    assert "common_praises_or_common_complaints" in assessment["warnings"]
    assert "price" in assessment["warnings"]
    assert "affiliate_link" in assessment["warnings"]


def test_dedupe_products_by_name_keeps_last():
    products, dropped = dedupe_products_by_name(
        [
            {"product_name": "Same Thing", "price": "$1"},
            {"product_name": "Same Thing", "price": "$2"},
            {"product_name": "Other", "price": "$3"},
        ]
    )
    assert len(products) == 2
    assert len(dropped) == 1
    same = next(p for p in products if p["product_name"] == "Same Thing")
    assert same["price"] == "$2"
