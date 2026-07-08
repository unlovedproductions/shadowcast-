import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from apf_import import normalize_apf_payload


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
    assert "Affiliate commission" in normalized["discountInfo"]
    assert normalized["seriesName"] == "VS Battle"


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
