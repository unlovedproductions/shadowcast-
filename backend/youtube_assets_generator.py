"""
ShadowCast YouTube Assets Generator — by Unloved Productions
Generates complete YouTube posting packages optimized for trust,
engagement, and affiliate conversions.
"""

import json
import os
from llm_config import get_config, parse_llm_json


def _collect_script_context(script: dict) -> str:
    parts = []
    if "chapters" in script:
        for chapter in script.get("chapters", []):
            chapter_name = str(chapter.get("chapter_name", "")).strip()
            if chapter_name:
                parts.append(f"[{chapter_name}]")
            for seg in chapter.get("segments", []):
                text = str(seg.get("text", "")).strip()
                if text:
                    parts.append(text)
    else:
        for seg in script.get("segments", []):
            text = str(seg.get("text", "")).strip()
            if text:
                parts.append(text)
    return " | ".join(parts)


def _fit_script_context(context: str, max_chars: int = 3600) -> str:
    if len(context) <= max_chars:
        return context
    head = max_chars // 2
    tail = max_chars - head
    return f"{context[:head]} | ... | {context[-tail:]}"


def generate_youtube_assets(product_info: dict, script: dict, video_format: str) -> dict:
    cfg = get_config()
    client = cfg.get_client()

    hook_type = script.get("hook_type", "curiosity")
    content_style = script.get("content_style", "honest_review")
    title_suggestion = script.get("title_suggestion", "")

    all_text = _fit_script_context(_collect_script_context(script))

    format_label = "YouTube Shorts (vertical, short-form)" if video_format == "short_form" else "YouTube (landscape, long-form)"
    affiliate_link = product_info.get('affiliate_link', '[AFFILIATE_LINK]')
    series_name = product_info.get('series_name', '')

    prompt = f"""You are an expert YouTube SEO specialist creating buyer-focused posting packages for people researching whether to buy a product. Generate a COMPLETE YouTube posting package that helps shoppers decide with honest pros, cons, fit, and practical purchase guidance.

PRODUCT INFORMATION:
- Product Name: {product_info['product_name']}
- Niche: {product_info.get('niche', product_info.get('product_category', 'General'))}
- Keywords: {', '.join(product_info.get('keywords', product_info.get('key_features', [])))}
- Product Link: {affiliate_link}
- Price: {product_info.get('price', 'N/A')}
- Target Audience: {product_info.get('target_audience', 'General consumers')}
- Competitor Products: {', '.join(product_info.get('competitors', ['N/A']))}
- Unique Selling Point: {product_info.get('unique_selling_point', '')}
- Discount: {product_info.get('discount_info', '')}
- Coupon Code: {product_info.get('coupon_code', '')}
- Common Complaints: {product_info.get('common_complaints', 'N/A')}
- Common Praises: {product_info.get('common_praises', 'N/A')}
- Series Name: {series_name}

VIDEO: {format_label} | Hook: {hook_type} | Style: {content_style} | Title: {title_suggestion}
Script Context: {all_text}

BUYER-FOCUSED APPROACH:
- Titles should help shoppers decide, not hype affiliate earnings
- Description must include HONEST framing — mention that you cover pros AND cons
- NEVER mention commission rates, EPC, hop conversion, or promoting the product
- Pinned comment must answer buyer objections and include the product link once, naturally
- Tags should target buyer-intent keywords (people ready to research or purchase)
- CTAs should feel like helpful purchase guidance, not pushy sales copy

PINNED COMMENT STRATEGY (CRITICAL):
The pinned comment is prime real estate. Use this structure:
1. Personal take with honest framing for shoppers
2. Product link with a benefit statement for buyers
3. Quick FAQ answering 2-3 common objections from reviews
4. Engagement question to drive replies

Return JSON:
{{
    "seo_title": "<max 70 chars, buyer-intent keyword, curiosity gap — NOT clickbait>",
    "seo_title_alternatives": ["<alt1 - negative framing test>", "<alt2 - question format>", "<alt3 - number/data format>"],
    "seo_description": "<2000-3000 chars structured as: Hook paragraph mentioning honest review → Product overview → Key Pros (3-4) → Key Cons (2-3) → Product link with soft CTA → More details → Timestamps → One brief disclaimer if needed: 'As an affiliate, I may earn a commission at no extra cost to you.'>",
    "tags": ["<30 tags: mix buyer-intent keywords like 'best X 2026', 'X review honest', 'X vs Y', 'should I buy X', 'X pros and cons'>"],
    "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"],
    "pinned_comment": "<300-600 chars: Personal honest take for shoppers → Product link with benefit → Quick FAQ (2-3 common objections answered) → Question for replies>",
    "pinned_comment_alternatives": ["<alt1 - comparison angle>", "<alt2 - value/savings angle>"],
    "thumbnail_text_primary": "<2-4 words, test negative framing like 'DON'T BUY' or 'HONEST TRUTH'>",
    "thumbnail_text_secondary": "<supporting text>",
    "thumbnail_color_scheme": "<description — suggest signature color consistency>",
    "thumbnail_tips": "<specific tips for A/B testing: test negative vs positive framing>",
    "end_screen_strategy": "<strategy linking to related content in same series/niche>",
    "cards_strategy": "<strategy — link to comparison or follow-up video>",
    "community_post_template": "<poll or question format to drive engagement before/after video>",
    "best_posting_time": "<recommendation based on niche and audience>",
    "posting_frequency_tip": "<quality over quantity advice>",
    "engagement_boosters": ["<tip1>", "<tip2>", "<tip3>", "<tip4>", "<tip5>"],
    "cross_promotion_ideas": ["<idea1 - Shorts teaser>", "<idea2 - Reddit/forum>", "<idea3 - other platform>"],
    "reply_templates": {{
        "positive_comment": "<grateful + helpful purchase guidance>",
        "question_about_product": "<helpful answer + product link naturally>",
        "comparison_question": "<honest comparison + link to comparison video if applicable>",
        "negative_comment": "<acknowledge concern + provide balanced perspective>",
        "where_to_buy": "<direct product link + mention any active deals>"
    }},
    "series_suggestions": ["<next video idea in same series>", "<related comparison video>", "<follow-up content idea>"]
}}

Product link: {affiliate_link}
Include the product link naturally in the description and pinned comment for shoppers who want to check details.
Return ONLY valid JSON."""

    response = client.chat.completions.create(
        model=cfg.model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        response_format={"type": "json_object"},
    )

    content = getattr(response.choices[0].message, "content", "")
    parsed = parse_llm_json(content)

    # If parsed output doesn't look like the expected package, create a safe fallback
    if not isinstance(parsed, dict) or "seo_title" not in parsed:
        fallback = {
            "seo_title": title_suggestion or f"{product_info['product_name']} - Honest Review",
            "seo_title_alternatives": [],
            "seo_description": f"Auto-generated posting package for {product_info['product_name']}.",
            "tags": product_info.get("keywords", [])[:20],
            "hashtags": [],
            "pinned_comment": "",
            "thumbnail_text_primary": product_info['product_name'],
        }
        # Merge any fields found in parsed dict
        if isinstance(parsed, dict):
            fallback.update(parsed)
        return fallback

    return parsed


def save_posting_package_readable(package: dict, product_info: dict, output_path: str):
    with open(output_path, "w") as f:
        f.write("=" * 70 + "\n")
        f.write("  YOUTUBE POSTING PACKAGE — Generated by ShadowCast\n")
        f.write(f"  Product: {product_info['product_name']}\n")
        if product_info.get('series_name'):
            f.write(f"  Series: {product_info['series_name']}\n")
        f.write("=" * 70 + "\n\n")

        for hook_type, formats in package.items():
            hook_name = hook_type.replace("_", " ").upper()
            for fmt_key, assets in formats.items():
                fmt_name = "SHORT-FORM (YouTube Shorts)" if fmt_key == "short_form" else "LONG-FORM (YouTube)"
                f.write("\n" + "━" * 70 + "\n")
                f.write(f"  HOOK: {hook_name} | FORMAT: {fmt_name}\n")
                f.write("━" * 70 + "\n\n")

                f.write(f"SEO TITLE:\n{assets.get('seo_title', 'N/A')}\n\n")
                f.write("Alternative Titles (A/B Test These):\n")
                for i, alt in enumerate(assets.get("seo_title_alternatives", []), 1):
                    f.write(f"  {i}. {alt}\n")

                f.write(f"\nSEO DESCRIPTION:\n{'-'*50}\n{assets.get('seo_description', 'N/A')}\n{'-'*50}\n\n")
                f.write(f"TAGS:\n{', '.join(assets.get('tags', []))}\n\n")
                f.write(f"HASHTAGS:\n{' '.join(assets.get('hashtags', []))}\n\n")

                f.write(f"PINNED COMMENT (Trust-Optimized):\n{'-'*50}\n{assets.get('pinned_comment', 'N/A')}\n{'-'*50}\n\n")
                f.write("Alternative Pinned Comments:\n")
                for i, alt in enumerate(assets.get("pinned_comment_alternatives", []), 1):
                    f.write(f"  {i}. {alt}\n")

                f.write(f"\nTHUMBNAIL (A/B Test Negative vs Positive Framing):\n")
                f.write(f"  Primary: {assets.get('thumbnail_text_primary', 'N/A')}\n")
                f.write(f"  Secondary: {assets.get('thumbnail_text_secondary', 'N/A')}\n")
                f.write(f"  Colors: {assets.get('thumbnail_color_scheme', 'N/A')}\n")
                f.write(f"  Tips: {assets.get('thumbnail_tips', 'N/A')}\n\n")

                f.write(f"END SCREEN: {assets.get('end_screen_strategy', 'N/A')}\n\n")
                f.write(f"CARDS: {assets.get('cards_strategy', 'N/A')}\n\n")
                f.write(f"COMMUNITY POST:\n{'-'*50}\n{assets.get('community_post_template', 'N/A')}\n{'-'*50}\n\n")
                f.write(f"POSTING TIME: {assets.get('best_posting_time', 'N/A')}\n")
                f.write(f"FREQUENCY: {assets.get('posting_frequency_tip', 'N/A')}\n\n")

                f.write("ENGAGEMENT BOOSTERS:\n")
                for i, t in enumerate(assets.get("engagement_boosters", []), 1):
                    f.write(f"  {i}. {t}\n")
                f.write("\nCROSS-PROMOTION:\n")
                for i, t in enumerate(assets.get("cross_promotion_ideas", []), 1):
                    f.write(f"  {i}. {t}\n")

                replies = assets.get("reply_templates", {})
                f.write(f"\nREPLY TEMPLATES:\n")
                f.write(f"  Positive: {replies.get('positive_comment','')}\n")
                f.write(f"  Question: {replies.get('question_about_product','')}\n")
                f.write(f"  Comparison: {replies.get('comparison_question','')}\n")
                f.write(f"  Negative: {replies.get('negative_comment','')}\n")
                f.write(f"  Where to Buy: {replies.get('where_to_buy','')}\n")

                series = assets.get("series_suggestions", [])
                if series:
                    f.write("\nNEXT VIDEO IDEAS:\n")
                    for i, s in enumerate(series, 1):
                        f.write(f"  {i}. {s}\n")
                f.write("\n")

        f.write("=" * 70 + "\n  END OF POSTING PACKAGE\n" + "=" * 70 + "\n")
    return output_path
