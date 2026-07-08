"""Canonical content style keys, aliases, and helpers."""

CONTENT_STYLES = {
    "honest_review": {
        "name": "Honest Review (Trust Builder)",
        "description": "Balanced pros AND cons. Includes 'Who This Is NOT For' section. Builds trust by being transparent about limitations.",
        "tone": "honest, balanced, trustworthy",
    },
    "elimination": {
        "name": "Elimination Round",
        "description": "Start by showing products you REJECTED and why, then reveal the winner. Builds massive credibility.",
        "tone": "critical, analytical, authoritative",
    },
    "worth_it_or_waste": {
        "name": "Worth It or Waste?",
        "description": "Series format. Test a hyped product against its claims. Verdict: Worth It or Waste of Money?",
        "tone": "investigative, fair, entertaining",
    },
    "budget_challenge": {
        "name": "Budget Challenge",
        "description": "Find the best product under a specific price. 'The $50 Challenge' format. Perfect for budget-conscious audiences.",
        "tone": "enthusiastic, value-focused, relatable",
    },
    "vs_battle": {
        "name": "VS Battle (Comparison)",
        "description": "Side-by-side comparison of two products. Spec-by-spec breakdown. Clear winner declared.",
        "tone": "analytical, fair, decisive",
    },
    "standard": {
        "name": "Standard Promo",
        "description": "Classic affiliate promotion. Features, benefits, CTA. Good for straightforward product showcases.",
        "tone": "enthusiastic, persuasive, energetic",
    },
}

DEFAULT_CONTENT_STYLE = "honest_review"

STYLE_ALIASES = {
    "elimination_round": "elimination",
    "trust_first_review": "honest_review",
    "standard_promo": "standard",
}

STYLE_BADGES = {
    "honest_review": "HONEST REVIEW",
    "elimination": "ELIMINATION",
    "worth_it_or_waste": "WORTH IT?",
    "budget_challenge": "BUDGET PICK",
    "vs_battle": "VS BATTLE",
}

SERIES_NAMES = {
    "worth_it_or_waste": "Worth It or Waste?",
    "elimination": "Elimination Round",
    "vs_battle": "VS Battle",
    "budget_challenge": "Budget Challenge",
    "honest_review": "Honest Review",
    "standard": "Product Review",
}


def normalize_content_style(value: str) -> str:
    if not value:
        return DEFAULT_CONTENT_STYLE
    key = str(value).strip().lower()
    key = STYLE_ALIASES.get(key, key)
    if key in CONTENT_STYLES:
        return key
    return DEFAULT_CONTENT_STYLE


def style_badge_text(style: str):
    return STYLE_BADGES.get(normalize_content_style(style))


def style_requires_competitors(style: str) -> bool:
    return normalize_content_style(style) in ("vs_battle", "elimination")


def human_style_name(style: str) -> str:
    info = CONTENT_STYLES.get(normalize_content_style(style), CONTENT_STYLES[DEFAULT_CONTENT_STYLE])
    return info["name"]


def series_name_for_style(style: str) -> str:
    return SERIES_NAMES.get(normalize_content_style(style), SERIES_NAMES["honest_review"])
