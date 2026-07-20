"""Shared prompt fragments for ShadowCast LLM generators."""

from content_styles import normalize_content_style

LAYOUT_SCHEMA = """
LAYOUT SEGMENTS (required for comparison styles — use "layout" field on segment objects):
- vs_split: {"layout":"vs_split","product_a":"<main>","product_b":"<competitor>","text":"..."}
- spec_compare: {"layout":"spec_compare","spec_name":"Price","value_a":"$79","value_b":"$249","winner":"a","text":"..."}
- scorecard: {"layout":"scorecard","product_a":"<main>","product_b":"<competitor>","scores":[{"category":"Value","winner":"a"}],"text":"..."}
- price_compare: {"layout":"price_compare","price_products":[{"name":"<product>","price":"$79","highlight":true}],"text":"..."}
- winner_reveal: {"layout":"winner_reveal","winner_name":"<product>","text":"..."}
Use text_style aliases: pro_point/pros, con_point/cons, elimination, verdict, scorecard, comparison.
"""

SCRIPT_SYSTEM_PROMPT = (
    "You are an expert YouTube scriptwriter for honest, buyer-focused product review videos. "
    "Output must be valid JSON only — no markdown fences, no commentary."
)

YOUTUBE_ASSETS_SYSTEM_PROMPT = (
    "You are an expert YouTube SEO specialist creating buyer-focused posting packages. "
    "Output must be valid JSON only — no markdown fences, no commentary."
)

BUYER_FOCUS_RULES = """RULES:
- Speak to shoppers considering a purchase, NOT affiliate marketers
- NEVER mention commission rates, EPC, hop conversion, promoting, or earning as an affiliate
- Use research-based language ("reviewers say", "specs show", "data proves")
- For honest/trust styles: include at least ONE con or limitation"""

BUYER_SEO_RULES = """BUYER-FOCUSED APPROACH:
- Titles should help shoppers decide, not hype affiliate earnings
- Description must include HONEST framing — mention that you cover pros AND cons
- NEVER mention commission rates, EPC, hop conversion, or promoting the product
- Pinned comment must answer buyer objections and include the product link once, naturally
- Tags should target buyer-intent keywords (people ready to research or purchase)
- CTAs should feel like helpful purchase guidance, not pushy sales copy"""


def build_research_context(product_info: dict) -> str:
    competitors = ", ".join(product_info.get("competitors", [])) or "N/A"
    common_complaints = product_info.get("common_complaints", "") or "Research common complaints from Amazon reviews and Reddit"
    common_praises = product_info.get("common_praises", "") or "Research top-rated aspects from user reviews"
    who_not_for = product_info.get("who_not_for", "") or "Determine from specs and reviews who should NOT buy this"

    comparison_block = ""
    if content_style := product_info.get("content_style"):
        style_key = normalize_content_style(content_style)
        if style_key in ("vs_battle", "elimination", "budget_challenge"):
            comparison_block = f"""
COMPARISON CONTEXT (use in layout segments):
- Main product: {product_info['product_name']}
- Competitors: {competitors}
- Price comparison notes: {product_info.get('price_comparison', '') or 'Compare against category alternatives'}
"""

    return f"""RESEARCH-BASED APPROACH (IMPORTANT):
You are creating content based on publicly available information — manufacturer specs,
Amazon/Reddit reviews, comparison articles, and expert opinions. You do NOT need to
have physically tested the product. Frame all claims using language like:
- "According to the specs..."
- "Reviewers consistently say..."
- "Based on the data..."
- "Users report that..."
- "Compared to [competitor], the specs show..."

PRODUCT RESEARCH DATA:
- Product Name: {product_info['product_name']}
- Key Features: {', '.join(product_info.get('key_features', []))}
- Price: {product_info.get('price', 'N/A')}
- Target Audience: {product_info.get('target_audience', 'General consumers')}
- Product Category: {product_info.get('product_category', product_info.get('niche', 'General'))}
- Unique Selling Point: {product_info.get('unique_selling_point', '')}
- Competitors: {competitors}
- Common Complaints (from reviews): {common_complaints}
- Common Praises (from reviews): {common_praises}
- Who Should NOT Buy This: {who_not_for}
- Discount Info: {product_info.get('discount_info', '')}
- Coupon Code: {product_info.get('coupon_code', '')}
- Price Comparison Notes: {product_info.get('price_comparison', '')}
- Series Name: {product_info.get('series_name', '')}
{comparison_block}"""


def short_form_json_schema(hook_type: str, content_style: str) -> str:
    return f"""Return JSON with this exact structure:
{{
    "hook_type": "{hook_type}",
    "content_style": "{content_style}",
    "format": "short_form",
    "total_duration_seconds": <number>,
    "title_suggestion": "<catchy title>",
    "segments": [
        {{
            "segment_id": 1,
            "start_time": 0.0,
            "duration": <seconds>,
            "text": "<text overlay, 3-8 words>",
            "text_style": "<headline_bold|subtitle|accent_pop|cta_button|stat_number|question|pro_point|con_point|verdict|elimination>",
            "text_color": "<hex>",
            "bg_color": "<hex>",
            "animation": "<pop_in|slide_up|fade_in|zoom_in|shake|typewriter|bounce>",
            "transition_to_next": "<cut|fade|glitch|flash|swipe|zoom>",
            "visual_note": "<background description>"
        }}
    ],
    "cta_text": "<call to action>",
    "cta_placement": "<end_screen|pinned_comment|link_in_bio>"
}}
Generate 12-20 segments."""


def long_form_json_schema(hook_type: str, content_style: str) -> str:
    return f"""Return JSON with this exact structure:
{{
    "hook_type": "{hook_type}",
    "content_style": "{content_style}",
    "format": "long_form",
    "total_duration_seconds": <300-480>,
    "title_suggestion": "<catchy title>",
    "chapters": [
        {{
            "chapter_name": "<chapter title>",
            "chapter_start_time": <seconds>,
            "segments": [
                {{
                    "segment_id": <number>,
                    "start_time": <seconds>,
                    "duration": <seconds>,
                    "text": "<text overlay, 5-15 words>",
                    "text_style": "<headline_bold|subtitle|accent_pop|cta_button|stat_number|question|pro_point|con_point|verdict|elimination|comparison|scorecard>",
                    "text_color": "<hex>",
                    "bg_color": "<hex>",
                    "animation": "<pop_in|slide_up|slide_left|fade_in|zoom_in|shake|typewriter|bounce|wipe>",
                    "transition_to_next": "<cut|fade|glitch|flash|swipe|zoom>",
                    "is_pattern_interrupt": <true|false>,
                    "visual_note": "<background description>"
                }}
            ]
        }}
    ],
    "engagement_questions": ["<q1>", "<q2>", "<q3>"],
    "cta_text": "<call to action>",
    "cta_placement": "end_screen_and_description"
}}
Generate 60-100+ segments across 5-7 chapters."""


def youtube_assets_json_schema(affiliate_link: str) -> str:
    return f"""Return JSON with this exact structure:
{{
    "seo_title": "<max 70 chars, buyer-intent keyword>",
    "seo_title_alternatives": ["<alt1>", "<alt2>", "<alt3>"],
    "seo_description": "<2000-3000 chars: Hook → Overview → Pros → Cons → Link → Timestamps → Brief disclaimer>",
    "tags": ["<30 buyer-intent tags>"],
    "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"],
    "pinned_comment": "<300-600 chars: honest take → link → FAQ → engagement question>",
    "pinned_comment_alternatives": ["<alt1>", "<alt2>"],
    "thumbnail_text_primary": "<2-4 words>",
    "thumbnail_text_secondary": "<supporting text>",
    "thumbnail_color_scheme": "<description>",
    "thumbnail_tips": "<A/B testing tips>",
    "end_screen_strategy": "<strategy>",
    "cards_strategy": "<strategy>",
    "community_post_template": "<poll or question>",
    "best_posting_time": "<recommendation>",
    "posting_frequency_tip": "<advice>",
    "engagement_boosters": ["<tip1>", "<tip2>", "<tip3>", "<tip4>", "<tip5>"],
    "cross_promotion_ideas": ["<idea1>", "<idea2>", "<idea3>"],
    "reply_templates": {{
        "positive_comment": "<template>",
        "question_about_product": "<template>",
        "comparison_question": "<template>",
        "negative_comment": "<template>",
        "where_to_buy": "<template>"
    }},
    "series_suggestions": ["<idea1>", "<idea2>", "<idea3>"]
}}
Product link: {affiliate_link}"""
