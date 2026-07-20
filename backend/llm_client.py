"""Provider-aware LLM chat completion with JSON mode and retry logic."""

import json
import urllib.error
import urllib.request
from typing import Any, Callable, Optional

from llm_config import get_config, get_provider_defaults, parse_llm_json, supports_json_response_format


def _strip_json_instruction(user: str, for_local: bool) -> str:
    if not for_local:
        return user
    suffix = (
        "\n\nIMPORTANT: Respond with ONLY a valid JSON object. "
        "No markdown code fences. No text before or after the JSON."
    )
    if suffix.strip() in user:
        return user
    return user + suffix


def chat_completion(
    system: str,
    user: str,
    *,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    json_mode: bool = True,
    timeout: Optional[float] = None,
) -> str:
    cfg = get_config()
    defaults = get_provider_defaults(cfg.provider)
    client = cfg.get_client()

    temp = temperature if temperature is not None else defaults["temperature"]
    tokens = max_tokens if max_tokens is not None else defaults["max_tokens"]
    req_timeout = timeout if timeout is not None else defaults["timeout"]

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    user_content = _strip_json_instruction(user, json_mode and not supports_json_response_format(cfg.provider))
    messages.append({"role": "user", "content": user_content})

    kwargs: dict[str, Any] = {
        "model": cfg.model,
        "messages": messages,
        "temperature": temp,
        "max_tokens": tokens,
        "timeout": req_timeout,
    }
    if json_mode and supports_json_response_format(cfg.provider):
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    return getattr(response.choices[0].message, "content", "") or ""


def chat_completion_json(
    system: str,
    user: str,
    *,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    max_retries: Optional[int] = None,
    required_keys: Optional[list[str]] = None,
    timeout: Optional[float] = None,
    validate_fn: Optional[Callable[[dict], bool]] = None,
) -> dict:
    cfg = get_config()
    defaults = get_provider_defaults(cfg.provider)
    retries = max_retries if max_retries is not None else defaults["json_retries"]
    temp = temperature if temperature is not None else defaults["temperature"]

    last_parsed: dict = {"__raw": ""}
    for attempt in range(retries + 1):
        attempt_temp = temp if attempt == 0 else max(0.1, temp - 0.15 * attempt)
        content = chat_completion(
            system,
            user,
            temperature=attempt_temp,
            max_tokens=max_tokens,
            json_mode=True,
            timeout=timeout,
        )
        parsed = parse_llm_json(content)
        last_parsed = parsed

        if "__raw" in parsed and len(parsed) == 1:
            continue
        if required_keys and not all(k in parsed for k in required_keys):
            continue
        if validate_fn is not None and not validate_fn(parsed):
            continue
        return parsed

    return last_parsed


def test_chat_completion(timeout: float = 10.0) -> tuple[bool, str, Optional[str]]:
    """Run a minimal chat completion to validate the LLM works end-to-end."""
    cfg = get_config()
    try:
        content = chat_completion(
            "You are a health check assistant.",
            'Reply with exactly: {"status":"ok"}',
            temperature=0.0,
            max_tokens=32,
            json_mode=True,
            timeout=timeout,
        )
        parsed = parse_llm_json(content)
        if isinstance(parsed, dict) and parsed.get("status") == "ok":
            return True, "", content[:200]
        if "ok" in content.lower():
            return True, "", content[:200]
        return False, f"Unexpected test response: {content[:200]}", content[:200]
    except Exception as exc:
        return False, str(exc), None


def list_ollama_models(base_url: str = "http://localhost:11434", timeout: float = 4.0) -> list[str]:
    """Discover models via Ollama native /api/tags endpoint."""
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3]
    url = f"{root}/api/tags"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
        models = []
        for item in data.get("models", []):
            name = item.get("name") or item.get("model")
            if name:
                models.append(name)
        return sorted(models)
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError):
        return []


def list_openai_compatible_models(timeout: float = 4.0) -> list[str]:
    """List models from OpenAI-compatible /v1/models endpoint."""
    cfg = get_config()
    base_url = (cfg.base_url or "").rstrip("/")
    if not base_url:
        return []
    headers = {}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"
    try:
        req = urllib.request.Request(f"{base_url}/models", headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
        models = []
        for item in data.get("data", []):
            model_id = item.get("id")
            if model_id:
                models.append(model_id)
        return sorted(models)
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, TimeoutError):
        return []
