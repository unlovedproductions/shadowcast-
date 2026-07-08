"""Audio mood resolution + API request field defaults."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from audio_options import resolve_audio_mood, VALID_AUDIO_MOODS, MOOD_TEMPO


def test_valid_moods():
    assert "chill" in VALID_AUDIO_MOODS
    assert "energetic" in VALID_AUDIO_MOODS
    assert "dramatic" in VALID_AUDIO_MOODS
    assert "minimal" in VALID_AUDIO_MOODS


def test_explicit_mood_wins():
    assert resolve_audio_mood("dramatic", "honest_review", "short_form") == "dramatic"
    assert resolve_audio_mood("minimal", "vs_battle", "long_form") == "minimal"


def test_auto_falls_back_to_content_style():
    assert resolve_audio_mood(None, "honest_review", "short_form") == "chill"
    assert resolve_audio_mood("auto", "vs_battle", "short_form") == "energetic"
    assert resolve_audio_mood("", "elimination", "long_form") == "dramatic"


def test_mood_tempo_map():
    assert MOOD_TEMPO["energetic"] == 120
    assert MOOD_TEMPO["chill"] == 80
