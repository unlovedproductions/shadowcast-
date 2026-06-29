"""
LLM Configuration Module
Supports OpenAI API, Ollama, LM Studio, and any OpenAI-compatible API.

─── LOCAL LLM RECOMMENDATIONS FOR RAZER BLADE 15 ADVANCED ───
Your specs: RTX 3080 (16GB VRAM), 32GB DDR4, i9-11900H, CUDA 8.6

TIER 1 — BEST QUALITY (fits in 16GB VRAM):
  • Qwen2.5-14B-Instruct (Q5_K_M) — ~12GB VRAM
    Best overall for script generation. Excellent instruction following,
    strong creative writing, handles JSON output well.
    Ollama: ollama pull qwen2.5:14b-instruct-q5_K_M

  • Mistral-Nemo-12B-Instruct (Q5_K_M) — ~10GB VRAM
    Great balance of speed and quality. Good at structured output.
    Ollama: ollama pull mistral-nemo:12b-instruct-q5_K_M

TIER 2 — FAST + GOOD (leaves VRAM headroom):
  • Llama-3.1-8B-Instruct (Q6_K) — ~7GB VRAM
    Fast inference, good quality. Leaves room for other apps.
    Ollama: ollama pull llama3.1:8b-instruct-q6_K

  • Phi-3.5-Mini-Instruct (Q6_K) — ~4GB VRAM
    Surprisingly capable for its size. Ultra-fast on your GPU.
    Ollama: ollama pull phi3.5:3.8b-mini-instruct-q6_K

TIER 3 — MAXIMUM QUALITY (uses VRAM + RAM offload, slower):
  • Qwen2.5-32B-Instruct (Q4_K_M) — ~20GB (16GB VRAM + 4GB RAM offload)
    Best possible quality. Will use GPU + CPU offload. Slower but
    produces the most polished scripts. Good for final production runs.
    Ollama: ollama pull qwen2.5:32b-instruct-q4_K_M

  • DeepSeek-V2-Lite (Q4_K_M) — MoE model, fits partially in VRAM
    Ollama: ollama pull deepseek-v2:lite

RECOMMENDED SETUP:
  1. Install Ollama: https://ollama.com/download
  2. Pull your model: ollama pull qwen2.5:14b-instruct-q5_K_M
  3. In the app Settings, select "Ollama" and set model to "qwen2.5:14b-instruct-q5_K_M"
  4. For batch jobs (many products), use the 8B model for speed.
  5. For single high-quality videos, use the 14B or 32B model.
"""

import os
import json
import re
from dataclasses import dataclass
from openai import OpenAI


# ── Provider Presets ───────────────────────────────────────────────────
PROVIDER_PRESETS = {
    "openai": {
        "name": "OpenAI API",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4.1-mini",
        "api_key_required": True,
        "description": "OpenAI cloud API. Requires an API key. ~$0.02 per video.",
    },
    "ollama": {
        "name": "Ollama (Local — FREE)",
        "base_url": "http://localhost:11434/v1",
        "default_model": "qwen2.5:14b-instruct-q5_K_M",
        "api_key_required": False,
        "description": "Ollama local LLM. FREE. Recommended: Qwen2.5-14B for your RTX 3080 16GB.",
        "recommended_models": [
            {"name": "qwen2.5:14b-instruct-q5_K_M", "vram": "~12GB", "quality": "Best", "speed": "Medium"},
            {"name": "mistral-nemo:12b-instruct-q5_K_M", "vram": "~10GB", "quality": "Great", "speed": "Fast"},
            {"name": "llama3.1:8b-instruct-q6_K", "vram": "~7GB", "quality": "Good", "speed": "Very Fast"},
            {"name": "phi3.5:3.8b-mini-instruct-q6_K", "vram": "~4GB", "quality": "Decent", "speed": "Ultra Fast"},
            {"name": "qwen2.5:32b-instruct-q4_K_M", "vram": "~20GB*", "quality": "Premium", "speed": "Slow"},
        ],
    },
    "lmstudio": {
        "name": "LM Studio (Local — FREE)",
        "base_url": "http://localhost:1234/v1",
        "default_model": "local-model",
        "api_key_required": False,
        "description": "LM Studio local LLM with GUI. FREE. Download models through the app.",
        "recommended_models": [
            {"name": "Qwen2.5-14B-Instruct-GGUF (Q5_K_M)", "vram": "~12GB", "quality": "Best", "speed": "Medium"},
            {"name": "Mistral-Nemo-12B-Instruct-GGUF (Q5_K_M)", "vram": "~10GB", "quality": "Great", "speed": "Fast"},
            {"name": "Meta-Llama-3.1-8B-Instruct-GGUF (Q6_K)", "vram": "~7GB", "quality": "Good", "speed": "Very Fast"},
        ],
    },
    "custom": {
        "name": "Custom OpenAI-Compatible",
        "base_url": "http://localhost:8000/v1",
        "default_model": "custom-model",
        "api_key_required": False,
        "description": "Any OpenAI-compatible API endpoint (vLLM, text-generation-webui, etc.).",
    },
}


@dataclass
class LLMConfig:
    provider: str = "openai"
    api_key: str = ""
    base_url: str = ""
    model: str = ""

    def __post_init__(self):
        preset = PROVIDER_PRESETS.get(self.provider, PROVIDER_PRESETS["openai"])
        if not self.base_url:
            self.base_url = preset["base_url"]
        if not self.model:
            self.model = preset["default_model"]
        if not self.api_key:
            self.api_key = os.environ.get("OPENAI_API_KEY", "")
        if not self.api_key and not preset["api_key_required"]:
            self.api_key = "not-needed"

    def get_client(self) -> OpenAI:
        return OpenAI(api_key=self.api_key, base_url=self.base_url)


# Global config instance (mutable at runtime via API)
_current_config = LLMConfig()


def get_config() -> LLMConfig:
    return _current_config


def set_config(provider: str = "openai", api_key: str = "", base_url: str = "", model: str = ""):
    global _current_config
    _current_config = LLMConfig(provider=provider, api_key=api_key, base_url=base_url, model=model)
    return _current_config


def parse_llm_json(text: str) -> dict:
    """
    Robustly parse JSON returned by an LLM. LLM outputs sometimes include
    explanation text surrounding JSON blobs; try to recover a JSON object
    by first attempting a direct load, then falling back to extracting the
    first {...} substring.
    Returns a dict (may contain a '__raw' key if parsing failed).
    """
    if not isinstance(text, str):
        return {"__raw": text}

    try:
        return json.loads(text)
    except Exception:
        # Attempt to extract a JSON object substring
        m = re.search(r"(\{.*\})", text, re.S)
        if m:
            candidate = m.group(1)
            try:
                return json.loads(candidate)
            except Exception:
                pass
        # Fallback: return the raw text so callers can decide how to proceed
        return {"__raw": text}

# BEGIN UNLOVED_FORCE_OLLAMA_CONFIG
#
# Local Unloved Stack override:
# ShadowCast was reporting OpenAI from /api/providers even when .env contained
# Ollama settings. This wrapper forces get_config() to respect the local Ollama
# runtime unless explicit env values say otherwise.
#
try:
    _unloved_original_get_config = get_config

    def get_config():
        import os

        cfg = _unloved_original_get_config()

        provider = os.getenv("LLM_PROVIDER", "ollama") or "ollama"
        base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1") or "http://localhost:11434/v1"
        model = os.getenv("LLM_MODEL", "qwen2.5:14b-instruct-q5_K_M") or "qwen2.5:14b-instruct-q5_K_M"
        api_key = os.getenv("OPENAI_API_KEY", "not-needed") or "not-needed"

        def set_value(target, key, value):
            if isinstance(target, dict):
                target[key] = value
            else:
                try:
                    setattr(target, key, value)
                except Exception:
                    pass

        # Common names used by ShadowCast config/client code.
        for key, value in {
            "provider": provider,
            "llm_provider": provider,
            "base_url": base_url,
            "llm_base_url": base_url,
            "model": model,
            "llm_model": model,
            "api_key": api_key,
            "openai_api_key": api_key,
        }.items():
            set_value(cfg, key, value)

        return cfg

except NameError:
    pass
# END UNLOVED_FORCE_OLLAMA_CONFIG
