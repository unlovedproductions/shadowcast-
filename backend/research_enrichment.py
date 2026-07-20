"""Merge Amazon scrape and YouTube research into product_info before LLM generation."""

import asyncio
from typing import Any

from amazon_scraper import scrape_amazon_product
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
        features = scraped["key_features"]
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
    return out


def _merge_youtube_research(product: dict, research: dict) -> dict:
    out = dict(product)
    tags = research.get("recommended_tags") or research.get("tags") or []
    if tags and not out.get("keywords"):
        out["keywords"] = tags[:20]
    titles = research.get("recommended_titles") or []
    if titles and _is_blank(out.get("unique_selling_point")):
        out["unique_selling_point"] = titles[0][:200]
    out["_youtube_research"] = {
        "recommended_tags": tags[:20],
        "recommended_titles": titles[:5],
        "question_keywords": (research.get("question_keywords") or [])[:10],
    }
    return out


async def enrich_product_research_async(product: dict) -> dict:
    enriched = dict(product)
    amazon_url = str(enriched.get("amazon_url") or "").strip()
    if amazon_url:
        scraped = await scrape_amazon_product(amazon_url)
        if isinstance(scraped, dict) and "error" not in scraped:
            enriched = _merge_amazon_scrape(enriched, scraped)

    name = str(enriched.get("product_name") or "").strip()
    needs_yt = _is_blank(enriched.get("keywords")) or _is_blank(enriched.get("unique_selling_point"))
    if name and needs_yt:
        research = await research_youtube_keywords(name)
        if isinstance(research, dict):
            enriched = _merge_youtube_research(enriched, research)
    return enriched


def enrich_product_research(product: dict) -> dict:
    return asyncio.run(enrich_product_research_async(product))
