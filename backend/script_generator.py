"""
Script Generator Module — Trust-Based Honest Review Edition
Generates scripts using AI research (specs, reviews, comparisons) so you
never need to physically buy or test products.
"""

from content_styles import DEFAULT_CONTENT_STYLE, normalize_content_style
from eval.output_validators import validate_script_output
from llm_client import chat_completion_json
from prompts import (
    HOOK_TYPES,
    HOOK_DESCRIPTIONS,
    SCRIPT_SYSTEM_PROMPT,
    build_script_user_prompt,
)

__all__ = [
    "HOOK_TYPES",
    "HOOK_DESCRIPTIONS",
    "generate_short_form_script",
    "generate_long_form_script",
    "generate_selected_scripts",
]


def _call_llm(
    user: str,
    required_keys: list[str] | None = None,
    *,
    content_style: str = "",
    fmt: str = "",
) -> dict:
    validate_fn = None
    if fmt:
        style = normalize_content_style(content_style or DEFAULT_CONTENT_STYLE)

        def validate_fn(parsed: dict) -> tuple[bool, list[str]]:
            return validate_script_output(parsed, style, fmt)

    return chat_completion_json(
        SCRIPT_SYSTEM_PROMPT,
        user,
        required_keys=required_keys,
        validate_fn=validate_fn,
        call_label="script_generator",
    )


def generate_short_form_script(product_info: dict, hook_type: str, content_style: str = None) -> dict:
    if content_style is None:
        content_style = product_info.get("content_style", DEFAULT_CONTENT_STYLE)
    content_style = normalize_content_style(content_style)
    user_prompt = build_script_user_prompt(product_info, hook_type, content_style, "short_form")
    return _call_llm(
        user_prompt,
        required_keys=["segments"],
        content_style=content_style,
        fmt="short_form",
    )


def generate_long_form_script(product_info: dict, hook_type: str, content_style: str = None) -> dict:
    if content_style is None:
        content_style = product_info.get("content_style", DEFAULT_CONTENT_STYLE)
    content_style = normalize_content_style(content_style)
    user_prompt = build_script_user_prompt(product_info, hook_type, content_style, "long_form")
    return _call_llm(
        user_prompt,
        required_keys=["chapters"],
        content_style=content_style,
        fmt="long_form",
    )


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
