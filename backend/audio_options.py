"""Audio mood options shared by API, renderer, and Mission Control."""

MOOD_SETTINGS_KEYS = ("chill", "energetic", "dramatic", "minimal")
VALID_AUDIO_MOODS = frozenset(MOOD_SETTINGS_KEYS)

MOOD_TEMPO = {
    "chill": 80,
    "energetic": 120,
    "dramatic": 110,
    "minimal": 60,
}

_STYLE_ALIASES = {
    "elimination_round": "elimination",
    "trust_first_review": "honest_review",
    "standard_promo": "standard",
}


def mood_for_content_style(content_style: str, fmt: str = "short_form") -> str:
    """Default background mood from content style + format."""
    style = (content_style or "").strip().lower()
    style = _STYLE_ALIASES.get(style, style)
    if fmt == "long_form":
        if style in ("vs_battle", "elimination"):
            return "dramatic"
        if style in ("honest_review", "worth_it_or_waste"):
            return "chill"
        if style == "budget_challenge":
            return "energetic"
        return "energetic"
    if style in ("vs_battle", "elimination", "budget_challenge"):
        return "energetic"
    if style in ("honest_review", "worth_it_or_waste"):
        return "chill"
    return "energetic"


def resolve_audio_mood(audio_mood: str | None, content_style: str, fmt: str = "short_form") -> str:
    """Use explicit mood when valid; otherwise infer from content style + format."""
    if audio_mood and audio_mood in VALID_AUDIO_MOODS:
        return audio_mood
    return mood_for_content_style(content_style, fmt)
