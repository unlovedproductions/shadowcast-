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


def _append_warning(product: dict, message: str) -> None:
    warnings = product.setdefault("_research_warnings", [])
    if message and message not in warnings:
        warnings.append(message)


def _merge_amazon_scrape(product: dict, scraped: dict) -> dict:
    out = dict(product)
    if scraped.get("product_name") and _is_blank(out.get("product_name")):
        out["product_name"] = scraped["product_name"]
    if scraped.get("price") and _is_blank(out.get("price")):
        out["price"] = scraped["price"]
    if scraped.get("key_features") and not out.get("key_features"):
        features = scraped.get("key_features")
        out["key_features"] = features if isinstance(features, list) else [features]
    if scraped.get("image_url") and _is_blank(out.get("image_url")):
        out["image_url"] = scraped["image_url"]

    positives = scraped.get("positive_reviews") or []
    negatives = scraped.get("negative_reviews") or []
    praise_themes = str(scraped.get("common_praise_themes") or "").strip()
    complaint_themes = str(scraped.get("common_complaint_themes") or "").strip()
    if praise_themes and _is_blank(out.get("common_praises")):
        out["common_praises"] = praise_themes
    elif positives and _is_blank(out.get("common_praises")):
        out["common_praises"] = "\n".join(
            f"- {r.get('title', 'Praise')}: {r.get('text', '')}" for r in positives[:5]
        )
    if complaint_themes and _is_blank(out.get("common_complaints")):
        out["common_complaints"] = complaint_themes
    elif negatives and _is_blank(out.get("common_complaints")):
        out["common_complaints"] = "\n".join(
            f"- {r.get('title', 'Complaint')}: {r.get('text', '')}" for r in negatives[:5]
        )
    out["_amazon_scrape"] = {
        "product_name": scraped.get("product_name", ""),
        "price": scraped.get("price", ""),
        "positive_count": len(positives),
        "negative_count": len(negatives),
        "praise_themes": praise_themes,
        "complaint_themes": complaint_themes,
    }
    if not positives and not negatives:
        _append_warning(out, "Amazon scrape returned no review signals.")
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
    if not tags and not titles:
        _append_warning(out, "YouTube research returned no tags or titles.")
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
    enriched.setdefault("_research_warnings", [])
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
        else:
            detail = ""
            if isinstance(scraped, dict):
                detail = str(scraped.get("error") or "").strip()
            _append_warning(
                enriched,
                f"Amazon scrape failed{': ' + detail if detail else '.'}".rstrip("."),
            )

    name = str(enriched.get("product_name") or "").strip()
    # Keywords only — blank USP is intentional and must not force YT research.
    needs_yt = _is_blank(enriched.get("keywords"))
    if name and needs_yt:
        research = await research_youtube_keywords(name)
        if isinstance(research, dict):
            enriched = _merge_youtube_research(enriched, research)
            if store is not None:
                store.ingest_youtube(research)
        else:
            _append_warning(enriched, "YouTube research returned an empty response.")
    elif needs_yt and not name:
        _append_warning(enriched, "Skipped YouTube research: product name is blank.")

    if store is not None and store.chunks:
        store.save()
        retrieved = store.retrieve_for_product(name or "product")
        enriched = _apply_retrieved_research(enriched, retrieved)
        if not retrieved:
            _append_warning(enriched, "Research store had chunks but retrieve returned none.")

    # Soft signal when enrichment produced no secondary research artifacts at all.
    has_signals = bool(
        enriched.get("_amazon_scrape")
        or enriched.get("_youtube_research")
        or enriched.get("_retrieved_research")
    )
    if amazon_url or needs_yt:
        if not has_signals and not enriched.get("_research_warnings"):
            _append_warning(enriched, "Research enrichment produced no usable signals.")

    return enriched


def enrich_product_research(product: dict, research_dir: Optional[Path] = None) -> dict:
    return asyncio.run(enrich_product_research_async(product, research_dir))
