"""
Script Generator Module — Trust-Based Honest Review Edition
Generates scripts using AI research (specs, reviews, comparisons) so you
never need to physically buy or test products.
"""

from content_styles import (
    CONTENT_STYLES,
    DEFAULT_CONTENT_STYLE,
    normalize_content_style,
)
from llm_client import chat_completion_json
from prompts import (
    BUYER_FOCUS_RULES,
    LAYOUT_SCHEMA,
    SCRIPT_SYSTEM_PROMPT,
    build_research_context,
    long_form_json_schema,
    short_form_json_schema,
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


def _call_llm(system: str, user: str, required_keys: list[str] | None = None) -> dict:
    return chat_completion_json(system, user, required_keys=required_keys)


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
    else:
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

    user_prompt = f"""Create a SHORT-FORM YouTube script (30-60 seconds, vertical 9:16).
FACELESS TEXT-ONLY video — animated text overlays on dynamic backgrounds.

{build_research_context(product_info)}

HOOK TYPE: {hook_type}
{HOOK_DESCRIPTIONS[hook_type]}

{_get_style_instructions(content_style)}

{_get_short_form_structure(content_style)}

{LAYOUT_SCHEMA}

SHORT-FORM RULES:
- First 2 seconds: extremely compelling hook text
- Visual changes every 1-1.5 seconds
- Each text segment: 3-8 words MAX
- End with a helpful CTA to check price/details if the product fits their needs
- Include emoji strategically

{BUYER_FOCUS_RULES}

{short_form_json_schema(hook_type, content_style)}"""

    return _call_llm(SCRIPT_SYSTEM_PROMPT, user_prompt, required_keys=["segments"])


def generate_long_form_script(product_info: dict, hook_type: str, content_style: str = None) -> dict:
    if content_style is None:
        content_style = product_info.get("content_style", DEFAULT_CONTENT_STYLE)
    content_style = normalize_content_style(content_style)
    product_info = {**product_info, "content_style": content_style}

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
    else:
        structure = """STRUCTURE:
1. Hook (0-5s): Compelling opening
2. Intro (5-15s): What this video covers
3. The Good (15s-2.5min): Key features and genuine strengths (with review evidence)
4. The Bad (2.5-4min): Honest limitations and cons (with review evidence)
5. Who It's For / Not For (4-5.5min): Specific use case matching
6. Verdict (5.5-6.5min): Clear, honest recommendation
7. CTA (6.5-7min): Help viewers check price/details if the product fits their needs"""

    user_prompt = f"""Create a LONG-FORM YouTube script (5-8 minutes, 16:9 landscape).
FACELESS TEXT-ONLY video with animated text overlays.

{build_research_context(product_info)}

HOOK TYPE: {hook_type}
{HOOK_DESCRIPTIONS[hook_type]}

{_get_style_instructions(content_style)}

{structure}

{LAYOUT_SCHEMA}

LONG-FORM RULES:
- Each text segment: 5-15 words
- Visual changes every 3-5 seconds
- Pattern interrupts every 15-20 seconds (visual change, question, stat)
- Mix styles: headlines, bullets, stats, questions, pros, cons
- Include engagement trigger questions that encourage comments
- For trust-based styles: dedicate real screen time to cons/limitations

{BUYER_FOCUS_RULES}

{long_form_json_schema(hook_type, content_style)}"""

    return _call_llm(SCRIPT_SYSTEM_PROMPT, user_prompt, required_keys=["chapters"])


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
