from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_apf_import_module_avoids_commission_discount_mapping():
    text = (ROOT / "backend" / "apf_import.py").read_text()
    assert "_buyer_discount_info" in text
    assert "_commission_discount" not in text
    assert "_sanitize_product_name" in text


def test_prompts_are_buyer_focused():
    text = (ROOT / "backend" / "prompts.py").read_text()
    assert "affiliate product marketing" not in text
    assert "NOT affiliate marketers" in text
    assert "NEVER mention commission rates" in text
    assert "affiliate disclosure" in text.lower() or "AFFILIATE DISCLOSURE" in text
    assert "Paid link" in text or "Paid link:" in text


def test_script_generator_uses_prompt_builders():
    text = (ROOT / "backend" / "script_generator.py").read_text()
    assert "build_script_user_prompt" in text
    assert "NOT affiliate marketers" not in text


def test_youtube_assets_uses_prompt_builder():
    text = (ROOT / "backend" / "youtube_assets_generator.py").read_text()
    assert "build_youtube_assets_user_prompt" in text
    assert "affiliate marketing strategist" not in text.lower()
    assert "Include it 3+ times" not in text


def test_frontend_apf_uses_backend_normalization_and_buyer_facing_copy():
    text = (ROOT / "frontend" / "index.html").read_text()
    assert 'fetch("/api/import-apf/direct"' in text
    assert "window.hydrateAPFBackendImport(JSON.parse(getBody))" in text
    assert 'niche: clean(normalized.niche) || "General"' in text
    assert "affiliate product" not in text.split("<!-- BEGIN UNLOVED_DIRECT_APF_DRAFT_LOADER -->", 1)[1].lower()
    assert "ClickBank product imported from APF" not in text


def test_buyer_language_rules_require_disclosure():
    text = (ROOT / "backend" / "eval" / "rag_corpus" / "BUYER_LANGUAGE_RULES.md").read_text()
    assert "Required shopper disclosure" in text
    assert "Paid link" in text or "Affiliate link" in text
    assert "EPC" in text
