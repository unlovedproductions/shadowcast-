"""Provider-aware LLM chat completion with JSON mode, retry, fallback, and telemetry."""

from __future__ import annotations

import os
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Optional, Union

from llm_config import (
    LLMConfig,
    get_config,
    get_provider_defaults,
    parse_llm_json,
    supports_json_response_format,
)
from llm_context import append_llm_call, get_job_id
from llm_telemetry import build_call_record, job_budget_exceeded, record_job_chars

ValidateFn = Callable[[dict], Union[bool, tuple[bool, list[str]]]]

_FALLBACK_CHAIN = [
    part.strip()
    for part in os.getenv("LLM_FALLBACK_CHAIN", "ollama,lmstudio,openai").split(",")
    if part.strip()
]


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


def _normalize_validate_result(result: Union[bool, tuple[bool, list[str]]]) -> tuple[bool, list[str]]:
    if isinstance(result, tuple):
        ok = bool(result[0])
        errors = list(result[1]) if len(result) > 1 and result[1] else []
        return ok, errors
    return bool(result), []


def _provider_attempt_order() -> list[str]:
    cfg = get_config()
    order = [cfg.provider]
    for provider in _FALLBACK_CHAIN:
        if provider not in order:
            order.append(provider)
    return order


def _config_for_provider(provider: str, base: LLMConfig) -> LLMConfig:
    return LLMConfig(
        provider=provider,
        api_key=base.api_key,
        base_url=base.base_url if provider == base.provider else "",
        model=base.model if provider == base.provider else "",
    )


def chat_completion(
    system: str,
    user: str,
    *,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    json_mode: bool = True,
    timeout: Optional[float] = None,
    call_label: str = "chat_completion",
    record_telemetry: bool = True,
) -> str:
    job_id = get_job_id()
    if job_id:
        exceeded, message = job_budget_exceeded(job_id)
        if exceeded:
            raise RuntimeError(message)

    original = get_config()
    last_error = "LLM request failed"
    fallback_used = False

    for index, provider in enumerate(_provider_attempt_order()):
        active = _config_for_provider(provider, original)
        if index > 0:
            fallback_used = True
        defaults = get_provider_defaults(active.provider)
        client = active.get_client()

        temp = temperature if temperature is not None else defaults["temperature"]
        tokens = int(max_tokens if max_tokens is not None else defaults["max_tokens"])
        req_timeout = timeout if timeout is not None else defaults["timeout"]

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        user_content = _strip_json_instruction(
            user,
            json_mode and not supports_json_response_format(active.provider),
        )
        messages.append({"role": "user", "content": user_content})

        kwargs: dict[str, Any] = {
            "model": active.model,
            "messages": messages,
            "temperature": temp,
            "max_tokens": tokens,
            "timeout": req_timeout,
        }
        if json_mode and supports_json_response_format(active.provider):
            kwargs["response_format"] = {"type": "json_object"}

        started = time.perf_counter()
        try:
            response = client.chat.completions.create(**kwargs)
            content = getattr(response.choices[0].message, "content", "") or ""
            latency_ms = (time.perf_counter() - started) * 1000
            sizes = {"prompt_chars": len(system or "") + len(user or ""), "response_chars": len(content)}
            if job_id:
                record_job_chars(job_id, sizes["prompt_chars"], sizes["response_chars"])
            if record_telemetry:
                append_llm_call(
                    build_call_record(
                        call_label=call_label,
                        provider=active.provider,
                        model=active.model,
                        latency_ms=latency_ms,
                        prompt_chars=sizes["prompt_chars"],
                        response_chars=sizes["response_chars"],
                        parse_ok=True,
                        retry_index=0,
                        validator_pass=None,
                        validator_errors=[],
                        fallback_used=fallback_used,
                    )
                )
            return content
        except Exception as exc:
            last_error = str(exc)
            latency_ms = (time.perf_counter() - started) * 1000
            if record_telemetry:
                append_llm_call(
                    build_call_record(
                        call_label=call_label,
                        provider=active.provider,
                        model=active.model,
                        latency_ms=latency_ms,
                        prompt_chars=len(system or "") + len(user or ""),
                        response_chars=0,
                        parse_ok=False,
                        retry_index=0,
                        validator_pass=None,
                        validator_errors=[],
                        fallback_used=fallback_used,
                        error=last_error,
                    )
                )
            continue

    raise RuntimeError(last_error)


def chat_completion_json(
    system: str,
    user: str,
    *,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    max_retries: Optional[int] = None,
    required_keys: Optional[list[str]] = None,
    timeout: Optional[float] = None,
    validate_fn: Optional[ValidateFn] = None,
    call_label: str = "chat_completion_json",
) -> dict:
    cfg = get_config()
    defaults = get_provider_defaults(cfg.provider)
    retries = max_retries if max_retries is not None else defaults["json_retries"]
    temp = temperature if temperature is not None else defaults["temperature"]

    last_parsed: dict = {"__raw": ""}
    last_validator_errors: list[str] = []

    for attempt in range(retries + 1):
        attempt_temp = temp if attempt == 0 else max(0.1, temp - 0.15 * attempt)
        started = time.perf_counter()
        content = ""
        parse_ok = False
        validator_pass: Optional[bool] = None
        validator_errors: list[str] = []
        provider = cfg.provider
        model = cfg.model
        error = ""

        try:
            content = chat_completion(
                system,
                user,
                temperature=attempt_temp,
                max_tokens=max_tokens,
                json_mode=True,
                timeout=timeout,
                call_label=f"{call_label}:attempt_{attempt}",
                record_telemetry=False,
            )
            parsed = parse_llm_json(content)
            last_parsed = parsed

            if "__raw" in parsed and len(parsed) == 1:
                parse_ok = False
            else:
                parse_ok = True

            if parse_ok and required_keys and not all(k in parsed for k in required_keys):
                parse_ok = False
                validator_errors = [f"missing required keys: {required_keys}"]

            if parse_ok and validate_fn is not None:
                ok, validator_errors = _normalize_validate_result(validate_fn(parsed))
                validator_pass = ok
                if not ok:
                    last_validator_errors = validator_errors
                    parse_ok = False
            elif parse_ok:
                validator_pass = True

            if parse_ok:
                return parsed
        except Exception as exc:
            error = str(exc)
            last_parsed = {"__raw": error}

        latency_ms = (time.perf_counter() - started) * 1000
        append_llm_call(
            build_call_record(
                call_label=f"{call_label}:attempt_{attempt}",
                provider=provider,
                model=model,
                latency_ms=latency_ms,
                prompt_chars=len(system or "") + len(user or ""),
                response_chars=len(content),
                parse_ok=parse_ok,
                retry_index=attempt,
                validator_pass=validator_pass,
                validator_errors=validator_errors or last_validator_errors,
                fallback_used=False,
                error=error,
            )
        )

    if last_validator_errors:
        append_llm_call(
            build_call_record(
                call_label=f"{call_label}:validator_warning",
                provider=cfg.provider,
                model=cfg.model,
                latency_ms=0,
                prompt_chars=0,
                response_chars=0,
                parse_ok=False,
                retry_index=retries,
                validator_pass=False,
                validator_errors=last_validator_errors,
                fallback_used=False,
                error="LLM output failed validation",
            )
        )
    detail = "; ".join(last_validator_errors) if last_validator_errors else ""
    raw = last_parsed.get("__raw", "") if isinstance(last_parsed, dict) else ""
    raise RuntimeError(
        f"LLM JSON failed after {retries + 1} attempts"
        + (f": {detail}" if detail else "")
        + (f" ({raw[:200]})" if raw else "")
    )


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
            call_label="health_check",
        )
        parsed = parse_llm_json(content)
        if isinstance(parsed, dict) and parsed.get("status") == "ok":
            return True, "", content[:200]
        if "ok" in content.lower():
            return True, "", content[:200]
        return False, f"Unexpected test response: {content[:200]}", content[:200]
    except Exception as exc:
        active = get_config()
        detail = f"{exc} (active provider: {active.provider})"
        return False, detail, None


def list_ollama_models(base_url: str = "http://localhost:11434", timeout: float = 4.0) -> list[str]:
    """Discover models via Ollama native /api/tags endpoint."""
    import json

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
    import json

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
