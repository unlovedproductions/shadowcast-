"""Shared prompt fragments and builders for ShadowCast LLM generators."""

from content_styles import CONTENT_STYLES, normalize_content_style

LAYOUT_SCHEMA = """
LAYOUT SEGMENTS (required for comparison styles — use "layout" field on segment objects):
- vs_split: {"layout":"vs_split","product_a":"<main>","product_b":"<competitor>","text":"..."}
- spec_compare: {"layout":"spec_compare","spec_name":"Price","value_a":"$79","value_b":"$249","winner":"a","text":"..."}
- scorecard: {"layout":"scorecard","product_a":"<main>","product_b":"<competitor>","scores":[{"category":"Value","winner":"a"}],"text":"..."}
- price_compare: {"layout":"price_compare","price_products":[{"name":"<product>","price":"$79","highlight":true}],"text":"..."}
- winner_reveal: {"layout":"winner_reveal","winner_name":"<product>","text":"..."}
Use text_style aliases: pro_point/pros, con_point/cons, elimination, verdict, scorecard, comparison.
"""

RESEARCH_FRAMING = """RESEARCH-BASED APPROACH:
Content is based on publicly available specs, Amazon/Reddit reviews, and comparison articles.
You have NOT physically tested the product. Frame claims as:
- "According to the specs..."
- "Reviewers consistently say..."
- "Based on the data..."
- "Users report that..."
- "Compared to [competitor], the specs show..."
"""

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

PINNED_COMMENT_STRATEGY = """PINNED COMMENT STRATEGY (CRITICAL):
1. Personal take with honest framing for shoppers
2. Product link with a benefit statement for buyers
3. Quick FAQ answering 2-3 common objections from reviews
4. Engagement question to drive replies"""

SCRIPT_SYSTEM_PROMPT = (
    "You are an expert YouTube scriptwriter for honest, buyer-focused product review videos.\n"
    "Output must be valid JSON only — no markdown fences, no commentary.\n\n"
    + RESEARCH_FRAMING
    + "\n"
    + BUYER_FOCUS_RULES
)

YOUTUBE_ASSETS_SYSTEM_PROMPT = (
    "You are an expert YouTube SEO specialist creating buyer-focused posting packages.\n"
    "Output must be valid JSON only — no markdown fences, no commentary.\n\n"
    + BUYER_SEO_RULES
    + "\n\n"
    + PINNED_COMMENT_STRATEGY
)

HOOK_TYPES = [
    "curiosity",
    "problem_agitation",
    "listicle",
    "urgency",
    "contrarian",
    "data_bomb",
    "confession",
    "comparison_trap",
    "myth_buster",
]

HOOK_DESCRIPTIONS = {
    "curiosity": "Curiosity hook: provocative question or surprising fact about the product.",
    "problem_agitation": "Problem-agitation hook: name a pain point, agitate it, tease the solution.",
    "listicle": "Listicle hook: numbered format with a clear value proposition.",
    "urgency": "Urgency hook: limited-time deal or scarcity without fake pressure.",
    "contrarian": "Contrarian hook: challenge a popular opinion to spark curiosity.",
    "data_bomb": "Data-bomb hook: open with one specific, surprising statistic.",
    "confession": "Confession hook: admit a past mistake to build trust.",
    "comparison_trap": "Comparison-trap hook: price or spec contrast that makes viewers feel smart.",
    "myth_buster": "Myth-buster hook: challenge conventional wisdom in the category.",
}


def render_full_prompt(system: str, user: str) -> str:
    return f"=== SYSTEM ===\n{system}\n\n=== USER ===\n{user}"


def build_product_research_block(product_info: dict) -> str:
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

    youtube_block = ""
    yt = product_info.get("_youtube_research")
    if isinstance(yt, dict) and yt:
        tags = yt.get("recommended_tags") or []
        titles = yt.get("recommended_titles") or []
        questions = yt.get("question_keywords") or []
        if tags or titles or questions:
            youtube_block = f"""
YOUTUBE RESEARCH (use for titles/tags, not verbatim copy):
- Recommended tags: {', '.join(tags[:15]) if tags else 'N/A'}
- Title angles: {' | '.join(titles[:3]) if titles else 'N/A'}
- Question keywords: {', '.join(questions[:8]) if questions else 'N/A'}
"""

    retrieved_block = ""
    retrieved = product_info.get("_retrieved_research") or []
    if isinstance(retrieved, list) and retrieved:
        lines = []
        for hit in retrieved[:8]:
            if not isinstance(hit, dict):
                continue
            source = hit.get("source", "research")
            text = str(hit.get("text", "")).strip()
            if text:
                lines.append(f"- [{source}] {text[:320]}")
        if lines:
            retrieved_block = "\nRETRIEVED RESEARCH (ground claims here; do not invent beyond this):\n" + "\n".join(lines)

    amazon_block = ""
    amazon = product_info.get("_amazon_scrape")
    if isinstance(amazon, dict) and amazon.get("product_name"):
        amazon_block = f"""
AMAZON SCRAPE SUMMARY:
- Scraped title: {amazon.get('product_name', '')}
- Scraped price: {amazon.get('price', 'N/A')}
- Review samples ingested: +{amazon.get('positive_count', 0)} / -{amazon.get('negative_count', 0)}
"""

    return f"""PRODUCT RESEARCH DATA:
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
{comparison_block}{amazon_block}{youtube_block}{retrieved_block}"""


def build_research_context(product_info: dict) -> str:
    return build_product_research_block(product_info)


def get_style_instructions(content_style: str) -> str:
    style = CONTENT_STYLES.get(content_style, CONTENT_STYLES["honest_review"])

    if content_style == "honest_review":
        return f"""CONTENT STYLE: {style['name']}
TONE: {style['tone']}
SPECIAL INSTRUCTIONS:
- MUST include genuine CONS/LIMITATIONS (at least 2-3). This builds trust.
- Include a "Who This Is NOT For" segment — be specific.
- Include a "Who This IS For" segment — match to target audience.
- Frame the recommendation honestly: "If [specific need], this is great. If [other need], look elsewhere."
- Use natural purchase-guidance CTAs for shoppers:
  1. Soft mention at ~30% through: "Check the current price in the description if you want details."
  2. Value-justified CTA at ~60%: "Link below if this sounds like a fit for you."
  3. Final CTA at ~90%: "See the link for availability and latest info."
"""
    if content_style == "elimination":
        return f"""CONTENT STYLE: {style['name']}
TONE: {style['tone']}
SPECIAL INSTRUCTIONS:
- Start by naming 3-5 products in the category (including competitors).
- Eliminate them one by one with specific reasons (bad reviews, overpriced, missing features).
- Build suspense — the recommended product is revealed last.
- For each eliminated product, give ONE specific damning fact from reviews.
- The surviving product should still have honest pros AND cons mentioned.
- This format builds MASSIVE credibility because you're telling viewers what NOT to buy.
"""
    if content_style == "worth_it_or_waste":
        return f"""CONTENT STYLE: {style['name']}
TONE: {style['tone']}
SPECIAL INSTRUCTIONS:
- Frame as an investigation: "Is [Product] actually worth the hype?"
- List the marketing CLAIMS the product makes.
- Test each claim against review data and specs — "Claim vs Reality."
- Give a clear verdict: "WORTH IT" or "WASTE" with specific reasoning.
- Even for "Worth It" verdicts, mention 1-2 caveats.
- End with: "Worth It for [specific person], Waste for [other person]."
"""
    if content_style == "budget_challenge":
        return f"""CONTENT STYLE: {style['name']}
TONE: {style['tone']}
SPECIAL INSTRUCTIONS:
- Frame around a price constraint: "Best [category] under $[price]"
- Compare 3-5 options at similar price points.
- Crown a clear winner with specific reasons.
- Emphasize VALUE — what you get per dollar.
- Relatable tone: "You don't need to spend $300 when this $50 option does 90% of the same job."
"""
    if content_style == "vs_battle":
        return f"""CONTENT STYLE: {style['name']}
TONE: {style['tone']}
SPECIAL INSTRUCTIONS:
- Direct head-to-head comparison between the product and its main competitor.
- Compare spec-by-spec: price, features, build quality, user reviews, value.
- Use a scorecard format: Product A wins [category], Product B wins [category].
- Declare a clear overall winner with reasoning.
- Be fair — acknowledge where the competitor is actually better.
"""
    return f"""CONTENT STYLE: {style['name']}
TONE: {style['tone']}
SPECIAL INSTRUCTIONS:
- Clear product overview for everyday buyers considering a purchase.
- Focus on benefits, fit, and tradeoffs rather than hype.
- End with helpful guidance on where to check price and details if interested.
"""


def get_short_form_structure(content_style: str) -> str:
    if content_style == "elimination":
        return """STRUCTURE (compressed):
1. Hook: reject bad options fast
2. Elimination beats: 2-3 rejected products with one reason each (text_style: elimination)
3. Winner reveal layout segment
4. Honest pro + con, CTA"""
    if content_style == "worth_it_or_waste":
        return """STRUCTURE (compressed):
1. Hook: hype vs reality
2. Claim checks (2-3 beats)
3. Verdict segment (text_style: verdict)
4. CTA"""
    if content_style == "vs_battle":
        return """STRUCTURE (compressed):
1. vs_split layout opener
2. 2-3 spec_compare layout segments
3. scorecard layout segment
4. winner_reveal layout segment
5. CTA"""
    if content_style == "budget_challenge":
        return """STRUCTURE (compressed):
1. Price constraint hook
2. price_compare layout segment
3. Value winner + CTA"""
    if content_style == "honest_review":
        return """STRUCTURE (compressed):
1. Hook
2. Pros (text_style: pros) + cons (text_style: cons)
3. Who it's for / not for
4. Verdict + CTA"""
    return """STRUCTURE (compressed):
1. Hook
2. Features + benefits
3. Urgency CTA"""


def get_long_form_structure(content_style: str) -> str:
    if content_style == "elimination":
        return """STRUCTURE:
1. Hook (0-5s): "I tested X products. Most were garbage."
2. The Lineup (5-30s): Show all contenders
3. Elimination Rounds (30s-5min): Eliminate products one by one with specific reasons
4. The Winner (5-6min): Reveal and detail the surviving product (with honest pros AND cons)
5. Verdict + CTA (6-7min): Clear recommendation with link to check price/details"""
    if content_style == "worth_it_or_waste":
        return """STRUCTURE:
1. Hook (0-5s): "Is [Product] actually worth the hype?"
2. The Claims (5-30s): What the marketing promises
3. Claim vs Reality (30s-5min): Test each claim against review data
4. The Verdict (5-6min): Worth It or Waste? With specific reasoning
5. Who Should Buy + CTA (6-7min): Specific use cases + link to check details"""
    if content_style == "vs_battle":
        return """STRUCTURE:
1. Hook (0-5s): "[Product A] vs [Product B] — only one survives"
2. Meet the Contenders (5-30s): Brief intro of both
3. Round-by-Round (30s-5min): Compare spec by spec (price, features, reviews, build, value)
4. Scorecard (5-6min): Tally the wins
5. The Winner + CTA (6-7min): Clear recommendation + link to check details"""
    if content_style == "budget_challenge":
        return """STRUCTURE:
1. Hook (0-5s): "Best [category] under $[price]?"
2. The Contenders (5-30s): Show all budget options
3. Breakdown (30s-5min): Review each option's value proposition
4. The Winner (5-6min): Crown the budget champion
5. CTA (6-7min): Where to check the best option + link in description"""
    return """STRUCTURE:
1. Hook (0-5s): Compelling opening
2. Intro (5-15s): What this video covers
3. The Good (15s-2.5min): Key features and genuine strengths (with review evidence)
4. The Bad (2.5-4min): Honest limitations and cons (with review evidence)
5. Who It's For / Not For (4-5.5min): Specific use case matching
6. Verdict (5.5-6.5min): Clear, honest recommendation
7. CTA (6.5-7min): Help viewers check price/details if the product fits their needs"""


def short_form_json_schema(hook_type: str, content_style: str) -> str:
    return f"""OUTPUT JSON SCHEMA (types required, no markdown):
{{
  "hook_type": "{hook_type}",
  "content_style": "{content_style}",
  "format": "short_form",
  "total_duration_seconds": number,
  "title_suggestion": string,
  "segments": [
    {{
      "segment_id": number,
      "start_time": number,
      "duration": number,
      "text": string,
      "text_style": "headline_bold|subtitle|accent_pop|cta_button|stat_number|question|pro_point|con_point|verdict|elimination",
      "text_color": string,
      "bg_color": string,
      "animation": "pop_in|slide_up|fade_in|zoom_in|shake|typewriter|bounce",
      "transition_to_next": "cut|fade|glitch|flash|swipe|zoom",
      "visual_note": string
    }}
  ],
  "cta_text": string,
  "cta_placement": "end_screen|pinned_comment|link_in_bio"
}}
Generate 12-20 segments. Each text field: 3-8 words max."""


def long_form_json_schema(hook_type: str, content_style: str) -> str:
    return f"""OUTPUT JSON SCHEMA (types required, no markdown):
{{
  "hook_type": "{hook_type}",
  "content_style": "{content_style}",
  "format": "long_form",
  "total_duration_seconds": number,
  "title_suggestion": string,
  "chapters": [
    {{
      "chapter_name": string,
      "chapter_start_time": number,
      "segments": [
        {{
          "segment_id": number,
          "start_time": number,
          "duration": number,
          "text": string,
          "text_style": "headline_bold|subtitle|accent_pop|cta_button|stat_number|question|pro_point|con_point|verdict|elimination|comparison|scorecard",
          "text_color": string,
          "bg_color": string,
          "animation": "pop_in|slide_up|slide_left|fade_in|zoom_in|shake|typewriter|bounce|wipe",
          "transition_to_next": "cut|fade|glitch|flash|swipe|zoom",
          "is_pattern_interrupt": boolean,
          "visual_note": string
        }}
      ]
    }}
  ],
  "engagement_questions": [string, string, string],
  "cta_text": string,
  "cta_placement": "end_screen_and_description"
}}
Generate 60-100+ segments across 5-7 chapters. Each text field: 5-15 words."""


def youtube_assets_json_schema(affiliate_link: str) -> str:
    return f"""OUTPUT JSON SCHEMA (types required, no markdown):
{{
  "seo_title": string,
  "seo_title_alternatives": [string, string, string],
  "seo_description": string,
  "tags": [string],
  "hashtags": [string],
  "pinned_comment": string,
  "pinned_comment_alternatives": [string, string],
  "thumbnail_text_primary": string,
  "thumbnail_text_secondary": string,
  "thumbnail_color_scheme": string,
  "thumbnail_tips": string,
  "end_screen_strategy": string,
  "cards_strategy": string,
  "community_post_template": string,
  "best_posting_time": string,
  "posting_frequency_tip": string,
  "engagement_boosters": [string],
  "cross_promotion_ideas": [string],
  "reply_templates": {{
    "positive_comment": string,
    "question_about_product": string,
    "comparison_question": string,
    "negative_comment": string,
    "where_to_buy": string
  }},
  "series_suggestions": [string]
}}
Constraints: seo_title max 70 chars; tags: 30 buyer-intent tags; pinned_comment 300-600 chars; seo_description 2000-3000 chars.
Product link: {affiliate_link}"""


def build_script_user_prompt(
    product_info: dict,
    hook_type: str,
    content_style: str,
    fmt: str,
) -> str:
    content_style = normalize_content_style(content_style)
    product_info = {**product_info, "content_style": content_style}

    if fmt == "short_form":
        return f"""Create a SHORT-FORM YouTube script (30-60 seconds, vertical 9:16).
FACELESS TEXT-ONLY video — animated text overlays on dynamic backgrounds.

{build_product_research_block(product_info)}

HOOK TYPE: {hook_type}
{HOOK_DESCRIPTIONS[hook_type]}

{get_style_instructions(content_style)}

{get_short_form_structure(content_style)}

{LAYOUT_SCHEMA}

SHORT-FORM RULES:
- First 2 seconds: extremely compelling hook text
- Visual changes every 1-1.5 seconds
- Each text segment: 3-8 words MAX
- End with a helpful CTA to check price/details if the product fits their needs
- Include emoji strategically

{short_form_json_schema(hook_type, content_style)}"""

    return f"""Create a LONG-FORM YouTube script (5-8 minutes, 16:9 landscape).
FACELESS TEXT-ONLY video with animated text overlays.

{build_product_research_block(product_info)}

HOOK TYPE: {hook_type}
{HOOK_DESCRIPTIONS[hook_type]}

{get_style_instructions(content_style)}

{get_long_form_structure(content_style)}

{LAYOUT_SCHEMA}

LONG-FORM RULES:
- Each text segment: 5-15 words
- Visual changes every 3-5 seconds
- Pattern interrupts every 15-20 seconds (visual change, question, stat)
- Mix styles: headlines, bullets, stats, questions, pros, cons
- Include engagement trigger questions that encourage comments
- For trust-based styles: dedicate real screen time to cons/limitations

{long_form_json_schema(hook_type, content_style)}"""


def build_youtube_assets_user_prompt(
    product_info: dict,
    script: dict,
    video_format: str,
    *,
    script_context: str,
    cons_lines: str = "N/A",
    cta_lines: str = "N/A",
    verdict_lines: str = "N/A",
) -> str:
    hook_type = script.get("hook_type", "curiosity")
    content_style = script.get("content_style", "honest_review")
    title_suggestion = script.get("title_suggestion", "")
    format_label = (
        "YouTube Shorts (vertical, short-form)"
        if video_format == "short_form"
        else "YouTube (landscape, long-form)"
    )
    affiliate_link = product_info.get("affiliate_link", "[AFFILIATE_LINK]")
    series_name = product_info.get("series_name", "")

    return f"""Create a COMPLETE YouTube posting package for shoppers researching whether to buy a product.

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
Script Context: {script_context}
Buyer Signal Lines:
- Cons / Limitations: {cons_lines}
- CTA Guidance: {cta_lines}
- Conclusion / Verdict: {verdict_lines}

{youtube_assets_json_schema(affiliate_link)}
Include the product link naturally in the description and pinned comment."""
