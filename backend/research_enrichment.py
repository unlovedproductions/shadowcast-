"""Merge Amazon scrape, YouTube research, and local RAG into product_info before generation."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Optional

from amazon_scraper import scrape_amazon_product
from llm_config import get_config
from rag_store import ResearchStore
from youtube_research import research_youtube_keywords


def _is_blank(value: Any) -> bool:
    return not str(value or "").strip()


def _merge_amazon_scrape(product: dict, scraped: dict) -> dict:
    out = dict(product)
    if scraped.get("product_name") and _is_blank(out.get("product_name")):
        out["product_name"] = scraped["product_name"]
    if scraped.get("price") and _is_blank(out.get("price")):
        out["price"] = scraped["price"]
    if scraped.get("key_features") and not out.get("key_features"):
        features = scraped.get("key_features")
        out["key_features"] = features if isinstance(features, list) else [features]

    positives = scraped.get("positive_reviews") or []
    negatives = scraped.get("negative_reviews") or []
    if positives and _is_blank(out.get("common_praises")):
        out["common_praises"] = "\n".join(
            f"- {r.get('title', 'Praise')}: {r.get('text', '')}" for r in positives[:5]
        )
    if negatives and _is_blank(out.get("common_complaints")):
        out["common_complaints"] = "\n".join(
            f"- {r.get('title', 'Complaint')}: {r.get('text', '')}" for r in negatives[:5]
        )
    out["_amazon_scrape"] = {
        "product_name": scraped.get("product_name", ""),
        "price": scraped.get("price", ""),
        "positive_count": len(positives),
        "negative_count": len(negatives),
    }
    return out


def _merge_youtube_research(product: dict, research: dict) -> dict:
    out = dict(product)
    tags = research.get("recommended_tags") or research.get("tags") or []
    if tags and not out.get("keywords"):
        out["keywords"] = tags[:20]
    titles = research.get("recommended_titles") or []
    # Titles stay in _youtube_research only — never write into unique_selling_point.
    out["_youtube_research"] = {
        "recommended_tags": tags[:20],
        "recommended_titles": titles[:5],
        "question_keywords": (research.get("question_keywords") or [])[:10],
    }
    return out


def _apply_retrieved_research(product: dict, retrieved: list[dict]) -> dict:
    out = dict(product)
    if not retrieved:
        return out
    out["_retrieved_research"] = retrieved

    complaints = [
        hit["text"]
        for hit in retrieved
        if "negative" in hit.get("source", "") or hit.get("metadata", {}).get("type") == "review"
    ]
    praises = [
        hit["text"]
        for hit in retrieved
        if "positive" in hit.get("source", "")
    ]
    if complaints and _is_blank(out.get("common_complaints")):
        out["common_complaints"] = "\n".join(f"- {text[:240]}" for text in complaints[:5])
    if praises and _is_blank(out.get("common_praises")):
        out["common_praises"] = "\n".join(f"- {text[:240]}" for text in praises[:5])
    return out


async def enrich_product_research_async(
    product: dict,
    research_dir: Optional[Path] = None,
) -> dict:
    enriched = dict(product)
    store = None
    if research_dir is not None:
        cfg = get_config()
        store = ResearchStore(research_dir, embed_base_url=cfg.base_url)

    amazon_url = str(enriched.get("amazon_url") or "").strip()
    if amazon_url:
        scraped = await scrape_amazon_product(amazon_url)
        if isinstance(scraped, dict) and "error" not in scraped:
            enriched = _merge_amazon_scrape(enriched, scraped)
            if store is not None:
                store.ingest_scrape(scraped)

    name = str(enriched.get("product_name") or "").strip()
    needs_yt = _is_blank(enriched.get("keywords")) or _is_blank(enriched.get("unique_selling_point"))
    if name and needs_yt:
        research = await research_youtube_keywords(name)
        if isinstance(research, dict):
            enriched = _merge_youtube_research(enriched, research)
            if store is not None:
                store.ingest_youtube(research)

    if store is not None and store.chunks:
        store.save()
        retrieved = store.retrieve_for_product(name or "product")
        enriched = _apply_retrieved_research(enriched, retrieved)

    return enriched


def enrich_product_research(product: dict, research_dir: Optional[Path] = None) -> dict:
    return asyncio.run(enrich_product_research_async(product, research_dir))
