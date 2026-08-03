"""Style-rules RAG retrieval for script generation prompts."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from content_styles import normalize_content_style
from llm_config import get_config
from rag_store import StyleCorpusStore

STYLE_RULES_RAG_ENABLED = os.getenv("STYLE_RULES_RAG", "1") != "0"

_DEFAULT_CORPUS_DIR = Path(__file__).resolve().parent / "eval" / "rag_corpus"
_style_corpus_store: Optional[StyleCorpusStore] = None

_STYLE_QUERY_TERMS: dict[str, str] = {
    "vs_battle": "vs_split scorecard winner_reveal spec_compare comparison layout renderer contract duration",
    "elimination": "elimination winner_reveal layout segments renderer contract duration",
    "budget_challenge": "price_compare budget layout segments renderer contract duration",
    "honest_review": "pros cons limitations who not for buyer language renderer contract TTS",
    "worth_it_or_waste": "verdict worth it waste renderer contract duration TTS",
    "standard": "hook features CTA renderer contract duration animation",
}


def _corpus_dir() -> Path:
    override = os.getenv("STYLE_RULES_CORPUS_DIR", "").strip()
    if override:
        path = Path(override)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent / path
        return path
    return _DEFAULT_CORPUS_DIR


def get_style_corpus_store() -> StyleCorpusStore:
    global _style_corpus_store
    if _style_corpus_store is None:
        cfg = get_config()
        _style_corpus_store = StyleCorpusStore(_corpus_dir(), embed_base_url=cfg.base_url)
    return _style_corpus_store


def build_style_rules_query(content_style: str, fmt: str, hook_type: str) -> str:
    style_key = normalize_content_style(content_style)
    fmt_label = fmt.replace("_form", "").replace("_", " ")
    parts = [
        style_key,
        fmt_label,
        "buyer language banned layout segments hook renderer contract duration TTS animation",
        hook_type,
        _STYLE_QUERY_TERMS.get(style_key, "renderer contract duration"),
    ]
    return " ".join(part for part in parts if part)


def retrieve_style_rules(
    content_style: str,
    fmt: str,
    hook_type: str,
    *,
    top_k: int = 4,
) -> list[dict[str, Any]]:
    store = get_style_corpus_store()
    query = build_style_rules_query(content_style, fmt, hook_type)
    ranked = store.retrieve_documents(query, top_k=top_k)
    results: list[dict[str, Any]] = []
    for doc_id, score in ranked:
        text = ""
        for chunk in store.chunks:
            if chunk.get("doc_id") == doc_id:
                text = str(chunk.get("text", "")).strip()[:320]
                break
        if not text:
            text = store.documents.get(doc_id, "")[:320].strip()
        if text:
            results.append({"source": doc_id, "text": text, "score": score})
    return results


def attach_style_rules_context(
    product_info: dict,
    content_style: str,
    fmt: str,
    hook_type: str,
) -> dict:
    if not STYLE_RULES_RAG_ENABLED:
        return product_info
    if product_info.get("_style_rules_context"):
        return product_info
    hits = retrieve_style_rules(content_style, fmt, hook_type)
    if not hits:
        return product_info
    return {**product_info, "_style_rules_context": hits}
