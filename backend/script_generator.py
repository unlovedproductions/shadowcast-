"""
Script Generator Module — Trust-Based Honest Review Edition
Generates scripts using AI research (specs, reviews, comparisons) so you
never need to physically buy or test products.
"""

import json
from llm_config import get_config, parse_llm_json
from content_styles import (
    CONTENT_STYLES,
    DEFAULT_CONTENT_STYLE,
    normalize_content_style,
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
    "curiosity": "A curiosity-driven hook that poses a provocative question or reveals a surprising fact. Example: 'You've been using your [product] wrong this whole time—here's why.'",
    "problem_agitation": "A problem-agitation hook that identifies a common pain point, agitates it, then teases the solution. Example: 'Tired of [pain point]? This $XX gadget is a literal lifesaver.'",
    "listicle": "A listicle hook with numbered format and clear value proposition. Example: 'Top 5 reasons you NEED this [product] in 2025.'",
    "urgency": "An urgency/FOMO hook leveraging limited-time deals or scarcity. Example: 'This deal is ending soon — here's why you need to grab it NOW.'",
    "contrarian": "A contrarian hook challenging a popular opinion to spark curiosity. Example: 'Stop buying [competitor] — this alternative is actually better.'",
    "data_bomb": "Open with a specific, surprising statistic. Example: '87% of people who buy [product category] return it within 30 days. Here's the one that nobody returns.' Specificity creates instant credibility.",
    "confession": "A confession hook that admits a past mistake to build trust. Example: 'I've been recommending the wrong [product] for 6 months. Here's what I should have told you.' Creates massive curiosity and trust simultaneously.",
    "comparison_trap": "A price comparison hook that makes viewers feel smart. Example: '[Product A] costs $200. [Product B] costs $40. They perform identically. Here's proof.' Extremely high-converting because it taps into the desire to feel smart about purchases.",
    "myth_buster": "Challenge conventional wisdom. Example: 'Everyone says you need to spend $300 on [product category]. That's a lie.' Creates engagement through controversy without being negative about a specific product.",
}

LAYOUT_SCHEMA = """
LAYOUT SEGMENTS (required for comparison styles — use "layout" field on segment objects):
- vs_split: {"layout":"vs_split","product_a":"<main>","product_b":"<competitor>","text":"..."}
- spec_compare: {"layout":"spec_compare","spec_name":"Price","value_a":"$79","value_b":"$249","winner":"a","text":"..."}
- scorecard: {"layout":"scorecard","product_a":"<main>","product_b":"<competitor>","scores":[{"category":"Value","winner":"a"}],"text":"..."}
- price_compare: {"layout":"price_compare","price_products":[{"name":"<product>","price":"$79","highlight":true}],"text":"..."}
- winner_reveal: {"layout":"winner_reveal","winner_name":"<product>","text":"..."}
Use text_style aliases: pro_point/pros, con_point/cons, elimination, verdict, scorecard, comparison.
"""


def _call_llm(prompt: str) -> dict:
    cfg = get_config()
    client = cfg.get_client()
    response = client.chat.completions.create(
        model=cfg.model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        response_format={"type": "json_object"},
    )
    content = getattr(response.choices[0].message, "content", "")
    parsed = parse_llm_json(content)
    return parsed


def _build_research_context(product_info: dict) -> str:
    """Build a research context block that tells the LLM to use publicly
    available information rather than hands-on testing."""
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

This builds credibility through research authority, not personal testing.

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


def _get_style_instructions(content_style: str) -> str:
    """Return style-specific script instructions."""
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
    elif content_style == "elimination":
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
    elif content_style == "worth_it_or_waste":
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
    elif content_style == "budget_challenge":
        return f"""CONTENT STYLE: {style['name']}
TONE: {style['tone']}
SPECIAL INSTRUCTIONS:
- Frame around a price constraint: "Best [category] under $[price]"
- Compare 3-5 options at similar price points.
- Crown a clear winner with specific reasons.
- Emphasize VALUE — what you get per dollar.
- Relatable tone: "You don't need to spend $300 when this $50 option does 90% of the same job."
"""
    elif content_style == "vs_battle":
        return f"""CONTENT STYLE: {style['name']}
TONE: {style['tone']}
SPECIAL INSTRUCTIONS:
- Direct head-to-head comparison between the product and its main competitor.
- Compare spec-by-spec: price, features, build quality, user reviews, value.
- Use a scorecard format: Product A wins [category], Product B wins [category].
- Declare a clear overall winner with reasoning.
- Be fair — acknowledge where the competitor is actually better.
"""
    else:  # standard
        return f"""CONTENT STYLE: {style['name']}
TONE: {style['tone']}
SPECIAL INSTRUCTIONS:
- Clear product overview for everyday buyers considering a purchase.
- Focus on benefits, fit, and tradeoffs rather than hype.
- End with helpful guidance on where to check price and details if interested.
"""


def _get_short_form_structure(content_style: str) -> str:
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


def generate_short_form_script(product_info: dict, hook_type: str, content_style: str = None) -> dict:
    if content_style is None:
        content_style = product_info.get("content_style", DEFAULT_CONTENT_STYLE)
    content_style = normalize_content_style(content_style)
    product_info = {**product_info, "content_style": content_style}

    research_ctx = _build_research_context(product_info)
    style_instructions = _get_style_instructions(content_style)
    structure = _get_short_form_structure(content_style)

    prompt = f"""You are an expert YouTube Shorts scriptwriter creating honest, buyer-focused product review videos for everyday consumers. These are FACELESS TEXT-ONLY videos — all content is animated text overlays on dynamic backgrounds.

{research_ctx}

HOOK TYPE: {hook_type}
{HOOK_DESCRIPTIONS[hook_type]}

{style_instructions}

{structure}

{LAYOUT_SCHEMA}

Generate a SHORT-FORM script (30-60 seconds, vertical 9:16).

RULES:
- Speak to shoppers considering a purchase, NOT affiliate marketers
- NEVER mention commission rates, EPC, hop conversion, promoting, or earning as an affiliate
- First 2 seconds: extremely compelling hook text
- Visual changes every 1-1.5 seconds
- Each text segment: 3-8 words MAX
- End with a helpful CTA to check price/details if the product fits their needs
- Include emoji strategically
- For honest/trust styles: include at least ONE con or limitation
- Use research-based language ("reviewers say", "specs show", "data proves")

Return JSON:
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
            "text": "<text overlay>",
            "text_style": "<headline_bold|subtitle|accent_pop|cta_button|stat_number|question|pro_point|con_point|verdict|elimination>",
            "text_color": "<hex>",
            "bg_color": "<hex>",
            "animation": "<pop_in|slide_up|fade_in|zoom_in|shake|typewriter|bounce>",
            "transition_to_next": "<cut|whip_pan|fade|zoom_through|glitch>",
            "visual_note": "<background description>"
        }}
    ],
    "cta_text": "<call to action>",
    "cta_placement": "<end_screen|pinned_comment|link_in_bio>"
}}

Generate 12-20 segments. Return ONLY valid JSON."""

    return _call_llm(prompt)


def generate_long_form_script(product_info: dict, hook_type: str, content_style: str = None) -> dict:
    if content_style is None:
        content_style = product_info.get("content_style", DEFAULT_CONTENT_STYLE)
    content_style = normalize_content_style(content_style)
    product_info = {**product_info, "content_style": content_style}

    research_ctx = _build_research_context(product_info)
    style_instructions = _get_style_instructions(content_style)

    # Build structure based on content style
    if content_style == "elimination":
        structure = """STRUCTURE:
1. Hook (0-5s): "I tested X products. Most were garbage."
2. The Lineup (5-30s): Show all contenders
3. Elimination Rounds (30s-5min): Eliminate products one by one with specific reasons
4. The Winner (5-6min): Reveal and detail the surviving product (with honest pros AND cons)
5. Verdict + CTA (6-7min): Clear recommendation with link to check price/details"""
    elif content_style == "worth_it_or_waste":
        structure = """STRUCTURE:
1. Hook (0-5s): "Is [Product] actually worth the hype?"
2. The Claims (5-30s): What the marketing promises
3. Claim vs Reality (30s-5min): Test each claim against review data
4. The Verdict (5-6min): Worth It or Waste? With specific reasoning
5. Who Should Buy + CTA (6-7min): Specific use cases + link to check details"""
    elif content_style == "vs_battle":
        structure = """STRUCTURE:
1. Hook (0-5s): "[Product A] vs [Product B] — only one survives"
2. Meet the Contenders (5-30s): Brief intro of both
3. Round-by-Round (30s-5min): Compare spec by spec (price, features, reviews, build, value)
4. Scorecard (5-6min): Tally the wins
5. The Winner + CTA (6-7min): Clear recommendation + link to check details"""
    elif content_style == "budget_challenge":
        structure = """STRUCTURE:
1. Hook (0-5s): "Best [category] under $[price]?"
2. The Contenders (5-30s): Show all budget options
3. Breakdown (30s-5min): Review each option's value proposition
4. The Winner (5-6min): Crown the budget champion
5. CTA (6-7min): Where to check the best option + link in description"""
    else:  # honest_review or standard
        structure = """STRUCTURE:
1. Hook (0-5s): Compelling opening
2. Intro (5-15s): What this video covers
3. The Good (15s-2.5min): Key features and genuine strengths (with review evidence)
4. The Bad (2.5-4min): Honest limitations and cons (with review evidence)
5. Who It's For / Not For (4-5.5min): Specific use case matching
6. Verdict (5.5-6.5min): Clear, honest recommendation
7. CTA (6.5-7min): Help viewers check price/details if the product fits their needs"""

    prompt = f"""You are an expert YouTube scriptwriter creating honest, buyer-focused product review videos for everyday consumers. FACELESS TEXT-ONLY videos with animated text overlays.

{research_ctx}

HOOK TYPE: {hook_type}
{HOOK_DESCRIPTIONS[hook_type]}

{style_instructions}

{structure}

{LAYOUT_SCHEMA}

Generate a LONG-FORM script (5-8 minutes, 16:9 landscape).

RULES:
- Speak to shoppers considering a purchase, NOT affiliate marketers
- NEVER mention commission rates, EPC, hop conversion, promoting, or earning as an affiliate
- Each text segment: 5-15 words
- Visual changes every 3-5 seconds
- Pattern interrupts every 15-20 seconds (visual change, question, stat)
- Mix styles: headlines, bullets, stats, questions, pros, cons
- Include engagement trigger questions that encourage comments
- Use research-based language throughout
- For trust-based styles: dedicate real screen time to cons/limitations

Return JSON:
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
                    "text": "<text overlay>",
                    "text_style": "<headline_bold|subtitle|accent_pop|cta_button|stat_number|question|pro_point|con_point|verdict|elimination|comparison|scorecard>",
                    "text_color": "<hex>",
                    "bg_color": "<hex>",
                    "animation": "<pop_in|slide_up|slide_left|fade_in|zoom_in|shake|typewriter|bounce|wipe>",
                    "transition_to_next": "<cut|whip_pan|fade|zoom_through|glitch|dissolve>",
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

Generate 60-100+ segments across 5-7 chapters. Return ONLY valid JSON."""

    return _call_llm(prompt)


def generate_selected_scripts(product_info: dict, hook_type: str,
                              formats: list = None, content_style: str = None) -> dict:
    if formats is None:
        formats = ["short_form", "long_form"]
    if content_style is None:
        content_style = product_info.get("content_style", DEFAULT_CONTENT_STYLE)
    content_style = normalize_content_style(content_style)
    product_info = {**product_info, "content_style": content_style}

    result = {"product_info": product_info, "hook_type": hook_type,
              "content_style": content_style, "scripts": {}}
    if "short_form" in formats:
        result["scripts"]["short_form"] = generate_short_form_script(product_info, hook_type, content_style)
    if "long_form" in formats:
        result["scripts"]["long_form"] = generate_long_form_script(product_info, hook_type, content_style)
    return result
