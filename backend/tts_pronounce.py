"""TTS pronunciation prep — plain-text lexicon (SSML-semantic, provider-safe).

ShadowCast providers (Kokoro, Piper, gTTS, OpenAI tts-1) take plain text, not SSML.
We honor W3C <sub alias> / <phoneme> intent by expanding to speakable text before synth.
"""

from __future__ import annotations

import json
import os
import re
from typing import Mapping

# <sub alias="foo">bar</sub> → foo (W3C substitution semantics)
_SUB_ALIAS_RE = re.compile(
    r'<sub\s+alias=["\']([^"\']+)["\'][^>]*>(.*?)</sub>',
    re.IGNORECASE | re.DOTALL,
)
_PHONEME_RE = re.compile(
    r"<phoneme\b[^>]*>(.*?)</phoneme>",
    re.IGNORECASE | re.DOTALL,
)
_SSML_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")
# Model / SKU tokens: A40, XM5, WF-1000XM5-ish letter+digit runs
_SKU_TOKEN_RE = re.compile(r"\b([A-Za-z]{1,8})[-_]?(\d{1,5}[A-Za-z0-9]{0,4})\b")
_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "]+",
    flags=re.UNICODE,
)


def _env_aliases() -> dict[str, str]:
    raw = (os.getenv("SHADOWCAST_TTS_PRONUNCIATIONS") or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in data.items():
        src = str(key or "").strip()
        dst = str(value or "").strip()
        if src and dst:
            out[src] = dst
    return out


def strip_ssml_to_speakable(text: str) -> str:
    """Map common SSML pronunciation tags to plain speech; drop other markup."""
    out = str(text or "")
    out = _SUB_ALIAS_RE.sub(r"\1", out)
    out = _PHONEME_RE.sub(r"\1", out)
    out = _SSML_TAG_RE.sub("", out)
    return out


def sku_token_to_speakable(token: str) -> str:
    """Split letter/digit SKU so TTS says 'A 40' instead of 'ayforty'."""
    m = _SKU_TOKEN_RE.fullmatch(str(token or "").strip())
    if not m:
        return str(token or "")
    letters, rest = m.group(1), m.group(2)
    # Keep long numeric bodies intact (1000) but space letter↔digit boundary.
    rest_spaced = re.sub(r"([A-Za-z]+)(\d+)", r"\1 \2", rest)
    rest_spaced = re.sub(r"(\d+)([A-Za-z]+)", r"\1 \2", rest_spaced)
    return f"{letters} {rest_spaced}".strip()


def expand_inline_skus(text: str) -> str:
    def _repl(match: re.Match[str]) -> str:
        return sku_token_to_speakable(match.group(0))

    return _SKU_TOKEN_RE.sub(_repl, text)


def prepare_tts_text(
    text: str,
    *,
    provider: str = "auto",
    aliases: Mapping[str, str] | None = None,
    product_names: list[str] | None = None,
) -> str:
    """
    Provider-aware speakable text.

    All current providers use plain text. `provider` is reserved for future
    SSML-capable engines; today everyone gets lexicon expansion + SSML strip.
    """
    del provider  # plain-text path for kokoro/piper/gtts/openai tts-1
    out = strip_ssml_to_speakable(text)
    out = _EMOJI_RE.sub("", out)

    merged: dict[str, str] = dict(_env_aliases())
    if aliases:
        for key, value in aliases.items():
            src = str(key or "").strip()
            dst = str(value or "").strip()
            if src and dst:
                merged[src] = dst

    # Longest keys first so "Space A40" wins over "A40"
    for src in sorted(merged.keys(), key=len, reverse=True):
        out = re.sub(re.escape(src), merged[src], out, flags=re.IGNORECASE)

    for name in product_names or []:
        name = str(name or "").strip()
        if not name:
            continue
        speakable = expand_inline_skus(name)
        if speakable != name:
            out = re.sub(re.escape(name), speakable, out, flags=re.IGNORECASE)

    out = expand_inline_skus(out)
    out = out.replace("&", " and ")
    out = re.sub(r"\s+", " ", out).strip()
    return out
