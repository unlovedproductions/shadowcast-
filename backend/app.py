"""
ShadowCast — FastAPI Backend by Unloved Productions
Supports single product, batch CSV upload, content styles, and
research-based honest review generation.
"""

import csv
import io
import json
import os
import re
import shutil
import time
import uuid
import threading
import traceback
import zipfile
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

load_dotenv(Path(__file__).parent / ".env")
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

import llm_config
from amazon_scraper import scrape_amazon_product
from youtube_research import research_youtube_keywords
from script_generator import (
    generate_selected_scripts, HOOK_TYPES, HOOK_DESCRIPTIONS,
    CONTENT_STYLES, DEFAULT_CONTENT_STYLE,
)
from content_styles import (
    normalize_content_style,
    style_badge_text,
    style_requires_competitors,
)
from script_postprocessor import enrich_script
from apf_import import extract_apf_product_payloads, normalize_apf_payload
from video_renderer import render_short_form_video, render_long_form_video, resolve_video_preset
from youtube_assets_generator import generate_youtube_assets, save_posting_package_readable
from thumbnail_generator import generate_thumbnail_set, add_badge
from tts_generator import get_available_providers as get_tts_providers, get_best_provider as get_best_tts
from social_poster import SocialPoster, get_platform_status
from analytics_tracker import AnalyticsTracker, create_tracking_link
from youtube_analytics import YouTubeAnalyticsClient, extract_youtube_video_id
from oauth_manager import OAuthManager
from publish_service import PublishService, resolve_job_assets
from publishers.rumble_publisher import RumblePublisher
from bg_generator import generate_background, get_style_for_content, apply_vignette, apply_film_grain

app = FastAPI(title="ShadowCast by Unloved Productions", version="4.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def check_internal_auth(request):
    service_key = request.headers.get("X-Service-Key")
    internal_secret = os.getenv("INTERNAL_SERVICE_SECRET")
    if internal_secret and service_key != internal_secret:
        # We don't raise 401 here to maintain backward compatibility 
        raise HTTPException(status_code=401, detail="Unauthorized")


# Global middleware to enforce internal service auth for non-GET requests
from fastapi.responses import JSONResponse


@app.middleware("http")
async def enforce_internal_auth_middleware(request: Request, call_next):
    # UNLOVED_PUBLIC_UI_ROUTE_AUTH_BYPASS
    path = request.url.path
    public_paths = {
        "/",
        "/api/health",
        "/api/providers",
        "/api/hooks",
        "/api/content-styles",
        "/api/tts-providers",
        "/api/csv-template",
        "/api/generate",
        "/api/batch-upload",
        "/api/import-apf",
        "/api/import-apf/direct",  # UNLOVED_APF_DIRECT_IMPORT_AUTH_BYPASS
        "/api/batch-generate",
    }
    public_prefixes = (
        "/api/status/",
        "/api/results/",
        "/api/retry-missing/",
        "/api/download/",
        "/api/files/",
        "/api/bg-",
        "/api/analytics",
        "/api/social",
        "/api/oauth",
        "/api/publish",
        "/api/media",
        "/api/tracking-link",
    )
    if path in public_paths or any(path.startswith(prefix) for prefix in public_prefixes):
        return await call_next(request)
    internal_secret = os.getenv("INTERNAL_SERVICE_SECRET", "")
    if internal_secret and request.method != "GET":
        service_key = request.headers.get("X-Service-Key")
        if service_key != internal_secret:
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


OUTPUT_BASE = Path(__file__).parent / "output"
OUTPUT_BASE.mkdir(exist_ok=True)

# ── Job store (RAM cache + disk persistence) ───────────────────────────
jobs = {}
_active_job_threads = set()
_job_thread_lock = threading.Lock()


def _job_path(job_id: str) -> Path:
    return OUTPUT_BASE / job_id / "job.json"


def _script_has_short_form_segments(script: dict) -> bool:
    segments = script.get("segments")
    return isinstance(segments, list) and len(segments) > 0


def _script_has_long_form_segments(script: dict) -> bool:
    chapters = script.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        return False
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        segments = chapter.get("segments")
        if isinstance(segments, list) and len(segments) > 0:
            return True
    return False


def _validate_script_payload(script_payload: dict, formats: List[str]) -> tuple[bool, str]:
    if not isinstance(script_payload, dict):
        return False, "scripts payload is not an object"

    for fmt in formats:
        script = script_payload.get(fmt)
        if not isinstance(script, dict):
            return False, f"{fmt} script missing"
        if "__raw" in script:
            return False, f"{fmt} script contains __raw parse fallback"
        if fmt == "short_form" and not _script_has_short_form_segments(script):
            return False, "short_form script has no segments"
        if fmt == "long_form" and not _script_has_long_form_segments(script):
            return False, "long_form script has no chapter segments"

    return True, ""


def _load_cached_script_payload(path: Path) -> Optional[dict]:
    try:
        with open(path) as f:
            scripts = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    payload = scripts.get("scripts", {}) if isinstance(scripts, dict) else {}
    return payload if isinstance(payload, dict) else None


def _artifact_ok(path: Path, artifact_type: str = "generic", formats: Optional[List[str]] = None) -> bool:
    try:
        file_ok = path.is_file() and path.stat().st_size > 0
    except OSError:
        return False
    if not file_ok:
        return False
    if artifact_type != "script":
        return True

    script_payload = _load_cached_script_payload(path)
    if script_payload is None:
        return False
    expected_formats = formats or ["short_form", "long_form"]
    valid, _ = _validate_script_payload(script_payload, expected_formats)
    return valid


def _save_job(job_id: str) -> None:
    job = jobs.get(job_id)
    if not job:
        return
    path = _job_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(job, f, indent=2)
    tmp.replace(path)


def _split_job_messages(messages: list) -> tuple[list, list, list]:
    script_errors = []
    video_warnings = []
    other_errors = []
    for msg in messages or []:
        text = str(msg)
        if "] Script (" in text or "No segments found in script" in text:
            script_errors.append(text)
        elif "] Video (" in text:
            video_warnings.append(text)
        else:
            other_errors.append(text)
    return script_errors, video_warnings, other_errors


def _count_hook_outputs(hooks: dict) -> tuple[int, int]:
    videos = 0
    packages = 0
    for hook_data in (hooks or {}).values():
        if not isinstance(hook_data, dict):
            continue
        videos += len(hook_data.get("videos") or {})
        packages += len(hook_data.get("youtube_assets") or {})
    return videos, packages


def _summarize_job_output(job: dict) -> dict:
    hook_types = job.get("hook_types") or []
    formats = job.get("formats") or []
    expected_per_product = len(hook_types) * len(formats)

    if job.get("mode") == "batch":
        products = job.get("product_results") or []
        total_expected = expected_per_product * max(len(products), 1)
        videos = 0
        packages = 0
        for product_result in products:
            v, p = _count_hook_outputs(product_result.get("hooks") or {})
            videos += v
            packages += p
    else:
        total_expected = expected_per_product
        videos, packages = _count_hook_outputs(job.get("results") or {})

    errors = job.get("errors") or []
    script_errors, video_warnings, other_errors = _split_job_messages(errors)
    warning_count = len(script_errors) + len(video_warnings) + len(other_errors)

    return {
        "videos_ready": videos,
        "videos_expected": total_expected,
        "packages_ready": packages,
        "packages_expected": total_expected,
        "warning_count": warning_count,
        "is_partial": (
            videos < total_expected
            or packages < total_expected
            or warning_count > 0
        ),
    }


def _trust_field_status(value: str, ai_fallback_hints: list) -> str:
    text = (value or "").strip()
    if not text:
        return "missing"
    lowered = text.lower()
    for hint in ai_fallback_hints:
        if hint.lower() in lowered:
            return "ai_guidance"
    return "provided"


def _summarize_trust_inputs(product: dict) -> dict:
    product = product or {}
    competitors = product.get("competitors") or []
    return {
        "common_complaints": _trust_field_status(
            product.get("common_complaints", ""),
            ["research common complaints", "from amazon reviews and reddit"],
        ),
        "common_praises": _trust_field_status(
            product.get("common_praises", ""),
            ["research", "from reviews"],
        ),
        "who_not_for": _trust_field_status(
            product.get("who_not_for", ""),
            ["determine from specs", "who should not buy"],
        ),
        "competitors": "provided" if competitors else "missing",
        "price_comparison": _trust_field_status(product.get("price_comparison", ""), []),
    }


def _generate_scripts_with_retry(
    product: dict,
    hook_type: str,
    formats: List[str],
    content_style: str,
    retries: int = 2,
) -> tuple[dict, dict]:
    last_reason = "unknown schema issue"
    for _ in range(retries + 1):
        scripts = generate_selected_scripts(product, hook_type, formats, content_style)
        script_payload = scripts.get("scripts", {})
        for fmt in formats:
            if fmt in script_payload:
                script_payload[fmt] = enrich_script(script_payload[fmt], product, content_style)
        valid, reason = _validate_script_payload(script_payload, formats)
        if valid:
            scripts["scripts"] = script_payload
            return scripts, script_payload
        last_reason = reason
    raise ValueError(f"Generated scripts invalid after {retries + 1} attempts: {last_reason}")


def _load_job(job_id: str) -> Optional[dict]:
    if job_id in jobs:
        return jobs[job_id]
    path = _job_path(job_id)
    if not path.exists():
        return None
    try:
        with open(path) as f:
            job = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    jobs[job_id] = job
    return job


def _start_job_thread(job_id: str, target) -> None:
    with _job_thread_lock:
        if job_id in _active_job_threads:
            return
        _active_job_threads.add(job_id)

    def _runner():
        try:
            target(job_id)
        finally:
            with _job_thread_lock:
                _active_job_threads.discard(job_id)

    threading.Thread(target=_runner, daemon=True).start()


def _resume_incomplete_jobs() -> None:
    if not OUTPUT_BASE.exists():
        return
    for job_dir in OUTPUT_BASE.iterdir():
        if not job_dir.is_dir():
            continue
        path = job_dir / "job.json"
        if not path.exists():
            continue
        job_id = job_dir.name
        job = _load_job(job_id)
        if not job or job.get("status") != "running":
            continue
        mode = job.get("mode", "single")
        job["current_step"] = f"Resuming after restart: {job.get('current_step', '...')}"
        _save_job(job_id)
        if mode == "batch":
            _start_job_thread(job_id, _run_batch_generation)
        else:
            _start_job_thread(job_id, _run_generation)


# ── Helpers ────────────────────────────────────────────────────────────
def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '_', text)
    text = text.strip('_')
    return text[:60] or "product"


def fmt_label(fmt: str) -> str:
    return "short_form" if fmt == "short_form" else "long_form"


def fmt_display(fmt: str) -> str:
    return "Short-Form" if fmt == "short_form" else "Long-Form"


# ── Pydantic Models ───────────────────────────────────────────────────
class LLMConfigRequest(BaseModel):
    provider: str = "openai"
    api_key: str = ""
    base_url: str = ""
    model: str = ""


class ProductInfo(BaseModel):
    product_name: str
    niche: str = "General"
    key_features: List[str] = []
    price: str = "$49.99"
    affiliate_link: str = "[YOUR_AFFILIATE_LINK]"
    keywords: List[str] = []
    target_audience: str = "General consumers"
    product_category: str = ""
    competitors: List[str] = []
    unique_selling_point: str = ""
    discount_info: str = ""
    coupon_code: str = ""
    # ── New trust-based fields ──
    common_complaints: str = ""
    common_praises: str = ""
    who_not_for: str = ""
    series_name: str = ""
    price_comparison: str = ""
    content_style: str = DEFAULT_CONTENT_STYLE


class GenerateRequest(BaseModel):
    product_info: ProductInfo
    hook_types: List[str] = ["curiosity"]
    formats: List[str] = ["short_form", "long_form"]
    content_style: str = DEFAULT_CONTENT_STYLE
    audio_enabled: bool = True
    audio_mood: str = "auto"
    use_tts: bool = False
    tts_provider: str = "auto"
    tts_voice: Optional[str] = None
    video_preset: str = "medium"


class BatchGenerateRequest(BaseModel):
    products: List[ProductInfo]
    hook_types: List[str] = ["curiosity"]
    formats: List[str] = ["short_form", "long_form"]
    content_style: str = DEFAULT_CONTENT_STYLE
    audio_enabled: bool = True
    audio_mood: str = "auto"
    use_tts: bool = False
    tts_provider: str = "auto"
    tts_voice: Optional[str] = None
    video_preset: str = "medium"


# ── CSV Parsing ───────────────────────────────────────────────────────
CSV_COLUMNS = [
    "product_name", "niche", "key_features", "price", "affiliate_link",
    "keywords", "target_audience", "product_category", "competitors",
    "unique_selling_point", "discount_info", "coupon_code",
    "common_complaints", "common_praises", "who_not_for",
    "series_name", "price_comparison", "content_style",
]


def parse_csv_products(csv_text: str) -> List[dict]:
    reader = csv.DictReader(io.StringIO(csv_text))
    products = []
    for row in reader:
        norm = {}
        for k, v in row.items():
            if k is None:
                continue
            nk = k.strip().lower().replace(" ", "_")
            norm[nk] = (v or "").strip()

        if not norm.get("product_name"):
            continue

        product = {
            "product_name": norm.get("product_name", ""),
            "niche": norm.get("niche", "General"),
            "key_features": [f.strip() for f in norm.get("key_features", "").split(",") if f.strip()],
            "price": norm.get("price", "$49.99"),
            "affiliate_link": norm.get("affiliate_link", "[YOUR_AFFILIATE_LINK]"),
            "keywords": [k.strip() for k in norm.get("keywords", "").split(",") if k.strip()],
            "target_audience": norm.get("target_audience", "General consumers"),
            "product_category": norm.get("product_category", norm.get("niche", "General")),
            "competitors": [c.strip() for c in norm.get("competitors", "").split(",") if c.strip()],
            "unique_selling_point": norm.get("unique_selling_point", ""),
            "discount_info": norm.get("discount_info", ""),
            "coupon_code": norm.get("coupon_code", ""),
            # New fields
            "common_complaints": norm.get("common_complaints", ""),
            "common_praises": norm.get("common_praises", ""),
            "who_not_for": norm.get("who_not_for", ""),
            "series_name": norm.get("series_name", ""),
            "price_comparison": norm.get("price_comparison", ""),
            "content_style": normalize_content_style(norm.get("content_style", DEFAULT_CONTENT_STYLE)),
        }
        products.append(product)
    return products


# ── Single Product Generation Worker ──────────────────────────────────
def _run_single_product(job_id: str, product: dict, product_dir: Path,
                        hook_types: list, formats: list,
                        content_style: str,
                        step_offset: int, total_steps: int,
                        audio_enabled: bool = True,
                        audio_mood: str = "auto",
                        use_tts: bool = False,
                        tts_provider: str = "auto",
                        tts_voice: Optional[str] = None,
                        video_preset: str = "medium"):
    job = jobs[job_id]
    slug = slugify(product["product_name"])
    step = step_offset

    # Use product-level content_style if set, otherwise job-level
    effective_style = normalize_content_style(product.get("content_style") or content_style)
    product["content_style"] = effective_style

    mood_arg = None if audio_mood in (None, "", "auto") else audio_mood
    render_preset = resolve_video_preset(video_preset)

    all_scripts = {}
    all_yt_packages = {}
    product_results = {"product_name": product["product_name"], "hooks": {}}

    # Phase 1: Scripts
    for hook_type in hook_types:
        hook_name = hook_type.replace("_", " ").title()
        fname = f"{slug}_{hook_type}_scripts.json"
        script_path = product_dir / fname
        job["current_step"] = f"[{product['product_name']}] Generating {hook_name} scripts..."
        job["progress"] = int(step / total_steps * 100)
        _save_job(job_id)

        try:
            if _artifact_ok(script_path, artifact_type="script", formats=formats):
                script_payload = _load_cached_script_payload(script_path) or {}
                all_scripts[hook_type] = script_payload
                job["current_step"] = f"[{product['product_name']}] Using cached {hook_name} scripts..."
            else:
                try:
                    if script_path.exists():
                        script_path.unlink()
                except OSError:
                    pass
                scripts, script_payload = _generate_scripts_with_retry(
                    product, hook_type, formats, effective_style
                )
                all_scripts[hook_type] = script_payload
                with open(str(script_path), "w") as f:
                    json.dump(scripts, f, indent=2)

            if hook_type not in product_results["hooks"]:
                product_results["hooks"][hook_type] = {}
            product_results["hooks"][hook_type]["scripts"] = fname
        except Exception as e:
            job["errors"].append(f"[{product['product_name']}] Script ({hook_type}): {str(e)}")
            traceback.print_exc()

        step += len(formats)
        job["progress"] = int(step / total_steps * 100)
        _save_job(job_id)

    # Phase 2: Videos
    for hook_type in hook_types:
        hook_name = hook_type.replace("_", " ").title()
        scripts_data = all_scripts.get(hook_type, {})

        for fmt in formats:
            if fmt not in scripts_data:
                step += 1
                continue

            fl = fmt_display(fmt)
            fname = f"{slug}_{hook_type}_{fmt_label(fmt)}.mp4"
            video_path = product_dir / fname
            job["current_step"] = f"[{product['product_name']}] Rendering {hook_name} {fl} video..."
            job["progress"] = int(step / total_steps * 100)
            _save_job(job_id)

            try:
                if _artifact_ok(video_path):
                    job["current_step"] = f"[{product['product_name']}] Using cached {hook_name} {fl} video..."
                else:
                    render_kwargs = dict(
                        product_name=product.get('product_name', ''),
                        price=product.get('price', ''),
                        series_name=product.get('series_name', ''),
                        content_style=effective_style,
                        competitors=product.get('competitors', []),
                        audio_enabled=audio_enabled,
                        audio_mood=mood_arg,
                        use_tts=use_tts,
                        tts_provider=tts_provider,
                        tts_voice=tts_voice,
                        video_preset=render_preset,
                    )
                    if fmt == "short_form":
                        render_short_form_video(scripts_data[fmt], str(video_path), **render_kwargs)
                    else:
                        render_long_form_video(scripts_data[fmt], str(video_path), **render_kwargs)

                if hook_type not in product_results["hooks"]:
                    product_results["hooks"][hook_type] = {}
                if "videos" not in product_results["hooks"][hook_type]:
                    product_results["hooks"][hook_type]["videos"] = {}
                product_results["hooks"][hook_type]["videos"][fmt] = fname
            except Exception as e:
                job["errors"].append(f"[{product['product_name']}] Video ({hook_type} {fmt}): {str(e)}")
                traceback.print_exc()

            step += 1
            job["progress"] = int(step / total_steps * 100)
            _save_job(job_id)

    # Phase 3: YouTube Assets
    for hook_type in hook_types:
        hook_name = hook_type.replace("_", " ").title()
        scripts_data = all_scripts.get(hook_type, {})
        all_yt_packages[hook_type] = {}

        for fmt in formats:
            if fmt not in scripts_data:
                step += 1
                continue

            fl = fmt_display(fmt)
            fname = f"{slug}_{hook_type}_{fmt_label(fmt)}_youtube_package.json"
            yt_path = product_dir / fname
            job["current_step"] = f"[{product['product_name']}] Generating {hook_name} {fl} YouTube package..."
            job["progress"] = int(step / total_steps * 100)
            _save_job(job_id)

            try:
                if _artifact_ok(yt_path):
                    with open(yt_path) as f:
                        assets = json.load(f)
                    job["current_step"] = f"[{product['product_name']}] Using cached {hook_name} {fl} YouTube package..."
                else:
                    assets = generate_youtube_assets(product, scripts_data[fmt], fmt)
                    with open(str(yt_path), "w") as f:
                        json.dump(assets, f, indent=2)

                all_yt_packages[hook_type][fmt] = assets

                if hook_type not in product_results["hooks"]:
                    product_results["hooks"][hook_type] = {}
                if "youtube_assets" not in product_results["hooks"][hook_type]:
                    product_results["hooks"][hook_type]["youtube_assets"] = {}
                product_results["hooks"][hook_type]["youtube_assets"][fmt] = assets
                if "posting_packages" not in product_results["hooks"][hook_type]:
                    product_results["hooks"][hook_type]["posting_packages"] = {}
                product_results["hooks"][hook_type]["posting_packages"][fmt] = fname
            except Exception as e:
                job["errors"].append(f"[{product['product_name']}] YT assets ({hook_type} {fmt}): {str(e)}")
                traceback.print_exc()

            step += 1
            job["progress"] = int(step / total_steps * 100)
            _save_job(job_id)

    # Phase 4: Thumbnails
    job["current_step"] = f"[{product['product_name']}] Generating thumbnails..."
    _save_job(job_id)
    for hook_type in hook_types:
        try:
            content_style_name = normalize_content_style(product.get('content_style', 'honest_review'))
            variant_keys = ("variant_a", "variant_b", "variant_c")
            existing = {
                vk: f"{slug}_{hook_type}_thumbnail_{vk}.png"
                for vk in variant_keys
                if _artifact_ok(product_dir / f"{slug}_{hook_type}_thumbnail_{vk}.png")
            }
            if len(existing) == len(variant_keys):
                if hook_type not in product_results["hooks"]:
                    product_results["hooks"][hook_type] = {}
                product_results["hooks"][hook_type]["thumbnails"] = existing
            else:
                thumb_set = generate_thumbnail_set(
                    product.get('product_name', 'Product'),
                    hook_type,
                    content_style_name,
                    keywords=product.get('keywords', []) if isinstance(product.get('keywords'), list) else [],
                )
                for variant_key, thumb_img in thumb_set.items():
                    badge_text = style_badge_text(content_style_name)

                    if badge_text:
                        thumb_img = add_badge(thumb_img, badge_text)

                    thumb_fname = f"{slug}_{hook_type}_thumbnail_{variant_key}.png"
                    thumb_img.save(str(product_dir / thumb_fname))

                    if hook_type not in product_results["hooks"]:
                        product_results["hooks"][hook_type] = {}
                    if "thumbnails" not in product_results["hooks"][hook_type]:
                        product_results["hooks"][hook_type]["thumbnails"] = {}
                    product_results["hooks"][hook_type]["thumbnails"][variant_key] = thumb_fname
        except Exception as e:
            job["errors"].append(f"[{product['product_name']}] Thumbnails ({hook_type}): {str(e)}")
            traceback.print_exc()

    # Save combined posting package
    try:
        fname = f"{slug}_YOUTUBE_POSTING_PACKAGE.txt"
        save_posting_package_readable(all_yt_packages, product, str(product_dir / fname))
    except Exception:
        pass

    _save_job(job_id)
    return product_results, step


# ── Generation Workers ────────────────────────────────────────────────
def _steps_per_product(hook_types, formats):
    n_hooks = len(hook_types)
    n_fmts = len(formats)
    return n_hooks * n_fmts * 3


def _run_generation(job_id: str):
    job = jobs[job_id]
    job_dir = OUTPUT_BASE / job_id
    product = job["product_info"]
    hook_types = job["hook_types"]
    formats = job["formats"]
    content_style = normalize_content_style(job.get("content_style", DEFAULT_CONTENT_STYLE))
    total_steps = _steps_per_product(hook_types, formats)

    try:
        product_dir = job_dir
        result, _ = _run_single_product(
            job_id, product, product_dir, hook_types, formats,
            content_style, 0, total_steps,
            audio_enabled=job.get("audio_enabled", True),
            audio_mood=job.get("audio_mood", "auto"),
            use_tts=job.get("use_tts", False),
            tts_provider=job.get("tts_provider", "auto"),
            tts_voice=job.get("tts_voice"),
            video_preset=job.get("video_preset", "medium"),
        )
        job["results"] = result.get("hooks", {})
        job["status"] = "complete"
        job["progress"] = 100
        job["current_step"] = "Done!"
        _save_job(job_id)
    except Exception as e:
        job["status"] = "error"
        job["current_step"] = f"Error: {str(e)}"
        job["errors"].append(str(e))
        _save_job(job_id)
        traceback.print_exc()


def _run_batch_generation(job_id: str):
    job = jobs[job_id]
    job_dir = OUTPUT_BASE / job_id
    products = job["products"]
    hook_types = job["hook_types"]
    formats = job["formats"]
    content_style = normalize_content_style(job.get("content_style", DEFAULT_CONTENT_STYLE))

    steps_per = _steps_per_product(hook_types, formats)
    total_steps = steps_per * len(products)
    step_offset = 0

    try:
        all_product_results = []

        for i, product in enumerate(products):
            slug = slugify(product["product_name"])
            product_dir = job_dir / slug
            product_dir.mkdir(exist_ok=True)

            job["current_step"] = f"Product {i+1}/{len(products)}: {product['product_name']}"
            _save_job(job_id)

            result, step_offset = _run_single_product(
                job_id, product, product_dir, hook_types, formats,
                content_style, step_offset, total_steps,
                audio_enabled=job.get("audio_enabled", True),
                audio_mood=job.get("audio_mood", "auto"),
                use_tts=job.get("use_tts", False),
                tts_provider=job.get("tts_provider", "auto"),
                tts_voice=job.get("tts_voice"),
                video_preset=job.get("video_preset", "medium"),
            )
            all_product_results.append(result)
            job["product_results"] = all_product_results
            _save_job(job_id)

        job["product_results"] = all_product_results

        zip_path = job_dir / "all_products.zip"
        with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(str(job_dir)):
                for file in files:
                    if file == "all_products.zip":
                        continue
                    full = os.path.join(root, file)
                    arcname = os.path.relpath(full, str(job_dir))
                    zf.write(full, arcname)

        job["status"] = "complete"
        job["progress"] = 100
        job["current_step"] = f"Done! {len(products)} products processed."
        _save_job(job_id)
    except Exception as e:
        job["status"] = "error"
        job["current_step"] = f"Error: {str(e)}"
        job["errors"].append(str(e))
        _save_job(job_id)
        traceback.print_exc()


# ── Endpoints ─────────────────────────────────────────────────────────

@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "ShadowCast", "version": "4.0"}


def _check_llm_reachable() -> tuple[bool, str]:
    cfg = llm_config.get_config()
    base_url = (cfg.base_url or "").rstrip("/")
    if not base_url:
        return False, "LLM base URL is not configured."
    headers = {}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"
    try:
        req = urllib_request.Request(f"{base_url}/models", headers=headers)
        with urllib_request.urlopen(req, timeout=4) as resp:
            if resp.status == 200:
                return True, ""
    except urllib_error.HTTPError as exc:
        if exc.code in (401, 403):
            return False, f"LLM auth failed ({exc.code}). Check API key or provider settings."
        return False, f"LLM HTTP {exc.code} at {base_url}."
    except Exception as exc:
        return False, f"LLM unreachable at {base_url}: {exc}"
    return False, f"LLM unreachable at {base_url}."


@app.get("/api/readiness")
def get_readiness():
    blockers: List[str] = []
    warnings: List[str] = []

    ffmpeg_ok = shutil.which("ffmpeg") is not None
    if not ffmpeg_ok:
        blockers.append("ffmpeg is not installed or not on PATH.")

    llm_ok, llm_detail = _check_llm_reachable()
    cfg = llm_config.get_config()
    if not llm_ok:
        blockers.append(llm_detail or "LLM provider is unreachable.")

    providers = get_tts_providers()
    best_tts = get_best_tts()
    quality_tts = best_tts in ("kokoro", "openai", "piper")
    if not quality_tts:
        warnings.append(
            "Only basic Google TTS is available. Install Kokoro/Piper or configure OpenAI TTS for better voice quality."
        )

    return {
        "ready": len(blockers) == 0,
        "blockers": blockers,
        "warnings": warnings,
        "checks": {
            "ffmpeg": ffmpeg_ok,
            "llm": llm_ok,
            "llm_provider": cfg.provider,
            "llm_model": cfg.model,
            "tts_best": best_tts,
            "tts_quality": quality_tts,
            "tts_providers": {
                key: bool(info.get("available"))
                for key, info in providers.items()
            },
        },
        "default_video_preset": resolve_video_preset(None),
    }


@app.get("/api/providers")
def get_providers():
    return {
        "providers": llm_config.PROVIDER_PRESETS,
        "current": {
            "provider": llm_config.get_config().provider,
            "base_url": llm_config.get_config().base_url,
            "model": llm_config.get_config().model,
            "has_api_key": bool(llm_config.get_config().api_key),
        },
    }


@app.post("/api/config")
def set_llm_config(req: LLMConfigRequest):
    cfg = llm_config.set_config(
        provider=req.provider, api_key=req.api_key,
        base_url=req.base_url, model=req.model,
    )
    return {
        "status": "ok", "provider": cfg.provider,
        "base_url": cfg.base_url, "model": cfg.model,
        "has_api_key": bool(cfg.api_key),
    }


@app.get("/api/hooks")
def get_hooks():
    return {
        "hooks": HOOK_TYPES,
        "descriptions": HOOK_DESCRIPTIONS,
    }


@app.get("/api/content-styles")
def get_content_styles():
    return {
        "styles": CONTENT_STYLES,
        "default": DEFAULT_CONTENT_STYLE,
    }


# ── TTS Providers ────────────────────────────────────────────────────
@app.get("/api/tts-providers")
def tts_providers():
    """Return available TTS providers and their status."""
    providers = get_tts_providers()
    best = get_best_tts()
    return {"providers": providers, "best": best}


# ── Amazon Product Scraper ────────────────────────────────────────────
@app.post("/api/scrape-amazon")
async def scrape_amazon(url: str = Form(...)):
    """Scrape an Amazon product URL to auto-fill product fields."""
    if not url or not url.strip():
        raise HTTPException(status_code=400, detail="No URL provided")
    result = await scrape_amazon_product(url.strip())
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    # Map scraped data to ShadowCast product fields
    mapped = {
        "product_name": result.get("product_name", ""),
        "price": result.get("price", ""),
        "key_features": ", ".join(result.get("key_features", [])),
        "star_rating": result.get("star_rating", ""),
        "number_of_reviews": result.get("number_of_reviews", ""),
        "common_praises": "\n".join(
            [f"- {r['title']}: {r['text']}" for r in result.get("positive_reviews", [])]
        ) if result.get("positive_reviews") else "",
        "common_complaints": "\n".join(
            [f"- {r['title']}: {r['text']}" for r in result.get("negative_reviews", [])]
        ) if result.get("negative_reviews") else "",
    }
    return {"status": "ok", "data": mapped, "raw": result}


# ── YouTube Keyword Research ─────────────────────────────────────────
@app.post("/api/youtube-research")
async def youtube_research(query: str = Form(...)):
    """Research YouTube keywords and get suggestions for a product/niche."""
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="No query provided")
    result = await research_youtube_keywords(query.strip())
    return {"status": "ok", "data": result}


@app.get("/api/csv-template")
def get_csv_template():
    header = ",".join(CSV_COLUMNS)
    example1 = 'SoundCore Space A40 Earbuds,Tech / Audio,"ANC, 50hr battery, Hi-Res Audio",$79.99,https://amzn.to/example123,"wireless earbuds, ANC earbuds",Tech-savvy 18-35,Wireless Earbuds,"AirPods Pro 2, Sony WF-1000XM5",Premium ANC at half the price,20% off this week,SOUND20,"Occasional ANC cutouts, case scratches easily","Battery life is incredible, ANC rivals $200 earbuds","Audiophiles wanting wired quality, very small ears",Worth It or Waste?,AirPods Pro 2 costs $249 for similar ANC performance,honest_review'
    example2 = 'Anker 737 Power Bank,Tech / Accessories,"140W output, 24000mAh, LED display",$89.99,https://amzn.to/example456,"power bank, portable charger",Remote workers and travelers,Power Banks,"Baseus 100W, Ugreen 145W",Fastest charging power bank under $100,,,Heavy at 1.3 lbs,Charges MacBook Pro to 50% in 30 min,People who want ultralight travel gear,Budget Challenge,Baseus 100W costs $69 but charges 30% slower,budget_challenge'
    content = header + "\n" + example1 + "\n" + example2 + "\n"
    return HTMLResponse(content=content, media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=product_template.csv"})


# ── Single product generation ─────────────────────────────────────────
@app.post("/api/generate")
def start_generation(req: GenerateRequest):
    job_id = str(uuid.uuid4())[:8]
    job_dir = OUTPUT_BASE / job_id
    job_dir.mkdir(exist_ok=True)

    product = req.product_info.dict()
    if not product.get("product_category"):
        product["product_category"] = product.get("niche", "General")
    req_style = normalize_content_style(req.content_style)
    product_style = normalize_content_style(product.get("content_style") or req_style)
    if not product.get("content_style") or normalize_content_style(product["content_style"]) == DEFAULT_CONTENT_STYLE:
        product["content_style"] = req_style
    else:
        product["content_style"] = product_style

    warnings = []
    if style_requires_competitors(product["content_style"]) and not product.get("competitors"):
        warnings.append(
            "Competitors recommended for this content style — import from APF or add manually."
        )

    jobs[job_id] = {
        "id": job_id, "mode": "single",
        "status": "running", "progress": 0, "current_step": "Starting...",
        "product_info": product, "hook_types": req.hook_types,
        "formats": req.formats, "content_style": product["content_style"],
        "audio_enabled": req.audio_enabled,
        "audio_mood": req.audio_mood,
        "use_tts": req.use_tts,
        "tts_provider": req.tts_provider,
        "tts_voice": req.tts_voice,
        "video_preset": resolve_video_preset(req.video_preset),
        "results": {}, "errors": [],
        "created_at": time.time(),
    }
    _save_job(job_id)

    _start_job_thread(job_id, _run_generation)
    response = {"job_id": job_id, "status": "running", "mode": "single"}
    if warnings:
        response["warnings"] = warnings
    return response


# ── Batch CSV upload ──────────────────────────────────────────────────
@app.post("/api/batch-upload")
async def batch_upload(
    file: UploadFile = File(...),
    hook_types: str = Form("curiosity"),
    formats: str = Form("short_form,long_form"),
    content_style: str = Form(DEFAULT_CONTENT_STYLE),
):
    content = await file.read()
    try:
        csv_text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        csv_text = content.decode("latin-1")

    products = parse_csv_products(csv_text)
    if not products:
        raise HTTPException(status_code=400, detail="No valid products found in CSV.")

    hook_list = [h.strip() for h in hook_types.split(",") if h.strip()]
    fmt_list = [f.strip() for f in formats.split(",") if f.strip()]

    job_id = str(uuid.uuid4())[:8]
    job_dir = OUTPUT_BASE / job_id
    job_dir.mkdir(exist_ok=True)

    jobs[job_id] = {
        "id": job_id, "mode": "batch",
        "status": "running", "progress": 0,
        "current_step": f"Starting batch: {len(products)} products...",
        "products": products, "hook_types": hook_list,
        "formats": fmt_list, "content_style": content_style,
        "product_results": [],
        "errors": [], "created_at": time.time(),
    }
    _save_job(job_id)

    _start_job_thread(job_id, _run_batch_generation)

    return {
        "job_id": job_id, "status": "running", "mode": "batch",
        "product_count": len(products),
        "products_found": [p["product_name"] for p in products],
    }


# ── Import from APF ──────────────────────────────────────────────────────
@app.post("/api/import-apf")
async def import_apf(file: UploadFile = File(...)):
    """Import products from APF JSON export file."""
    content = await file.read()
    try:
        json_text = content.decode("utf-8-sig")
        products_data = json.loads(json_text)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON file: {str(e)}")
    
    if not isinstance(products_data, list):
        raise HTTPException(status_code=400, detail="JSON must be an array of products")
    
    products = []
    for item in products_data:
        try:
            product = ProductInfo(
                product_name=item.get("product_name", ""),
                niche=item.get("niche", "General"),
                key_features=item.get("key_features", []) if isinstance(item.get("key_features"), list) else [item.get("key_features", "")],
                price=item.get("price", "$49.99"),
                affiliate_link=item.get("affiliate_link", "[YOUR_AFFILIATE_LINK]"),
                keywords=item.get("keywords", []) if isinstance(item.get("keywords"), list) else [item.get("keywords", "")],
                target_audience=item.get("target_audience", "General consumers"),
                product_category=item.get("product_category", item.get("niche", "General")),
                competitors=item.get("competitors", []) if isinstance(item.get("competitors"), list) else [item.get("competitors", "")],
                unique_selling_point=item.get("unique_selling_point", ""),
                discount_info=item.get("discount_info", ""),
                coupon_code=item.get("coupon_code", ""),
                common_complaints=item.get("common_complaints", ""),
                common_praises=item.get("common_praises", ""),
                who_not_for=item.get("who_not_for", ""),
                series_name=item.get("series_name", ""),
                price_comparison=item.get("price_comparison", ""),
                content_style=normalize_content_style(item.get("content_style", DEFAULT_CONTENT_STYLE)),
            )
            products.append(product)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid product data: {str(e)}")
    
    if not products:
        raise HTTPException(status_code=400, detail="No valid products found in JSON.")
    
    return {
        "status": "ok",
        "product_count": len(products),
        "products": [p.dict() for p in products],
        "products_found": [p.product_name for p in products],
    }


# ── Batch JSON upload ─────────────────────────────────────────────────
@app.post("/api/batch-generate")
def batch_generate(req: BatchGenerateRequest):
    products = []
    for p in req.products:
        item = p.dict()
        if not item.get("product_category"):
            item["product_category"] = item.get("niche", "General")
        item["content_style"] = normalize_content_style(
            item.get("content_style") or req.content_style
        )
        products.append(item)

    job_id = str(uuid.uuid4())[:8]
    job_dir = OUTPUT_BASE / job_id
    job_dir.mkdir(exist_ok=True)

    jobs[job_id] = {
        "id": job_id, "mode": "batch",
        "status": "running", "progress": 0,
        "current_step": f"Starting batch: {len(products)} products...",
        "products": products, "hook_types": req.hook_types,
        "formats": req.formats, "content_style": normalize_content_style(req.content_style),
        "audio_enabled": req.audio_enabled,
        "audio_mood": req.audio_mood,
        "use_tts": req.use_tts,
        "tts_provider": req.tts_provider,
        "tts_voice": req.tts_voice,
        "video_preset": resolve_video_preset(req.video_preset),
        "product_results": [],
        "errors": [], "created_at": time.time(),
    }
    _save_job(job_id)

    _start_job_thread(job_id, _run_batch_generation)

    return {
        "job_id": job_id, "status": "running", "mode": "batch",
        "product_count": len(products),
        "products_found": [p["product_name"] for p in products],
    }


# ── Status & Results ──────────────────────────────────────────────────
@app.get("/api/status/{job_id}")
def get_status(job_id: str):
    job = _load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    errors = job.get("errors", [])
    script_errors, video_warnings, other_errors = _split_job_messages(errors)
    resp = {
        "id": job["id"], "mode": job.get("mode", "single"),
        "status": job["status"], "progress": job.get("progress", 0),
        "current_step": job.get("current_step", ""), "errors": errors,
        "script_errors": script_errors,
        "video_warnings": video_warnings,
        "other_errors": other_errors,
    }
    if job.get("mode") == "batch":
        resp["product_count"] = len(job.get("products", []))
    return resp


@app.get("/api/results/{job_id}")
def get_results(job_id: str):
    job = _load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    errors = job.get("errors", [])
    script_errors, video_warnings, other_errors = _split_job_messages(errors)
    resp = {
        "id": job["id"], "mode": job.get("mode", "single"),
        "status": job["status"], "progress": job.get("progress", 0),
        "current_step": job.get("current_step", ""), "errors": errors,
        "script_errors": script_errors,
        "video_warnings": video_warnings,
        "other_errors": other_errors,
    }
    if job.get("mode") == "batch":
        resp["product_results"] = job.get("product_results", [])
        resp["products"] = job.get("products", [])
        resp["hook_types"] = job.get("hook_types", [])
        resp["formats"] = job.get("formats", [])
    else:
        resp["product_info"] = job.get("product_info", {})
        resp["hook_types"] = job.get("hook_types", [])
        resp["formats"] = job.get("formats", [])
        resp["results"] = job.get("results", {})
    resp["summary"] = _summarize_job_output(job)
    if job.get("mode") == "batch":
        resp["trust_inputs"] = [
            {
                "product_name": product.get("product_name", ""),
                "signals": _summarize_trust_inputs(product),
            }
            for product in job.get("products", [])
        ]
    else:
        resp["trust_inputs"] = _summarize_trust_inputs(job.get("product_info") or {})
    return resp


@app.post("/api/retry-missing/{job_id}")
def retry_missing_outputs(job_id: str):
    job = _load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") == "running":
        raise HTTPException(status_code=409, detail="Job is already running")

    summary = _summarize_job_output(job)
    if job.get("status") == "complete" and not summary.get("is_partial"):
        return {
            "job_id": job_id,
            "status": "complete",
            "message": "All expected outputs are already present.",
            "summary": summary,
        }

    job["status"] = "running"
    job["current_step"] = "Resuming missing outputs..."
    job["progress"] = max(int(job.get("progress") or 0), 0)
    _save_job(job_id)

    if job.get("mode") == "batch":
        _start_job_thread(job_id, _run_batch_generation)
    else:
        _start_job_thread(job_id, _run_generation)

    return {
        "job_id": job_id,
        "status": "running",
        "message": "Retry started. Existing artifacts will be skipped.",
        "summary": summary,
    }


@app.on_event("startup")
def _on_startup_resume_jobs():
    _resume_incomplete_jobs()


@app.get("/api/download/{job_id}/{path:path}")
def download_file(job_id: str, path: str):
    file_path = OUTPUT_BASE / job_id / path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    media_type = "video/mp4" if path.endswith(".mp4") else "application/json"
    if path.endswith(".txt"):
        media_type = "text/plain"
    if path.endswith(".zip"):
        media_type = "application/zip"
    return FileResponse(str(file_path), filename=file_path.name, media_type=media_type)


@app.get("/api/files/{job_id}")
def list_files(job_id: str):
    job_dir = OUTPUT_BASE / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="Job not found")
    files = []
    for root, dirs, filenames in os.walk(str(job_dir)):
        for fn in filenames:
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, str(job_dir))
            files.append({
                "path": rel,
                "name": fn,
                "size": os.path.getsize(full),
                "type": "video" if fn.endswith(".mp4") else "text" if fn.endswith(".txt") else "json" if fn.endswith(".json") else "zip" if fn.endswith(".zip") else "other",
            })
    return {"job_id": job_id, "files": files}


# ── Social Posting ───────────────────────────────────────────────────
social_poster = SocialPoster()
analytics = AnalyticsTracker(db_path=str(OUTPUT_BASE / "analytics.json"))
oauth_manager = OAuthManager()
youtube_analytics_client = YouTubeAnalyticsClient()
publish_service = PublishService(jobs=jobs, analytics=analytics)
rumble_publisher = RumblePublisher()


@app.get("/api/social/status")
def social_status():
    oauth_status = oauth_manager.status()
    legacy = get_platform_status()
    merged = {}
    for platform in ("youtube", "instagram", "facebook", "tiktok", "rumble"):
        connected = oauth_status.get(platform, {}).get("connected", False)
        merged[platform] = "Connected" if connected else legacy.get(platform, "Not Configured")
    return merged


@app.get("/api/media/serve")
def serve_media_for_platforms(path: str):
    """Serve job output files at a stable URL for Instagram video_url requirements."""
    if ".." in path or path.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid path")
    parts = Path(path).parts
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="Path must be job_id/relative/file")
    job_id, rel = parts[0], str(Path(*parts[1:]))
    candidate = OUTPUT_BASE / job_id / rel
    if candidate.exists() and candidate.is_file():
        media_type = "video/mp4" if path.endswith(".mp4") else "image/png" if path.endswith(".png") else "application/octet-stream"
        return FileResponse(str(candidate), media_type=media_type)
    raise HTTPException(status_code=404, detail="File not found")


# ── OAuth ─────────────────────────────────────────────────────────────
def _frontend_redirect(path: str) -> RedirectResponse:
    base = os.getenv("OAUTH_REDIRECT_BASE_URL", "http://localhost:8000").rstrip("/")
    return RedirectResponse(url=f"{base}{path}", status_code=302)


@app.get("/api/oauth/status")
def oauth_status():
    return oauth_manager.status()


@app.get("/api/oauth/config")
def oauth_config():
    return oauth_manager.config_status()


@app.get("/api/oauth/{platform}/authorize")
def oauth_authorize(platform: str):
    try:
        return oauth_manager.start_authorize(platform)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/oauth/{platform}/callback")
def oauth_callback(platform: str, code: str = "", state: str = "", error: str = ""):
    if error:
        return _frontend_redirect(f"/?page=social&oauth_error={quote(error)}")
    if not code:
        return _frontend_redirect("/?page=social&oauth_error=Missing+authorization+code")
    try:
        oauth_manager.handle_callback(platform, code, state)
        return _frontend_redirect(f"/?page=social&connected={platform}")
    except Exception as e:
        return _frontend_redirect(f"/?page=social&oauth_error={quote(str(e))}")


class RumbleLoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/oauth/rumble/login")
def oauth_rumble_login(req: RumbleLoginRequest):
    try:
        rumble_publisher.login_and_capture_session(req.username, req.password)
        return {"platform": "rumble", "status": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/oauth/{platform}")
def oauth_disconnect(platform: str):
    return oauth_manager.disconnect(platform)


# ── Publish ───────────────────────────────────────────────────────────
class PublishRequest(BaseModel):
    job_id: str
    hook_type: str
    video_format: str = "short_form"
    platform: str
    product_slug: Optional[str] = None
    dry_run: bool = False
    thumbnail_variant: str = "variant_a"
    target_page_id: Optional[str] = None


class PublishBatchRequest(BaseModel):
    job_id: str
    hook_type: str
    video_format: str = "short_form"
    platforms: List[str]
    product_slug: Optional[str] = None
    dry_run: bool = False


@app.post("/api/publish")
def publish_video(req: PublishRequest):
    try:
        return publish_service.publish(
            req.job_id, req.hook_type, req.video_format, req.platform,
            product_slug=req.product_slug, dry_run=req.dry_run,
            thumbnail_variant=req.thumbnail_variant, target_page_id=req.target_page_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/publish/batch")
def publish_video_batch(req: PublishBatchRequest):
    try:
        return {"results": publish_service.publish_batch(
            req.job_id, req.hook_type, req.video_format, req.platforms,
            product_slug=req.product_slug, dry_run=req.dry_run,
        )}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class PostRequest(BaseModel):
    video_path: Optional[str] = None
    caption: str = ""
    platform: str
    hashtags: List[str] = []
    dry_run: bool = False
    job_id: Optional[str] = None
    hook_type: Optional[str] = None
    video_format: Optional[str] = "short_form"
    product_slug: Optional[str] = None


@app.post("/api/social/post")
def social_post(req: PostRequest):
    try:
        if req.job_id and req.hook_type:
            return publish_service.publish(
                req.job_id, req.hook_type, req.video_format or "short_form", req.platform,
                product_slug=req.product_slug, dry_run=req.dry_run,
            )
        if not req.video_path:
            raise HTTPException(status_code=400, detail="video_path or job_id required")
        if req.platform == "instagram":
            result = social_poster.post_to_instagram(
                req.video_path, req.caption, req.hashtags, dry_run=req.dry_run
            )
        elif req.platform == "tiktok":
            result = social_poster.post_to_tiktok(
                req.video_path, req.caption, req.hashtags, dry_run=req.dry_run
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown platform: {req.platform}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/social/queue")
def social_queue():
    return {"queue": social_poster.get_queue()}


class SchedulePostRequest(BaseModel):
    platform: str
    video_path: Optional[str] = None
    caption: str = ""
    hashtags: List[str] = []
    scheduled_time: str
    job_id: Optional[str] = None
    hook_type: Optional[str] = None
    video_format: Optional[str] = "short_form"
    product_slug: Optional[str] = None


@app.post("/api/social/schedule")
def schedule_social_post(req: SchedulePostRequest):
    video_path = req.video_path or ""
    if req.job_id and req.hook_type:
        resolved = resolve_job_assets(
            req.job_id, req.hook_type, req.video_format or "short_form",
            product_slug=req.product_slug, jobs=jobs,
        )
        video_path = resolved["video_path"]
    result = social_poster.schedule_post(
        req.platform, video_path, req.caption,
        req.hashtags, req.scheduled_time,
        job_id=req.job_id, hook_type=req.hook_type,
        video_format=req.video_format, product_slug=req.product_slug,
    )
    return result


@app.post("/api/social/queue/process")
def process_social_queue(dry_run: bool = False):
    processed = social_poster.process_queue(dry_run=dry_run, publish_service=publish_service, jobs=jobs)
    return {"processed": processed, "queue": social_poster.get_queue()}


# ── Analytics ────────────────────────────────────────────────────────
@app.post("/api/analytics/track")
def track_video(
    product_name: str = Form(...),
    hook_type: str = Form(...),
    format_type: str = Form(...),
    video_path: str = Form(...),
    youtube_url: Optional[str] = Form(None),
):
    video_id = analytics.track_video(
        product_name, hook_type, format_type, video_path, youtube_url
    )
    return {"video_id": video_id}


class MetricRequest(BaseModel):
    video_id: str
    metric_type: str
    value: float


@app.post("/api/analytics/record")
def record_metric(req: MetricRequest):
    analytics.record_metric(req.video_id, req.metric_type, req.value)
    return {"status": "recorded"}


@app.post("/api/analytics/sync-youtube")
def sync_youtube_analytics():
    yt_ids: list[str] = []
    for video_info in analytics.data.get("videos", {}).values():
        yt_id = video_info.get("youtube_video_id") or extract_youtube_video_id(video_info.get("youtube_url"))
        if yt_id:
            yt_ids.append(yt_id)
    if not yt_ids:
        raise HTTPException(status_code=400, detail="No tracked videos with YouTube URLs. Publish or track videos first.")
    try:
        stats = youtube_analytics_client.fetch_video_stats(list(dict.fromkeys(yt_ids)))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        msg = str(e)
        if "insufficient" in msg.lower() or "403" in msg:
            raise HTTPException(
                status_code=403,
                detail="YouTube Analytics access denied. Reconnect YouTube on the Social page to grant analytics scopes.",
            )
        raise HTTPException(status_code=500, detail=msg)
    result = analytics.sync_youtube_stats(stats)
    result["fetched"] = len(stats)
    return result


@app.get("/api/analytics/dashboard")
def analytics_dashboard():
    return analytics.generate_dashboard_data()


@app.get("/api/analytics/hooks")
def hook_performance():
    return analytics.get_hook_performance()


@app.get("/api/analytics/formats")
def format_performance():
    return analytics.get_format_performance()


@app.get("/api/analytics/top")
def top_performers(metric: str = "views", limit: int = 10):
    return analytics.get_top_performers(metric, limit)


@app.get("/api/analytics/revenue")
def revenue_report():
    return analytics.get_revenue_report()


@app.get("/api/analytics/export")
def export_analytics():
    export_path = str(OUTPUT_BASE / "analytics_export.csv")
    analytics.export_csv(export_path)
    return FileResponse(export_path, filename="shadowcast_analytics.csv")


@app.get("/api/tracking-link")
def get_tracking_link(affiliate_url: str, video_id: str, platform: str = "youtube"):
    return {"tracking_url": create_tracking_link(affiliate_url, video_id, platform)}


# ── Background Styles ────────────────────────────────────────────────
BG_STYLES = [
    "gradient", "mesh_gradient", "geometric", "circuit", "wave",
    "bokeh", "noise", "radial", "grid", "abstract"
]


@app.get("/api/bg-styles")
def list_bg_styles():
    return {"styles": BG_STYLES}


@app.get("/api/bg-preview/{style}")
def preview_bg(style: str):
    if style not in BG_STYLES:
        raise HTTPException(status_code=400, detail=f"Unknown style: {style}")
    preview_path = OUTPUT_BASE / f"bg_preview_{style}.png"
    img = generate_background(640, 360, style=style)
    img = apply_vignette(img, strength=0.4)
    img.save(str(preview_path))
    return FileResponse(str(preview_path), media_type="image/png")


@app.get("/api/bg-recommend")
def recommend_bg(content_style: str = "honest_review", hook_type: str = "curiosity"):
    recommended = get_style_for_content(content_style, hook_type)
    return {"recommended_style": recommended, "all_styles": BG_STYLES}

# BEGIN UNLOVED_APF_DIRECT_IMPORT_ENDPOINTS
# Local APF → ShadowCast direct draft import.
import os as _unloved_os
import json as _unloved_json
import secrets as _unloved_secrets
from pathlib import Path as _UnlovedPath
from datetime import datetime as _unloved_datetime, timezone as _unloved_timezone
from fastapi import Request as _UnlovedRequest, HTTPException as _UnlovedHTTPException

_UNLOVED_APF_IMPORT_DIR = _UnlovedPath(
    _unloved_os.getenv(
        "SHADOWCAST_APF_IMPORT_DIR",
        "/home/unloved/shadowcast-/backend/apf_imports"
    )
)
_UNLOVED_APF_IMPORT_DIR.mkdir(parents=True, exist_ok=True)

@app.post("/api/import-apf/direct")
async def unloved_apf_direct_import(request: _UnlovedRequest):
    payload = await request.json()
    token = _unloved_secrets.token_urlsafe(18)
    product_payloads = extract_apf_product_payloads(payload)

    if len(product_payloads) > 1:
        products = []
        for item in product_payloads:
            import_result = normalize_apf_payload(item if isinstance(item, dict) else {"product": item})
            normalized = import_result["normalized"]
            if not normalized.get("productName"):
                continue
            products.append({
                "normalized": normalized,
                "recommended_content_style": import_result["recommended_content_style"],
                "payload": item,
            })
        if not products:
            raise _UnlovedHTTPException(status_code=400, detail="APF batch payload did not include product names.")

        doc = {
            "ok": True,
            "batch": True,
            "token": token,
            "created_at": _unloved_datetime.now(_unloved_timezone.utc).isoformat(),
            "product_count": len(products),
            "products": products,
            "normalized": products[0]["normalized"],
            "recommended_content_style": products[0]["recommended_content_style"],
            "payload": payload,
        }
        path = _UNLOVED_APF_IMPORT_DIR / f"{token}.json"
        path.write_text(_unloved_json.dumps(doc, ensure_ascii=False, indent=2))
        base = _unloved_os.getenv("SHADOWCAST_PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
        return {
            "ok": True,
            "batch": True,
            "token": token,
            "product_count": len(products),
            "productName": products[0]["normalized"].get("productName"),
            "product_names": [p["normalized"].get("productName") for p in products],
            "recommended_content_style": products[0]["recommended_content_style"],
            "normalized": products[0]["normalized"],
            "open_url": f"{base}/?apf_draft={token}",
        }

    single = product_payloads[0] if product_payloads else payload
    import_result = normalize_apf_payload(single if isinstance(single, dict) else payload)
    normalized = import_result["normalized"]
    recommended_content_style = import_result["recommended_content_style"]

    if not normalized.get("productName"):
        raise _UnlovedHTTPException(status_code=400, detail="APF payload did not include a product name.")

    doc = {
        "ok": True,
        "token": token,
        "created_at": _unloved_datetime.now(_unloved_timezone.utc).isoformat(),
        "payload": payload,
        "normalized": normalized,
        "recommended_content_style": recommended_content_style,
    }

    path = _UNLOVED_APF_IMPORT_DIR / f"{token}.json"
    path.write_text(_unloved_json.dumps(doc, ensure_ascii=False, indent=2))

    base = _unloved_os.getenv("SHADOWCAST_PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
    return {
        "ok": True,
        "token": token,
        "productName": normalized.get("productName"),
        "recommended_content_style": recommended_content_style,
        "normalized": normalized,
        "open_url": f"{base}/?apf_draft={token}",
    }

@app.get("/api/import-apf/direct/{token}")
async def unloved_get_apf_direct_import(token: str):
    if not token or "/" in token or "\\" in token or ".." in token:
        raise _UnlovedHTTPException(status_code=400, detail="Invalid token.")

    path = _UNLOVED_APF_IMPORT_DIR / f"{token}.json"
    if not path.exists():
        raise _UnlovedHTTPException(status_code=404, detail="APF import draft not found.")

    return _unloved_json.loads(path.read_text())
# END UNLOVED_APF_DIRECT_IMPORT_ENDPOINTS

# ── Serve Frontend ────────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

if (FRONTEND_DIR / "index.html").exists():
    assets_dir = FRONTEND_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="static_assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        file_path = FRONTEND_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(FRONTEND_DIR / "index.html"))
else:
    @app.get("/")
    def root():
        return {"message": "ShadowCast API v4.0 — by Unloved Productions | Forged in Passion"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

