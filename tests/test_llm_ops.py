"""LLM ops: telemetry, fallback chain, and RAG store tests."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from eval.output_validators import validate_youtube_assets
from llm_client import _normalize_validate_result, _provider_attempt_order
from llm_context import append_llm_call, clear_job_context, drain_pending_calls, set_job_context
from llm_telemetry import build_call_record, get_job_token_budget
from rag_store import ResearchStore, StyleCorpusStore, chunk_text, chunk_text_sentences


def test_normalize_validate_result_tuple():
    ok, errors = _normalize_validate_result((False, ["bad tag"]))
    assert ok is False
    assert errors == ["bad tag"]


def test_provider_attempt_order_includes_configured_provider():
    order = _provider_attempt_order()
    assert order
    assert order[0]


def test_llm_context_buffers_calls():
    clear_job_context()
    set_job_context("job123")
    append_llm_call({"label": "test"})
    pending = drain_pending_calls()
    assert len(pending) == 1
    clear_job_context()


def test_chunk_text_overlap():
    text = "word " * 200
    chunks = chunk_text(text, chunk_size=100, overlap=20)
    assert len(chunks) >= 2


def test_chunk_text_sentences_respects_boundaries():
    text = "First sentence about battery life. Second sentence about ANC performance. Third about price value."
    chunks = chunk_text_sentences(text, max_size=60, overlap_sentences=0)
    assert len(chunks) >= 2
    assert all("." in chunk or chunk for chunk in chunks)


def test_style_corpus_store_retrieves_audit_for_banned_language():
    corpus = Path(__file__).resolve().parents[1] / "backend" / "eval" / "rag_corpus"
    store = StyleCorpusStore(corpus)
    hits = store.retrieve_documents("What buyer-facing language is banned in scripts?", top_k=3)
    doc_ids = [doc_id for doc_id, _ in hits]
    assert "BUYER_LANGUAGE_RULES" in doc_ids or "AUDIT" in doc_ids


def test_research_store_lexical_retrieve(tmp_path):
    store = ResearchStore(tmp_path / "research")
    store._add_chunks(["Battery life is incredible for commuters"], "amazon_review_positive", {"type": "review"})
    store._add_chunks(["ANC cutouts on the train"], "amazon_review_negative", {"type": "review"})
    hits = store.retrieve("common complaints ANC", top_k=2)
    assert hits
    assert any("ANC" in hit["text"] for hit in hits)


def test_youtube_validator_checks_research_tag_overlap():
    assets = {
        "seo_title": "SoundCore Space A40 Honest Review",
        "tags": ["wireless earbuds", "anc earbuds", "review", "budget", "commuter"],
        "pinned_comment": "Link: https://example.com/a40",
    }
    product = {"_youtube_research": {"recommended_tags": ["wireless earbuds", "ANC earbuds"]}}
    ok, errors = validate_youtube_assets(assets, "https://example.com/a40", product)
    assert ok, errors


def test_job_token_budget_env(monkeypatch):
    monkeypatch.setenv("LLM_MAX_TOKENS_PER_JOB", "5000")
    assert get_job_token_budget() == 5000


def test_chat_completion_json_raises_after_exhausted_retries(monkeypatch):
    from llm_client import chat_completion_json

    monkeypatch.setattr(
        "llm_client.chat_completion",
        lambda *args, **kwargs: "not-json-at-all {{{",
    )
    with pytest.raises(RuntimeError, match="LLM JSON failed"):
        chat_completion_json("sys", "user", max_retries=0, required_keys=["seo_title"])


def test_build_call_record_shape():
    record = build_call_record(
        call_label="script",
        provider="ollama",
        model="qwen2.5:14b",
        latency_ms=120.5,
        prompt_chars=1000,
        response_chars=500,
        parse_ok=True,
        retry_index=0,
        validator_pass=True,
        validator_errors=[],
        fallback_used=False,
    )
    assert record["provider"] == "ollama"
    assert record["validator_pass"] is True
