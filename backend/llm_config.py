"""
LLM Configuration Module — local-first (Ollama default).
Supports Ollama, LM Studio, custom OpenAI-compatible endpoints, and optional OpenAI API.
"""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass


PROVIDER_PRESETS = {
    "ollama": {
        "name": "Ollama (Local — FREE)",
        "base_url": "http://localhost:11434/v1",
        "default_model": "qwen2.5:14b-instruct-q5_K_M",
        "api_key_required": False,
        "description": "Ollama local LLM. Default for ShadowCast. Recommended: Qwen2.5-14B for RTX 3080 16GB.",
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
        "description": "Any local OpenAI-compatible API endpoint (vLLM, text-generation-webui, etc.).",
    },
    "openai": {
        "name": "OpenAI API (optional cloud)",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4.1-mini",
        "api_key_required": True,
        "description": "Optional cloud API. Requires an API key. ~$0.02 per video.",
    },
}

PROVIDER_DEFAULTS = {
    "openai": {"temperature": 0.4, "max_tokens": 4096, "timeout": 120.0, "json_retries": 2},
    "ollama": {"temperature": 0.3, "max_tokens": 8192, "timeout": 300.0, "json_retries": 2},
    "lmstudio": {"temperature": 0.3, "max_tokens": 8192, "timeout": 300.0, "json_retries": 2},
    "custom": {"temperature": 0.4, "max_tokens": 4096, "timeout": 180.0, "json_retries": 2},
}

_JSON_MODE_PROVIDERS = frozenset({"openai"})


@dataclass
class LLMConfig:
    provider: str = "ollama"
    api_key: str = ""
    base_url: str = ""
    model: str = ""

    def __post_init__(self):
        preset = PROVIDER_PRESETS.get(self.provider, PROVIDER_PRESETS["ollama"])
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


def get_provider_defaults(provider: str) -> dict:
    return PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["ollama"])


def supports_json_response_format(provider: str) -> bool:
    return provider in _JSON_MODE_PROVIDERS


def _config_from_env() -> LLMConfig:
    provider = os.getenv("LLM_PROVIDER", "ollama").strip() or "ollama"
    base_url = os.getenv("LLM_BASE_URL", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    return LLMConfig(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        model=model,
    )


_current_config = _config_from_env()


def get_config() -> LLMConfig:
    return _current_config


def set_config(provider: str = "ollama", api_key: str = "", base_url: str = "", model: str = ""):
    global _current_config
    _current_config = LLMConfig(provider=provider, api_key=api_key, base_url=base_url, model=model)
    return _current_config


def _strip_markdown_fences(text: str) -> str:
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.I)
    if fenced:
        return fenced.group(1).strip()
    return text.strip()


def _remove_trailing_commas(text: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", text)


def parse_llm_json(text: str) -> dict:
    if not isinstance(text, str):
        return {"__raw": text}

    cleaned = _strip_markdown_fences(text.strip())
    candidates = [cleaned, _remove_trailing_commas(cleaned)]

    for candidate in candidates:
        try:
            result = json.loads(candidate)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, TypeError):
            pass

    m = re.search(r"(\{[\s\S]*\})", cleaned)
    if m:
        blob = m.group(1)
        for candidate in (blob, _remove_trailing_commas(blob)):
            try:
                result = json.loads(candidate)
                if isinstance(result, dict):
                    return result
            except (json.JSONDecodeError, TypeError):
                pass

    return {"__raw": text}
