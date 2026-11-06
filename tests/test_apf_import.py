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


def test_image_url_from_vendor_material_excerpt():
    payload = {
        "product": {"name": "Glow Serum", "affiliate_url": "https://example.com/hop"},
        "vendor_materials": [
            {
                "source_type": "sales_page",
                "title": "Glow Serum Official",
                "url": "https://vendor.example.com/glow",
                "excerpt": "See the bottle https://cdn.example.com/products/glow-serum.jpg on the page.",
            }
        ],
    }
    normalized = normalize_apf_payload(payload)["normalized"]
    assert normalized["image_url"] == "https://cdn.example.com/products/glow-serum.jpg"


def test_image_url_from_sales_page_og_image(monkeypatch):
    html = """
    <html><head>
      <meta property="og:image" content="https://cdn.example.com/media/product-hero.png"/>
    </head><body><img src="/logo.png"/></body></html>
    """

    def fake_fetch(url, timeout=8.0):
        assert "vendor.example.com" in url
        return html

    monkeypatch.setattr("apf_import._fetch_page_html", fake_fetch)
    payload = {
        "product": {"name": "Hero Bottle"},
        "vendor_materials": [
            {
                "source_type": "sales_page",
                "title": "Hero Bottle Offer",
                "url": "https://vendor.example.com/hero",
            }
        ],
    }
    normalized = normalize_apf_payload(payload)["normalized"]
    assert normalized["image_url"] == "https://cdn.example.com/media/product-hero.png"


def test_explicit_image_url_wins_over_vendor_page(monkeypatch):
    monkeypatch.setattr(
        "apf_import._fetch_page_html",
        lambda *a, **k: '<meta property="og:image" content="https://cdn.example.com/wrong.jpg"/>',
    )
    payload = {
        "product": {
            "name": "Explicit",
            "image_url": "https://cdn.example.com/products/explicit.webp",
        },
        "vendor_materials": [
            {"source_type": "sales_page", "title": "Offer", "url": "https://vendor.example.com/x"}
        ],
    }
    normalized = normalize_apf_payload(payload)["normalized"]
    assert normalized["image_url"] == "https://cdn.example.com/products/explicit.webp"


def test_digistore_skips_compliance_coda_and_picks_bottle(monkeypatch):
    """Mislabeled Digistore compliance 'sales_page' must not beat real order-page bottle art."""
    pages = {
        "https://vendor.example.com/compliance": """
            <html><body>
              <img src="https://cdn.coda.io/assets/x/img/import_google_docs.png"/>
              <img src="https://codaio.imgix.net/docs/x/blobs/bl-abc/deadbeef"/>
            </body></html>
        """,
        "https://vendor.example.com/order": """
            <html><body>
              <img src="https://assets.vendor.com/Images/Logo/Logo-White.png"/>
              <img src="https://assets.vendor.com/Images/Landing/chart.png"/>
              <img src="https://assets.vendor.com/Images/Products-2020/Advanced-Mitochondrial-Formula/1bottle.png"/>
              <img src="https://assets.vendor.com/Images/Landing/header-bottle.png"/>
            </body></html>
        """,
        "https://www.digistore24-app.com/detail/50163": """
            <html><head>
              <meta property="og:image" content="https://www.digistore24.com/webinc/images/brand/digistore/logo/logo_for_fb.png"/>
            </head></html>
        """,
    }

    def fake_fetch(url, timeout=8.0):
        return pages.get(url, "")

    monkeypatch.setattr("apf_import._fetch_page_html", fake_fetch)
    payload = {
        "product": {
            "name": "Advanced Mitochondrial Formula",
            "affiliate_url": "https://www.checkout-ds24.com/redir/50163/x/apf",
            "product_detail_url": "https://www.digistore24-app.com/detail/50163",
        },
        "vendor_materials": [
            {
                "source_type": "sales_page",
                "title": "Compliance Guidelines (Read Before Launch)",
                "url": "https://vendor.example.com/compliance",
            },
            {
                "source_type": "order_page",
                "title": "Too Tired To Enjoy It",
                "url": "https://vendor.example.com/order",
            },
            {
                "source_type": "offer_page",
                "title": "Earn 60% Commission Promoting Advanced Mitochondrial Formula",
                "url": "https://www.digistore24-app.com/detail/50163",
            },
        ],
    }
    normalized = normalize_apf_payload(payload)["normalized"]
    assert "bottle" in normalized["image_url"]
    assert "coda" not in normalized["image_url"]
    assert normalized["image_url"].endswith("header-bottle.png") or "1bottle.png" in normalized["image_url"]
    assert normalized["_image_resolve"]["status"] == "ok"


def test_looks_like_product_image_allows_extensionless_cdn():
    from apf_import import _looks_like_product_image

    assert _looks_like_product_image(
        "https://cdn.vendor.com/images/media/blob/abc123?w=800"
    )
    assert not _looks_like_product_image(
        "https://cdn.coda.io/assets/x/img/import_google_docs.png"
    )
    assert not _looks_like_product_image(
        "https://www.digistore24.com/webinc/images/brand/digistore/logo/logo_for_fb.png"
    )


def test_assess_completeness_warns_when_image_missing_but_offer_present():
    assessment = assess_product_completeness(
        {
            "product_name": "No Image Offer",
            "content_style": "honest_review",
            "price": "$47.00",
            "affiliate_link": "https://www.checkout-ds24.com/redir/1/x/apf",
            "image_url": "",
            "common_praises": "Works well",
            "common_complaints": "Pricey",
        }
    )
    assert "image_url" in assessment["warnings"]
    assert assessment["blocking"] == []
    assert assessment.get("image_resolve", {}).get("status") == "empty"


def test_assess_completeness_silent_when_image_present():
    assessment = assess_product_completeness(
        {
            "product_name": "Has Image",
            "content_style": "honest_review",
            "price": "$47.00",
            "affiliate_link": "https://example.com/hop",
            "image_url": "https://cdn.example.com/products/bottle.png",
            "common_praises": "Good",
            "common_complaints": "None",
        }
    )
    assert "image_url" not in assessment["warnings"]



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
    # Marketplace portal URLs must never ship as buyer affiliate CTAs.
    aff = (normalized.get("affiliate_link") or normalized.get("affiliateLink") or "").lower()
    assert "digistore24-app.com" not in aff
    assert "/affiliate/account/" not in aff


def test_rejects_digistore_marketplace_affiliate_url():
    payload = {
        "product": {
            "name": "Joseph's Well",
            "affiliate_url": (
                "https://www.digistore24-app.com/app/en/affiliate/account/"
                "marketplace/all/detail/54669"
            ),
        },
        "review_brief": {},
        "shadowcast_import": {
            "affiliate_link": (
                "https://www.digistore24-app.com/app/en/affiliate/account/"
                "marketplace/all/detail/54669"
            ),
        },
    }
    normalized = normalize_apf_payload(payload)["normalized"]
    aff = normalized.get("affiliate_link") or normalized.get("affiliateLink") or ""
    assert aff == ""

    assessment = assess_product_completeness(
        {
            "product_name": "Joseph's Well",
            "affiliate_link": (
                "https://www.digistore24-app.com/app/en/affiliate/account/"
                "marketplace/all/detail/54669"
            ),
            "price": "$79.95",
            "content_style": "honest_review",
        }
    )
    assert "affiliate_link" in assessment["warnings"]


def test_keeps_real_digistore_buyer_affiliate_url():
    hop = "https://www.checkout-ds24.com/redir/1/example/apf"
    normalized = normalize_apf_payload(
        {
            "product": {"name": "CircO2", "affiliate_url": hop},
            "review_brief": {},
        }
    )["normalized"]
    aff = normalized.get("affiliate_link") or normalized.get("affiliateLink")
    assert aff == hop


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


def test_claim_ledger_fills_key_features():
    payload = {
        "product": {
            "name": "Advanced Mitochondrial Formula",
            "affiliate_url": "https://example.com/hop",
        },
        "shadowcast_import": {
            "claim_ledger": [
                {
                    "text": "1 Bottle $79.95",
                    "kind": "price",
                    "source_url": "https://vendor.example/order",
                    "source_type": "order_page",
                },
                {
                    "text": "Niacinamide supports NAD",
                    "kind": "ingredient",
                    "source_url": "https://vendor.example/order",
                    "source_type": "order_page",
                },
            ]
        },
        "review_brief": {
            "common_claims": ["Positioned as a Health product."],
        },
    }
    normalized = normalize_apf_payload(payload)["normalized"]
    joined = "\n".join(normalized["key_features"])
    assert "79.95" in joined
    assert "Niacinamide" in joined
    assert "Positioned as" not in joined


def test_assess_completeness_warns_when_claim_ledger_empty_with_offer():
    assessment = assess_product_completeness(
        {
            "product_name": "No Claims Offer",
            "content_style": "honest_review",
            "price": "$47.00",
            "affiliate_link": "https://www.checkout-ds24.com/redir/1/x/apf",
            "image_url": "https://cdn.example.com/products/bottle.png",
            "common_praises": "Good",
            "common_complaints": "None",
            "claim_ledger": [],
        }
    )
    assert "claim_ledger" in assessment["warnings"]
    assert assessment["blocking"] == []


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
