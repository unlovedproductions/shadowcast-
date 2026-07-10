import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from apf_import import extract_apf_product_payloads, normalize_apf_payload


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
