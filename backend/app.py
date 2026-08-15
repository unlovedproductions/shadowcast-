"""
ShadowCast — FastAPI Backend by Unloved Productions
Supports single product, batch CSV upload, content styles, and
research-based honest review generation.
"""

import csv
import io
import json
import logging
import os
import re
import shutil
import subprocess
import time
import uuid
import threading
import traceback
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv
import sentry_sdk
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

load_dotenv(Path(__file__).parent / ".env")
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

import llm_config
from llm_client import list_ollama_models, list_openai_compatible_models, test_chat_completion
from amazon_scraper import scrape_amazon_product
from youtube_research import research_youtube_keywords
from api_models import (
    BatchGenerateRequest,
    ConfigResponse,
    ContentStylesResponse,
    ErrorResponse,
    GenerateRequest,
    GenerateResponse,
    HealthResponse,
    HooksResponse,
    JobAuditResponse,
    JobResultsResponse,
    JobStatusResponse,
    LLMConfigRequest,
    LLMModelsResponse,
    LLMTestResponse,
    MetricRequest,
    MediaLibraryResponse,
    ProductInfo,
    ProvidersResponse,
    ReadinessChecks,
    ReadinessResponse,
    RetryMissingResponse,
    ScrapeAmazonRequest,
    TTSProvidersResponse,
    YouTubeResearchRequest,
)
from research_enrichment import enrich_product_research
from llm_context import clear_job_context, merge_llm_calls_into_job, set_job_context
from script_generator import (
    generate_selected_scripts, HOOK_TYPES, HOOK_DESCRIPTIONS,
)
from content_styles import (
    CONTENT_STYLES,
    DEFAULT_CONTENT_STYLE,
    normalize_content_style,
    style_badge_text,
    style_requires_competitors,
)
from script_postprocessor import enrich_script
from apf_import import (
    assess_product_completeness,
    as_snake_product_info,
    dedupe_products_by_name,
    extract_apf_product_payloads,
    normalize_apf_payload,
)
from video_renderer import (
    render_short_form_video,
    render_long_form_video,
    resolve_video_preset,
    compute_render_fingerprint,
)
from youtube_assets_generator import generate_youtube_assets, save_posting_package_readable
from thumbnail_generator import generate_thumbnail_set, add_badge
from product_media import resolve_product_image
from visual_quality import audit_thumbnail_contrast
from tts_generator import get_available_providers as get_tts_providers, get_best_provider as get_best_tts
from social_poster import SocialPoster, get_platform_status
from analytics_tracker import AnalyticsTracker, create_tracking_link
from youtube_analytics import YouTubeAnalyticsClient, extract_youtube_video_id
from oauth_manager import OAuthManager
from publish_service import PublishService, resolve_job_assets, _slugify as job_slugify
from publish_quality import evaluate_publish_quality
from publishers.rumble_publisher import RumblePublisher
from bg_generator import generate_background, get_style_for_content, apply_vignette, apply_film_grain
from video_claim_audit import audit_output
from video_claims import FORMAT_CLAIMS, LONG_FORM, SHORT_FORM, sum_segment_durations
from openapi_customize import customize_openapi
from broll import any_broll_files
from media_library import media_library_snapshot
from sound_design import music_bed_moods, music_beds_present
from auth_public_routes import is_public_path

logging.basicConfig(
    level=logging.INFO,
    format='{"level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
)
logger = logging.getLogger("shadowcast")

_SENTRY_SCRUB_HEADERS = frozenset({"authorization", "cookie", "x-service-key"})
_SENTRY_DROP_TRACE_PATHS = frozenset({"/api/health", "/api/readiness"})


def _sentry_frontend_loader_key() -> str:
    dsn = (os.getenv("SENTRY_FRONTEND_DSN") or "").strip()
    if not dsn or "@" not in dsn:
        return ""
    try:
        return dsn.split("://", 1)[1].split("@", 1)[0]
    except IndexError:
        return ""


def _sentry_before_send(event, hint):
    request_data = event.get("request")
    if isinstance(request_data, dict):
        headers = request_data.get("headers")
        if isinstance(headers, dict):
            for key in list(headers):
                if str(key).lower() in _SENTRY_SCRUB_HEADERS:
                    headers[key] = "[Filtered]"
    return event


def _sentry_traces_sampler(sampling_context):
    asgi_scope = sampling_context.get("asgi_scope") or {}
    path = asgi_scope.get("path") or ""
    if path in _SENTRY_DROP_TRACE_PATHS:
        return 0.0
    parent_sampled = sampling_context.get("parent_sampled")
    if parent_sampled is not None:
        return float(parent_sampled)
    return 1.0


if os.getenv("SENTRY_DSN", "").strip():
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        environment=os.getenv("SENTRY_ENVIRONMENT", "development"),
        release=os.getenv("SENTRY_RELEASE") or None,
        send_default_pii=False,
        traces_sampler=_sentry_traces_sampler,
        enable_logs=True,
        ignore_errors=["JobCancelled"],
        before_send=_sentry_before_send,
    )

_oauth_rate_buckets: dict[str, list[float]] = defaultdict(list)
_OAUTH_RATE_LIMIT = 60
_OAUTH_RATE_WINDOW = 60.0


@asynccontextmanager
async def lifespan(_app: FastAPI):
    cleanup_old_job_outputs()
    _resume_incomplete_jobs()
    yield


app = FastAPI(
    title="ShadowCast by Unloved Productions",
    version="4.0",
    description=(
        "Affiliate video generation API: product research, script generation, "
        "video rendering, publishing, and analytics."
    ),
    servers=[{"url": "/", "description": "Current deployment host"}],
    lifespan=lifespan,
)

_cors_raw = os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")
_cors_origins = [origin.strip() for origin in _cors_raw.split(",") if origin.strip()]
if os.getenv("CORS_ALLOW_ALL", "").lower() in ("1", "true", "yes"):
    _cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_COMMON_ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Bad request"},
    401: {"model": ErrorResponse, "description": "Unauthorized"},
    404: {"model": ErrorResponse, "description": "Not found"},
    409: {"model": ErrorResponse, "description": "Conflict"},
    422: {"model": ErrorResponse, "description": "Validation error"},
    503: {"model": ErrorResponse, "description": "Service unavailable"},
}


def _error_code(status_code: int) -> str:
    return {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }.get(status_code, f"HTTP_{status_code}")


def _error_payload(status_code: int, message: str, details: list | None = None) -> dict:
    detail_items = details or []
    return {
        "detail": message,
        "error": {
            "code": _error_code(status_code),
            "message": message,
            "details": detail_items,
        },
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code >= 500:
        sentry_sdk.capture_exception(exc)
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(exc.status_code, message),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = [
        {
            "field": ".".join(str(part) for part in err.get("loc", ())),
            "code": err.get("type", "validation_error"),
            "message": err.get("msg", "Invalid value"),
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=_error_payload(422, "Request validation failed", details),
    )

# Global middleware to enforce internal service auth for non-GET requests


@app.middleware("http")
async def enforce_internal_auth_middleware(request: Request, call_next):
    # UNLOVED_PUBLIC_UI_ROUTE_AUTH_BYPASS — allowlist shared with openapi_customize
    path = request.url.path
    if is_public_path(path):
        return await call_next(request)
    internal_secret = os.getenv("INTERNAL_SERVICE_SECRET", "")
    if internal_secret and request.method != "GET":
        service_key = request.headers.get("X-Service-Key")
        if service_key != internal_secret:
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


@app.middleware("http")
async def security_headers_and_rate_limit(request: Request, call_next):
    """In-process OAuth rate limiting (slowapi-compatible bucket pattern)."""
    path = request.url.path
    if path.startswith("/api/oauth"):
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        bucket = [t for t in _oauth_rate_buckets[ip] if now - t < _OAUTH_RATE_WINDOW]
        if len(bucket) >= _OAUTH_RATE_LIMIT:
            return JSONResponse(status_code=429, content=_error_payload(429, "Rate limit exceeded"))
        bucket.append(now)
        _oauth_rate_buckets[ip] = bucket

    response = await call_next(request)
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data: https:; script-src 'self' 'unsafe-inline' https://js.sentry-cdn.com https://browser.sentry-cdn.com; style-src 'self' 'unsafe-inline'; connect-src 'self' https://*.sentry.io https://*.ingest.sentry.io; worker-src 'self' blob:",
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


from path_safety import OUTPUT_BASE, _PROTECTED_OUTPUT_NAMES, _safe_job_file
from job_store import (
    JobCancelled,
    _active_job_threads,
    _add_job_warning,
    _job_heartbeats,
    _job_path,
    _job_state_lock,
    _job_thread_lock,
    _load_job,
    _output_max_age_days,
    _raise_if_cancelled,
    _save_job,
    _start_job_thread,
    cleanup_old_job_outputs,
    jobs,
)

# ── Job store (imported from job_store; path helpers from path_safety) ─

def _batch_workers() -> int:
    """Max concurrent products in a batch job. Default 1 = sequential."""
    raw = (os.getenv("SHADOWCAST_BATCH_WORKERS") or "1").strip()
    try:
        n = int(raw)
    except ValueError:
        logging.warning("Invalid SHADOWCAST_BATCH_WORKERS=%r; using 1", raw)
        return 1
    return 1 if n < 1 else n


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


def _probe_mp4_ok(path: Path) -> tuple[bool, str]:
    command = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", "-show_format", str(path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return True, ""
    if result.returncode != 0:
        return False, "ffprobe could not read MP4"
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False, "ffprobe returned invalid JSON"
    streams = payload.get("streams", [])
    has_video = any(
        isinstance(s, dict) and s.get("codec_type") == "video" for s in streams
    )
    if not has_video:
        return False, "MP4 has no video stream"
    fmt = payload.get("format", {})
    duration = fmt.get("duration")
    if duration is not None:
        try:
            if float(duration) <= 0:
                return False, "MP4 has zero duration"
        except (TypeError, ValueError):
            pass
    return True, ""


def _youtube_package_ok(path: Path) -> bool:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    seo_title = str(data.get("seo_title", "")).strip()
    return bool(seo_title) and not data.get("_shadowcast_fallback", False)


def _script_ready_for_render(script: dict) -> tuple[bool, str]:
    """Fail-fast before MoviePy: require speakable overlay segments."""
    if not isinstance(script, dict):
        return False, "script is not an object"
    segments: list = []
    if isinstance(script.get("segments"), list):
        segments.extend(script["segments"])
    for chapter in script.get("chapters") or []:
        if isinstance(chapter, dict) and isinstance(chapter.get("segments"), list):
            segments.extend(chapter["segments"])
    if not segments:
        return False, "script has no segments"
    texts = [str(s.get("text") or "").strip() for s in segments if isinstance(s, dict)]
    if not any(texts):
        return False, "script segments have empty text"
    fmt = str(script.get("format") or "").strip()
    if not fmt:
        fmt = LONG_FORM if script.get("chapters") else SHORT_FORM
    if fmt == LONG_FORM:
        total = sum_segment_durations(script, LONG_FORM)
        min_s = FORMAT_CLAIMS[LONG_FORM].min_duration_seconds
        if total < min_s:
            return False, f"long_form duration {total:.1f}s below {min_s:.0f}s floor"
    return True, ""


def _artifact_ok(path: Path, artifact_type: str = "generic", formats: Optional[List[str]] = None) -> bool:
    try:
        file_ok = path.is_file() and path.stat().st_size > 0
    except OSError:
        return False
    if not file_ok:
        return False
    if artifact_type == "script":
        script_payload = _load_cached_script_payload(path)
        if script_payload is None:
            return False
        expected_formats = formats or ["short_form", "long_form"]
        valid, _ = _validate_script_payload(script_payload, expected_formats)
        return valid
    if artifact_type == "youtube_package" or path.name.endswith("_youtube_package.json"):
        return _youtube_package_ok(path)
    if path.suffix.lower() == ".mp4":
        ok, _ = _probe_mp4_ok(path)
        return ok
    return True


def _video_render_meta_path(video_path: Path) -> Path:
    return video_path.with_suffix(video_path.suffix + ".render.json")


def _write_video_render_meta(video_path: Path, fingerprint: str, options: dict) -> None:
    meta = {
        "fingerprint": fingerprint,
        "options": options,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _video_render_meta_path(video_path).write_text(json.dumps(meta, indent=2))


def _video_cache_ok(video_path: Path, fingerprint: str) -> bool:
    """Reuse MP4 only when structural probe passes and fingerprint matches."""
    if not _artifact_ok(video_path):
        return False
    meta_path = _video_render_meta_path(video_path)
    if not meta_path.is_file():
        return False
    try:
        meta = json.loads(meta_path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(meta, dict) and meta.get("fingerprint") == fingerprint


def _apply_llm_warnings(job: dict) -> None:
    for call in job.get("llm_calls", [])[-8:]:
        if call.get("validator_pass") is False and call.get("validator_errors"):
            detail = "; ".join(str(item) for item in call["validator_errors"][:3])
            _add_job_warning(job, f"LLM validator ({call.get('label', 'call')}): {detail}")


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
            or len(job.get("warnings") or []) > 0
        ),
    }


def _run_job_audit(job_dir: Path) -> dict:
    try:
        return audit_output(job_dir)
    except Exception as exc:
        return {
            "output_dir": str(job_dir),
            "videos_checked": 0,
            "fail_count": 0,
            "warn_count": 0,
            "findings": [],
            "audit_error": str(exc),
        }


def _finalize_job_status(job_id: str, job_dir: Path, *, done_message: str) -> None:
    job = jobs[job_id]
    if job.get("cancel_requested"):
        job["status"] = "cancelled"
        job["current_step"] = "Cancelled by operator"
        job["progress"] = int(job.get("progress") or 0)
        _save_job(job_id)
        return

    audit_result = _run_job_audit(job_dir)
    job["audit"] = audit_result
    summary = _summarize_job_output(job)
    job["summary"] = summary

    fail_count = int(audit_result.get("fail_count") or 0)
    warn_count = int(audit_result.get("warn_count") or 0)
    has_outputs = summary.get("videos_ready", 0) > 0

    if fail_count > 0:
        job["errors"].append(f"Video claim audit: {fail_count} FAIL finding(s)")
    if warn_count > 0:
        _add_job_warning(job, f"Video claim audit: {warn_count} WARN finding(s)")
    if audit_result.get("audit_error"):
        _add_job_warning(job, f"Video claim audit error: {audit_result['audit_error']}")

    if fail_count > 0 or not has_outputs:
        job["status"] = "error"
        job["current_step"] = (
            done_message if has_outputs else "Error: No video outputs produced"
        )
    elif summary.get("is_partial"):
        job["status"] = "partial"
        job["current_step"] = f"{done_message} (review warnings)"
    else:
        job["status"] = "complete"
        job["current_step"] = done_message

    job["progress"] = 100
    _save_job(job_id)


_VARIANT_MP4_RE = re.compile(r"_(?P<hook>[^_/]+)_(?P<fmt>short_form|long_form)\.mp4$")


def _caption_hint_from_assets(assets: dict | None) -> str:
    if not assets:
        return ""
    return str(assets.get("pinned_comment") or assets.get("seo_description") or "").strip()


def _build_postable_variant(
    *,
    hook_type: str,
    video_format: str,
    video_file: str,
    product_slug: str | None,
    product_name: str,
    content_style: str,
    assets: dict | None,
    thumbnail_file: str | None,
) -> dict:
    slug_prefix = f"{product_slug}/" if product_slug else ""
    label_name = (product_name or "Product")[:50]
    style = content_style or hook_type.replace("_", " ")
    fmt_label = fmt_display(video_format)
    hashtags = (assets or {}).get("hashtags") or []
    return {
        "hook_type": hook_type,
        "video_format": video_format,
        "video_file": video_file,
        "path_prefix": slug_prefix,
        "thumbnail_file": thumbnail_file,
        "product_slug": product_slug,
        "label": f"{label_name} — {style} — {fmt_label}",
        "caption_hint": _caption_hint_from_assets(assets),
        "hashtags": hashtags if isinstance(hashtags, list) else [],
        "seo_title": str((assets or {}).get("seo_title") or ""),
    }


def _variants_from_hooks(
    hooks: dict,
    job_dir: Path,
    *,
    product_slug: str | None,
    product_name: str,
    content_style: str,
) -> list[dict]:
    variants: list[dict] = []
    base_dir = job_dir / product_slug if product_slug else job_dir
    prefix = f"{product_slug}/" if product_slug else ""

    for hook_type, hook_data in (hooks or {}).items():
        if not isinstance(hook_data, dict):
            continue
        videos = hook_data.get("videos") or {}
        assets_map = hook_data.get("youtube_assets") or {}
        thumbs = hook_data.get("thumbnails") or {}

        for video_format, video_fname in videos.items():
            if not video_fname:
                continue
            video_path = base_dir / video_fname
            if not _artifact_ok(video_path):
                continue

            assets = assets_map.get(video_format)
            if not assets:
                pkg_matches = sorted(base_dir.glob(f"*_{hook_type}_{video_format}_youtube_package.json"))
                if pkg_matches:
                    try:
                        assets = json.loads(pkg_matches[0].read_text())
                    except (OSError, json.JSONDecodeError):
                        assets = None
            if not assets:
                continue

            thumb_fname = thumbs.get("variant_a") or next(iter(thumbs.values()), None)
            if not thumb_fname:
                thumb_matches = sorted(base_dir.glob(f"*_{hook_type}_thumbnail_*.png"))
                thumb_fname = thumb_matches[0].name if thumb_matches else None

            variants.append(
                _build_postable_variant(
                    hook_type=hook_type,
                    video_format=video_format,
                    video_file=video_fname,
                    product_slug=product_slug,
                    product_name=product_name,
                    content_style=content_style,
                    assets=assets,
                    thumbnail_file=thumb_fname,
                )
            )
    return variants


def _glob_postable_variants(job_dir: Path, existing_keys: set[tuple]) -> list[dict]:
    variants: list[dict] = []
    for mp4 in sorted(job_dir.rglob("*.mp4")):
        if "video_only" in mp4.name:
            continue
        match = _VARIANT_MP4_RE.search(mp4.name)
        if not match:
            continue

        hook_type = match.group("hook")
        video_format = match.group("fmt")
        rel = mp4.relative_to(job_dir)
        product_slug = rel.parts[0] if len(rel.parts) > 1 else None
        key = (hook_type, video_format, product_slug)
        if key in existing_keys:
            continue

        pkg_path = mp4.with_name(f"{mp4.stem}_youtube_package.json")
        if not pkg_path.exists():
            continue

        try:
            assets = json.loads(pkg_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue

        thumb_matches = sorted(mp4.parent.glob(f"*_{hook_type}_thumbnail_*.png"))
        thumb_fname = thumb_matches[0].name if thumb_matches else None
        product_name = product_slug.replace("_", " ") if product_slug else job_dir.name

        variants.append(
            _build_postable_variant(
                hook_type=hook_type,
                video_format=video_format,
                video_file=mp4.name if len(rel.parts) == 1 else str(Path(*rel.parts[1:])),
                product_slug=product_slug,
                product_name=product_name,
                content_style=hook_type,
                assets=assets,
                thumbnail_file=thumb_fname,
            )
        )
        existing_keys.add(key)
    return variants


def _postable_job_entry(job_id: str, job_dir: Path) -> dict | None:
    job = _load_job(job_id)
    if not job:
        return None

    variants: list[dict] = []
    batch_products: list[dict] = []
    content_style = str(job.get("content_style") or job.get("product_info", {}).get("content_style") or "")

    if job.get("mode") == "batch":
        for product_result in job.get("product_results") or []:
            product_name = str(product_result.get("product_name") or "Product")
            product_slug = slugify(product_name)
            batch_products.append({"slug": product_slug, "name": product_name})
            variants.extend(
                _variants_from_hooks(
                    product_result.get("hooks") or {},
                    job_dir,
                    product_slug=product_slug,
                    product_name=product_name,
                    content_style=str(product_result.get("content_style") or content_style),
                )
            )
    else:
        product_name = str(job.get("product_info", {}).get("product_name") or job_id)
        variants.extend(
            _variants_from_hooks(
                job.get("results") or {},
                job_dir,
                product_slug=None,
                product_name=product_name,
                content_style=content_style,
            )
        )

    existing_keys = {
        (v["hook_type"], v["video_format"], v.get("product_slug"))
        for v in variants
    }
    variants.extend(_glob_postable_variants(job_dir, existing_keys))
    if not variants:
        return None

    job_path = _job_path(job_id)
    updated_at = datetime.fromtimestamp(job_path.stat().st_mtime, tz=timezone.utc).isoformat()
    product_name = str(job.get("product_info", {}).get("product_name") or "")
    if not product_name and batch_products:
        product_name = batch_products[0]["name"]

    return {
        "job_id": job_id,
        "status": job.get("status", "unknown"),
        "mode": job.get("mode", "single"),
        "product_name": product_name,
        "content_style": content_style,
        "updated_at": updated_at,
        "batch_products": batch_products,
        "variants": variants,
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


# ── CSV Parsing ───────────────────────────────────────────────────────
CSV_COLUMNS = [
    "product_name", "niche", "key_features", "price", "affiliate_link",
    "keywords", "target_audience", "product_category", "competitors",
    "unique_selling_point", "discount_info", "coupon_code",
    "common_complaints", "common_praises", "who_not_for",
    "series_name", "price_comparison", "content_style", "amazon_url", "image_url",
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
            "amazon_url": norm.get("amazon_url", ""),
            "image_url": norm.get("image_url", ""),
        }
        products.append(product)
    return products


def _completeness_gate(product: dict, content_style: str | None = None) -> list[str]:
    """Raise HTTP 422 on blocking gaps; return warning field names."""
    assessment = assess_product_completeness(product, content_style)
    if assessment["blocking"]:
        name = assessment.get("product_name") or product.get("product_name") or "(unnamed)"
        raise HTTPException(
            status_code=422,
            detail={
                "message": f"Product incomplete for generate: {name}",
                "blocking": assessment["blocking"],
                "warnings": assessment["warnings"],
                "content_style": assessment["content_style"],
            },
        )
    return assessment["warnings"]


def _prepare_products_for_generate(
    products: list[dict],
    *,
    default_style: str,
) -> tuple[list[dict], list[str]]:
    deduped, dropped = dedupe_products_by_name(products)
    warnings: list[str] = []
    if dropped:
        warnings.append(f"Dropped {len(dropped)} duplicate product name(s): {', '.join(dropped[:5])}")
    prepared = []
    for product in deduped:
        item = as_snake_product_info(product)
        item.update({k: product[k] for k in product if k.startswith("_")})
        if not item.get("product_category"):
            item["product_category"] = item.get("niche", "General")
        item["content_style"] = normalize_content_style(
            item.get("content_style") or default_style
        )
        field_warnings = _completeness_gate(item, item["content_style"])
        for field in field_warnings:
            name = item.get("product_name", "?")
            if field == "image_url":
                warnings.append(f"{name}: No product image — thumbs will be text-only")
            elif field == "claim_ledger":
                warnings.append(f"{name}: No cited claims — scripts will hedge or invent")
            else:
                warnings.append(f"{name}: weak/missing {field}")
        prepared.append(item)
    if not prepared:
        raise HTTPException(status_code=400, detail="No valid products after completeness/dedupe.")
    return prepared, warnings


def _tts_default_enabled() -> bool:
    """API default: TTS on unless SHADOWCAST_TTS_DEFAULT=0."""
    return os.getenv("SHADOWCAST_TTS_DEFAULT", "1").strip() not in ("0", "false", "False")


def _resolve_use_tts(requested: bool) -> bool:
    """Honor client flag; SHADOWCAST_TTS_DEFAULT=0 forces off."""
    if not _tts_default_enabled():
        return False
    return bool(requested)


def _resolve_product_image_path(product: dict) -> str | None:
    path = resolve_product_image(product.get("image_url") or product.get("imageUrl") or "")
    return str(path) if path else None


# ── Single Product Generation Worker ──────────────────────────────────
def _run_single_product(job_id: str, product: dict, product_dir: Path,
                        hook_types: list, formats: list,
                        content_style: str,
                        step_offset: int, total_steps: int,
                        audio_enabled: bool = True,
                        audio_mood: str = "auto",
                        use_tts: bool = True,
                        tts_provider: str = "auto",
                        tts_voice: Optional[str] = None,
                        video_preset: str = "medium"):
    job = jobs[job_id]
    slug = slugify(product["product_name"])
    step = step_offset
    set_job_context(job_id)
    _raise_if_cancelled(job_id)

    # Use product-level content_style if set, otherwise job-level
    effective_style = normalize_content_style(product.get("content_style") or content_style)
    product["content_style"] = effective_style

    research_dir = OUTPUT_BASE / job_id / "research" / slug
    try:
        product = enrich_product_research(product, research_dir=research_dir)
        for warning in product.get("_research_warnings") or []:
            job.setdefault("warnings", []).append(f"Research: {warning}")
    except Exception as exc:
        job.setdefault("warnings", []).append(f"Research enrichment skipped: {exc}")

    mood_arg = None if audio_mood in (None, "", "auto") else audio_mood
    render_preset = resolve_video_preset(video_preset)
    product_image_path = _resolve_product_image_path(product)
    if product.get("image_url") and not product_image_path:
        job.setdefault("warnings", []).append(
            f"[{product.get('product_name', '?')}] Product image_url could not be downloaded; using procedural backgrounds."
        )
    elif not (product.get("image_url") or "").strip():
        job.setdefault("warnings", []).append(
            f"[{product.get('product_name', '?')}] No product image — thumbs will be text-only"
        )

    all_scripts = {}
    all_yt_packages = {}
    product_results = {"product_name": product["product_name"], "hooks": {}}
    phase_timings_ms: dict[str, float] = {}

    def _mark_phase(name: str, started: float) -> None:
        phase_timings_ms[name] = round((time.perf_counter() - started) * 1000, 1)

    # Phase 1: Scripts
    _phase_t0 = time.perf_counter()
    for hook_type in hook_types:
        _raise_if_cancelled(job_id)
        hook_name = hook_type.replace("_", " ").title()
        fname = f"{slug}_{hook_type}_scripts.json"
        script_path = product_dir / fname
        job["current_step"] = f"[{product['product_name']}] Generating {hook_name} scripts..."
        job["progress"] = int(step / total_steps * 100)
        _save_job(job_id)

        try:
            if _artifact_ok(script_path, artifact_type="script", formats=formats):
                try:
                    with open(script_path) as f:
                        scripts_file = json.load(f)
                except (OSError, json.JSONDecodeError):
                    scripts_file = {}
                script_payload = scripts_file.get("scripts", {}) if isinstance(scripts_file, dict) else {}
                if not isinstance(script_payload, dict):
                    script_payload = {}
                changed = False
                for fmt in formats:
                    if fmt not in script_payload:
                        continue
                    enriched = enrich_script(script_payload[fmt], product, effective_style)
                    if enriched != script_payload[fmt]:
                        script_payload[fmt] = enriched
                        changed = True
                if changed and isinstance(scripts_file, dict):
                    scripts_file["scripts"] = script_payload
                    scripts_file["product_info"] = product
                    scripts_file["content_style"] = effective_style
                    with open(str(script_path), "w") as f:
                        json.dump(scripts_file, f, indent=2)
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
                style_ctx = scripts.get("product_info", {}).get("_style_rules_context")
                if style_ctx:
                    product["_style_rules_context"] = style_ctx
                    job.setdefault("style_rules_retrieval", {})[hook_type] = {
                        "hits": len(style_ctx),
                        "sources": [
                            hit.get("source")
                            for hit in style_ctx
                            if isinstance(hit, dict) and hit.get("source")
                        ],
                    }
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

    _mark_phase("scripts", _phase_t0)

    # Phase 2: Videos
    _phase_t0 = time.perf_counter()
    for hook_type in hook_types:
        _raise_if_cancelled(job_id)
        hook_name = hook_type.replace("_", " ").title()
        scripts_data = all_scripts.get(hook_type, {})

        for fmt in formats:
            _raise_if_cancelled(job_id)
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
                ready, ready_detail = _script_ready_for_render(scripts_data[fmt])
                if not ready:
                    job["errors"].append(
                        f"[{product['product_name']}] Video ({hook_type} {fmt}): "
                        f"fail-fast before render — {ready_detail}"
                    )
                    step += 1
                    job["progress"] = int(step / total_steps * 100)
                    _save_job(job_id)
                    continue

                render_options = {
                    "product_name": product.get("product_name", ""),
                    "price": product.get("price", ""),
                    "series_name": product.get("series_name", ""),
                    "content_style": effective_style,
                    "competitors": product.get("competitors", []),
                    "audio_enabled": audio_enabled,
                    "audio_mood": mood_arg,
                    "use_tts": use_tts,
                    "tts_provider": tts_provider,
                    "tts_voice": tts_voice,
                    "video_preset": render_preset,
                    "product_image_path": product_image_path or "",
                }
                fingerprint = compute_render_fingerprint(
                    scripts_data[fmt],
                    fmt=fmt,
                    render_options=render_options,
                )
                if _video_cache_ok(video_path, fingerprint):
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
                        render_warnings=job.setdefault("warnings", []),
                        product_image_path=product_image_path,
                    )
                    if fmt == "short_form":
                        render_short_form_video(scripts_data[fmt], str(video_path), **render_kwargs)
                    else:
                        render_long_form_video(scripts_data[fmt], str(video_path), **render_kwargs)
                    _write_video_render_meta(video_path, fingerprint, render_options)

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

    _mark_phase("videos", _phase_t0)

    # Phase 3: YouTube Assets
    _phase_t0 = time.perf_counter()
    for hook_type in hook_types:
        _raise_if_cancelled(job_id)
        hook_name = hook_type.replace("_", " ").title()
        scripts_data = all_scripts.get(hook_type, {})
        all_yt_packages[hook_type] = {}

        for fmt in formats:
            _raise_if_cancelled(job_id)
            if fmt not in scripts_data:
                step += 1
                continue

            hook_videos = (
                product_results.get("hooks", {})
                .get(hook_type, {})
                .get("videos", {})
            )
            if fmt not in hook_videos:
                step += 1
                continue

            fl = fmt_display(fmt)
            fname = f"{slug}_{hook_type}_{fmt_label(fmt)}_youtube_package.json"
            yt_path = product_dir / fname
            job["current_step"] = f"[{product['product_name']}] Generating {hook_name} {fl} YouTube package..."
            job["progress"] = int(step / total_steps * 100)
            _save_job(job_id)

            try:
                if _artifact_ok(yt_path, artifact_type="youtube_package"):
                    with open(yt_path) as f:
                        assets = json.load(f)
                    job["current_step"] = f"[{product['product_name']}] Using cached {hook_name} {fl} YouTube package..."
                else:
                    assets = generate_youtube_assets(product, scripts_data[fmt], fmt)
                    if assets.get("_shadowcast_fallback"):
                        debug_path = yt_path.with_suffix(".fallback.json")
                        with open(str(debug_path), "w") as f:
                            json.dump(assets, f, indent=2)
                        try:
                            if yt_path.exists():
                                yt_path.unlink()
                        except OSError:
                            pass
                        msg = (
                            f"[{product['product_name']}] YT package ({hook_type} {fmt}): "
                            "LLM fallback stub — not registered as deliverable"
                        )
                        _add_job_warning(job, msg)
                        job["errors"].append(msg)
                        step += 1
                        job["progress"] = int(step / total_steps * 100)
                        _save_job(job_id)
                        continue
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

    _mark_phase("youtube_assets", _phase_t0)

    # Phase 4: Thumbnails
    _phase_t0 = time.perf_counter()
    _raise_if_cancelled(job_id)
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
                yt_assets = (product_results.get("hooks", {}).get(hook_type) or {}).get("youtube_assets") or {}
                pkg = yt_assets.get("short_form") or yt_assets.get("long_form") or {}
                thumb_set = generate_thumbnail_set(
                    product.get('product_name', 'Product'),
                    hook_type,
                    content_style_name,
                    keywords=product.get('keywords', []) if isinstance(product.get('keywords'), list) else [],
                    product_image_path=product_image_path,
                    thumbnail_text_primary=pkg.get("thumbnail_text_primary"),
                    thumbnail_text_secondary=pkg.get("thumbnail_text_secondary"),
                )
                for variant_key, thumb_img in thumb_set.items():
                    badge_text = style_badge_text(content_style_name)

                    if badge_text:
                        thumb_img = add_badge(thumb_img, badge_text)

                    thumb_fname = f"{slug}_{hook_type}_thumbnail_{variant_key}.png"
                    thumb_path = product_dir / thumb_fname
                    thumb_img.save(str(thumb_path))
                    severity, _expected, actual, detail = audit_thumbnail_contrast(thumb_path)
                    if severity == "WARN":
                        job.setdefault("warnings", []).append(
                            f"[{product['product_name']}] Thumbnail {variant_key} contrast {actual}: {detail}"
                        )

                    if hook_type not in product_results["hooks"]:
                        product_results["hooks"][hook_type] = {}
                    if "thumbnails" not in product_results["hooks"][hook_type]:
                        product_results["hooks"][hook_type]["thumbnails"] = {}
                    product_results["hooks"][hook_type]["thumbnails"][variant_key] = thumb_fname
        except Exception as e:
            job["errors"].append(f"[{product['product_name']}] Thumbnails ({hook_type}): {str(e)}")
            traceback.print_exc()

    _mark_phase("thumbnails", _phase_t0)
    product_results["phase_timings_ms"] = phase_timings_ms
    job.setdefault("phase_timings", []).append(
        {"product_name": product["product_name"], **phase_timings_ms}
    )

    # Save combined posting package
    try:
        fname = f"{slug}_YOUTUBE_POSTING_PACKAGE.txt"
        save_posting_package_readable(all_yt_packages, product, str(product_dir / fname))
    except Exception as e:
        _add_job_warning(job, f"[{product['product_name']}] Posting package TXT failed: {e}")

    merge_llm_calls_into_job(jobs, job_id)
    _apply_llm_warnings(job)
    clear_job_context()
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
        _finalize_job_status(job_id, job_dir, done_message="Done!")
    except JobCancelled:
        job["status"] = "cancelled"
        job["current_step"] = "Cancelled by operator"
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
    workers = min(_batch_workers(), max(len(products), 1))
    render_kwargs = dict(
        audio_enabled=job.get("audio_enabled", True),
        audio_mood=job.get("audio_mood", "auto"),
        use_tts=job.get("use_tts", False),
        tts_provider=job.get("tts_provider", "auto"),
        tts_voice=job.get("tts_voice"),
        video_preset=job.get("video_preset", "medium"),
    )

    def _process_product(index: int, product: dict):
        _raise_if_cancelled(job_id)
        slug = slugify(product["product_name"])
        product_dir = job_dir / slug
        product_dir.mkdir(exist_ok=True)
        with _job_state_lock:
            job["current_step"] = (
                f"Product {index + 1}/{len(products)}: {product['product_name']}"
            )
            _save_job(job_id)
        result, _ = _run_single_product(
            job_id,
            product,
            product_dir,
            hook_types,
            formats,
            content_style,
            index * steps_per,
            total_steps,
            **render_kwargs,
        )
        return result

    try:
        all_product_results = []

        if workers == 1:
            step_offset = 0
            for i, product in enumerate(products):
                _raise_if_cancelled(job_id)
                slug = slugify(product["product_name"])
                product_dir = job_dir / slug
                product_dir.mkdir(exist_ok=True)

                job["current_step"] = f"Product {i+1}/{len(products)}: {product['product_name']}"
                _save_job(job_id)

                result, step_offset = _run_single_product(
                    job_id, product, product_dir, hook_types, formats,
                    content_style, step_offset, total_steps,
                    **render_kwargs,
                )
                all_product_results.append(result)
                job["product_results"] = all_product_results
                _save_job(job_id)
        else:
            slot_results: list = [None] * len(products)
            cancelled = False
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_map = {
                    executor.submit(_process_product, i, product): i
                    for i, product in enumerate(products)
                }
                for future in as_completed(future_map):
                    i = future_map[future]
                    try:
                        slot_results[i] = future.result()
                    except JobCancelled:
                        cancelled = True
                        for pending in future_map:
                            pending.cancel()
                        break
                    except Exception as exc:
                        name = products[i].get("product_name", f"product_{i}")
                        with _job_state_lock:
                            job.setdefault("errors", []).append(
                                f"[{name}] Product failed: {exc}"
                            )
                        traceback.print_exc()
                    with _job_state_lock:
                        job["product_results"] = [r for r in slot_results if r is not None]
                        _save_job(job_id)
            if cancelled:
                raise JobCancelled(job_id)
            all_product_results = [r for r in slot_results if r is not None]

        job["product_results"] = all_product_results

        try:
            zip_path = job_dir / "all_products.zip"
            with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(str(job_dir)):
                    for file in files:
                        if file == "all_products.zip":
                            continue
                        full = os.path.join(root, file)
                        arcname = os.path.relpath(full, str(job_dir))
                        zf.write(full, arcname)
        except Exception as zip_exc:
            _add_job_warning(job, f"ZIP creation failed: {zip_exc}")

        _finalize_job_status(
            job_id,
            job_dir,
            done_message=f"Done! {len(products)} products processed.",
        )
    except JobCancelled:
        job["status"] = "cancelled"
        job["current_step"] = "Cancelled by operator"
        _save_job(job_id)
    except Exception as e:
        job["status"] = "error"
        job["current_step"] = f"Error: {str(e)}"
        job["errors"].append(str(e))
        _save_job(job_id)
        traceback.print_exc()


# ── Endpoints ─────────────────────────────────────────────────────────

@app.get("/api/health", response_model=HealthResponse, responses=_COMMON_ERROR_RESPONSES, tags=["ops"])
def health_check():
    return {"status": "ok", "app": "ShadowCast", "version": "4.0"}


@app.get("/api/openapi.json", tags=["ops"])
def openapi_spec():
    return JSONResponse(app.openapi())


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
        detail = f"LLM unreachable at {base_url}: {exc}"
        if cfg.provider == "ollama":
            detail += " Start Ollama (ollama serve) and pull a model (ollama pull qwen2.5:14b-instruct-q5_K_M)."
        return False, detail
    detail = f"LLM unreachable at {base_url}."
    if cfg.provider == "ollama":
        detail += " Start Ollama (ollama serve) and verify the model is pulled."
    return False, detail


def _ensure_generation_ready() -> None:
    blockers: List[str] = []
    if shutil.which("ffmpeg") is None:
        blockers.append("ffmpeg is not installed or not on PATH.")
    if shutil.which("ffprobe") is None:
        blockers.append("ffprobe is not installed or not on PATH.")
    llm_ok, llm_detail = _check_llm_reachable()
    if not llm_ok:
        blockers.append(llm_detail or "LLM provider is unreachable.")
    if blockers:
        raise HTTPException(status_code=503, detail="; ".join(blockers))


@app.get("/api/readiness", response_model=ReadinessResponse, responses=_COMMON_ERROR_RESPONSES, tags=["ops"])
def get_readiness():
    blockers: List[str] = []
    warnings: List[str] = []

    ffmpeg_ok = shutil.which("ffmpeg") is not None
    if not ffmpeg_ok:
        blockers.append("ffmpeg is not installed or not on PATH.")

    ffprobe_ok = shutil.which("ffprobe") is not None
    if not ffprobe_ok:
        blockers.append("ffprobe is not installed or not on PATH.")

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

    beds_ok = music_beds_present()
    bed_moods = music_bed_moods()
    broll_ok = any_broll_files()
    library = media_library_snapshot()
    music_missing = list(library.get("music", {}).get("missing") or [])
    broll_tags = list(library.get("broll", {}).get("present") or [])
    broll_missing = list(library.get("broll", {}).get("missing") or [])
    if not beds_ok:
        warnings.append(
            "No royalty-free music beds under backend/assets/music/. Run scripts/fetch_operator_media.sh (synth fallback sounds weak)."
        )
    elif music_missing:
        warnings.append(
            f"Music beds incomplete — missing moods: {', '.join(music_missing)}. See GET /api/media-library."
        )
    if not broll_ok:
        warnings.append(
            "No B-roll clips under backend/assets/broll/. Run scripts/fetch_operator_media.sh for long-form pads."
        )
    elif broll_missing:
        warnings.append(
            f"B-roll pack incomplete — missing: {', '.join(broll_missing)}. See GET /api/media-library."
        )

    return ReadinessResponse(
        ready=len(blockers) == 0,
        blockers=blockers,
        warnings=warnings,
        checks=ReadinessChecks(
            ffmpeg=ffmpeg_ok,
            ffprobe=ffprobe_ok,
            llm=llm_ok,
            llm_provider=cfg.provider,
            llm_model=cfg.model,
            tts_best=best_tts,
            tts_quality=quality_tts,
            tts_providers={
                key: bool(info.get("available"))
                for key, info in providers.items()
            },
            music_beds=beds_ok,
            music_bed_moods=bed_moods,
            music_beds_missing=music_missing,
            broll_pack=broll_ok,
            broll_tags=broll_tags,
            broll_missing=broll_missing,
        ),
        default_video_preset=resolve_video_preset(None),
    )


@app.get(
    "/api/media-library",
    response_model=MediaLibraryResponse,
    responses=_COMMON_ERROR_RESPONSES,
    tags=["ops"],
)
def get_media_library(q: str = ""):
    """List/tag/search operator music beds and B-roll clips (findability)."""
    return media_library_snapshot(query=q or None)


@app.get("/api/providers", response_model=ProvidersResponse, responses=_COMMON_ERROR_RESPONSES, tags=["config"])
def get_providers():
    cfg = llm_config.get_config()
    return {
        "providers": llm_config.PROVIDER_PRESETS,
        "current": {
            "provider": cfg.provider,
            "base_url": cfg.base_url,
            "model": cfg.model,
            "has_api_key": bool(cfg.api_key),
        },
    }


@app.post("/api/config", response_model=ConfigResponse, responses=_COMMON_ERROR_RESPONSES, tags=["config"])
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


@app.get("/api/llm/test", response_model=LLMTestResponse, responses=_COMMON_ERROR_RESPONSES, tags=["config"])
def test_llm():
    cfg = llm_config.get_config()
    ok, detail, sample = test_chat_completion(timeout=15.0)
    return {
        "ok": ok,
        "provider": cfg.provider,
        "model": cfg.model,
        "base_url": cfg.base_url,
        "detail": detail or None,
        "sample": sample,
    }


@app.get("/api/llm/models", response_model=LLMModelsResponse, responses=_COMMON_ERROR_RESPONSES, tags=["config"])
def list_llm_models():
    cfg = llm_config.get_config()
    models = list_ollama_models(cfg.base_url if cfg.provider == "ollama" else "http://localhost:11434")
    source = "ollama" if models else "openai_compatible"
    if not models:
        models = list_openai_compatible_models()
    return {
        "provider": cfg.provider,
        "model": cfg.model,
        "source": source,
        "models": models,
        "count": len(models),
    }


@app.get("/api/hooks", response_model=HooksResponse, responses=_COMMON_ERROR_RESPONSES, tags=["catalog"])
def get_hooks():
    return {
        "hooks": HOOK_TYPES,
        "descriptions": HOOK_DESCRIPTIONS,
    }


@app.get("/api/content-styles", response_model=ContentStylesResponse, responses=_COMMON_ERROR_RESPONSES, tags=["catalog"])
def get_content_styles():
    return {
        "styles": CONTENT_STYLES,
        "default": DEFAULT_CONTENT_STYLE,
    }


# ── TTS Providers ────────────────────────────────────────────────────
@app.get("/api/tts-providers", response_model=TTSProvidersResponse, responses=_COMMON_ERROR_RESPONSES, tags=["catalog"])
def tts_providers():
    """Return available TTS providers and their status."""
    providers = get_tts_providers()
    best = get_best_tts()
    return {"providers": providers, "best": best}


# ── Amazon Product Scraper ────────────────────────────────────────────
@app.post("/api/scrape-amazon")
async def scrape_amazon(url: str = Form(...)):
    """Scrape an Amazon product URL to auto-fill product fields."""
    req = ScrapeAmazonRequest(url=url)
    result = await scrape_amazon_product(req.url)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    if not str(result.get("product_name", "")).strip():
        raise HTTPException(
            status_code=422,
            detail="Could not extract product name from Amazon page",
        )
    # Map scraped data to ShadowCast product fields
    mapped = {
        "product_name": result.get("product_name", ""),
        "price": result.get("price", ""),
        "key_features": ", ".join(result.get("key_features", [])),
        "star_rating": result.get("star_rating", ""),
        "number_of_reviews": result.get("number_of_reviews", ""),
        "common_praises": (
            (result.get("common_praise_themes") or "").strip()
            or (
                "\n".join(
                    [f"- {r['title']}: {r['text']}" for r in result.get("positive_reviews", [])]
                )
                if result.get("positive_reviews")
                else ""
            )
        ),
        "common_complaints": (
            (result.get("common_complaint_themes") or "").strip()
            or (
                "\n".join(
                    [f"- {r['title']}: {r['text']}" for r in result.get("negative_reviews", [])]
                )
                if result.get("negative_reviews")
                else ""
            )
        ),
    }
    return {"status": "ok", "data": mapped, "raw": result}


# ── YouTube Keyword Research ─────────────────────────────────────────
@app.post("/api/youtube-research")
async def youtube_research(query: str = Form(...)):
    """Research YouTube keywords and get suggestions for a product/niche."""
    req = YouTubeResearchRequest(query=query)
    result = await research_youtube_keywords(req.query)
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
@app.post("/api/generate", response_model=GenerateResponse, responses=_COMMON_ERROR_RESPONSES, tags=["jobs"])
def start_generation(req: GenerateRequest):
    _ensure_generation_ready()
    job_id = str(uuid.uuid4())[:8]
    job_dir = OUTPUT_BASE / job_id
    job_dir.mkdir(exist_ok=True)

    product = req.product_info.dict()
    req_style = normalize_content_style(req.content_style)
    prepared, completeness_warnings = _prepare_products_for_generate(
        [product],
        default_style=req_style,
    )
    product = prepared[0]

    warnings = list(completeness_warnings)
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
        "use_tts": _resolve_use_tts(req.use_tts),
        "tts_provider": req.tts_provider,
        "tts_voice": req.tts_voice,
        "video_preset": resolve_video_preset(req.video_preset),
        "results": {}, "errors": [], "warnings": warnings,
        "phase_timings": [],
        "created_at": time.time(),
    }
    _save_job(job_id)

    if not _start_job_thread(job_id, _run_generation):
        raise HTTPException(status_code=409, detail="Job thread already active")
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
    audio_enabled: bool = Form(True),
    audio_mood: str = Form("auto"),
    use_tts: bool = Form(True),
    tts_provider: str = Form("auto"),
    tts_voice: str = Form(""),
    video_preset: str = Form("medium"),
):
    _ensure_generation_ready()
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
    style = normalize_content_style(content_style)
    products, completeness_warnings = _prepare_products_for_generate(products, default_style=style)

    job_id = str(uuid.uuid4())[:8]
    job_dir = OUTPUT_BASE / job_id
    job_dir.mkdir(exist_ok=True)

    jobs[job_id] = {
        "id": job_id, "mode": "batch",
        "status": "running", "progress": 0,
        "current_step": f"Starting batch: {len(products)} products...",
        "products": products, "hook_types": hook_list,
        "formats": fmt_list, "content_style": style,
        "audio_enabled": audio_enabled,
        "audio_mood": audio_mood,
        "use_tts": _resolve_use_tts(use_tts),
        "tts_provider": tts_provider,
        "tts_voice": tts_voice or None,
        "video_preset": resolve_video_preset(video_preset),
        "product_results": [],
        "errors": [], "warnings": completeness_warnings, "created_at": time.time(),
        "phase_timings": [],
    }
    _save_job(job_id)

    if not _start_job_thread(job_id, _run_batch_generation):
        raise HTTPException(status_code=409, detail="Job thread already active")

    return {
        "job_id": job_id, "status": "running", "mode": "batch",
        "product_count": len(products),
        "products_found": [p["product_name"] for p in products],
        "warnings": completeness_warnings,
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
    _ensure_generation_ready()
    style = normalize_content_style(req.content_style)
    raw_products = [p.dict() for p in req.products]
    products, completeness_warnings = _prepare_products_for_generate(
        raw_products,
        default_style=style,
    )

    job_id = str(uuid.uuid4())[:8]
    job_dir = OUTPUT_BASE / job_id
    job_dir.mkdir(exist_ok=True)

    jobs[job_id] = {
        "id": job_id, "mode": "batch",
        "status": "running", "progress": 0,
        "current_step": f"Starting batch: {len(products)} products...",
        "products": products, "hook_types": req.hook_types,
        "formats": req.formats, "content_style": style,
        "audio_enabled": req.audio_enabled,
        "audio_mood": req.audio_mood,
        "use_tts": _resolve_use_tts(req.use_tts),
        "tts_provider": req.tts_provider,
        "tts_voice": req.tts_voice,
        "video_preset": resolve_video_preset(req.video_preset),
        "product_results": [],
        "errors": [], "warnings": completeness_warnings, "created_at": time.time(),
        "phase_timings": [],
    }
    _save_job(job_id)

    if not _start_job_thread(job_id, _run_batch_generation):
        raise HTTPException(status_code=409, detail="Job thread already active")

    return {
        "job_id": job_id, "status": "running", "mode": "batch",
        "product_count": len(products),
        "products_found": [p["product_name"] for p in products],
        "warnings": completeness_warnings,
    }


# ── Status & Results ──────────────────────────────────────────────────
@app.get("/api/status/{job_id}", response_model=JobStatusResponse, responses=_COMMON_ERROR_RESPONSES, tags=["jobs"])
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
        "warnings": job.get("warnings", []),
        "script_errors": script_errors,
        "video_warnings": video_warnings,
        "other_errors": other_errors,
        "summary": _summarize_job_output(job),
        "audit": job.get("audit"),
    }
    if job.get("mode") == "batch":
        resp["product_count"] = len(job.get("products", []))
    return resp


@app.get("/api/results/{job_id}", response_model=JobResultsResponse, responses=_COMMON_ERROR_RESPONSES, tags=["jobs"])
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
        "warnings": job.get("warnings", []),
        "script_errors": script_errors,
        "video_warnings": video_warnings,
        "other_errors": other_errors,
        "summary": _summarize_job_output(job),
        "audit": job.get("audit"),
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


@app.post("/api/retry-missing/{job_id}", response_model=RetryMissingResponse, responses=_COMMON_ERROR_RESPONSES, tags=["jobs"])
def retry_missing_outputs(job_id: str):
    job = _load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") == "running":
        if job_id in _active_job_threads and not _job_thread_is_stale(job_id):
            raise HTTPException(
                status_code=409,
                detail="Job is already running with an active worker thread",
            )
        _active_job_threads.discard(job_id)

    summary = _summarize_job_output(job)
    if job.get("status") in ("complete", "partial") and not summary.get("is_partial"):
        return {
            "job_id": job_id,
            "status": "complete",
            "message": "All expected outputs are already present.",
            "summary": summary,
        }

    job["status"] = "running"
    job["cancel_requested"] = False
    job["current_step"] = "Resuming missing outputs..."
    job["progress"] = max(int(job.get("progress") or 0), 0)
    _save_job(job_id)

    if job.get("mode") == "batch":
        started = _start_job_thread(job_id, _run_batch_generation)
    else:
        started = _start_job_thread(job_id, _run_generation)

    if not started:
        raise HTTPException(
            status_code=409,
            detail="Could not start retry worker — job thread already active",
        )

    return {
        "job_id": job_id,
        "status": "running",
        "message": "Retry started. Existing artifacts will be skipped.",
        "summary": summary,
    }


@app.post("/api/cancel/{job_id}", tags=["jobs"], responses=_COMMON_ERROR_RESPONSES)
def cancel_job(job_id: str):
    job = _load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    status = str(job.get("status") or "")
    active = job_id in _active_job_threads and not _job_thread_is_stale(job_id)
    if status in ("complete", "cancelled", "error") and not active:
        return {
            "job_id": job_id,
            "status": status,
            "message": "Job is not running",
        }

    job["cancel_requested"] = True
    job["current_step"] = "Cancel requested — stopping at next checkpoint..."
    _save_job(job_id)
    return {
        "job_id": job_id,
        "status": "cancelling",
        "message": "Cancel requested. Worker stops at the next checkpoint.",
    }


@app.get("/api/audit/{job_id}", response_model=JobAuditResponse, responses=_COMMON_ERROR_RESPONSES, tags=["jobs"])
def get_job_audit(job_id: str, refresh: bool = False):
    job = _load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job_dir = OUTPUT_BASE / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="Job output directory not found")

    if refresh or not job.get("audit"):
        audit_result = _run_job_audit(job_dir)
        job["audit"] = audit_result
        _save_job(job_id)
    else:
        audit_result = job["audit"]

    return {
        "job_id": job_id,
        "status": job.get("status"),
        "audit": audit_result,
        "summary": _summarize_job_output(job),
    }


@app.get("/api/download/{job_id}/{path:path}")
def download_file(job_id: str, path: str):
    file_path = _safe_job_file(job_id, path)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    media_type = "video/mp4" if path.endswith(".mp4") else "application/json"
    if path.endswith(".txt"):
        media_type = "text/plain"
    if path.endswith(".zip"):
        media_type = "application/zip"
    return FileResponse(str(file_path), filename=file_path.name, media_type=media_type)


@app.get("/api/files/{job_id}")
def list_files(job_id: str):
    if (
        not job_id
        or job_id in _PROTECTED_OUTPUT_NAMES
        or job_id in {".", ".."}
        or "/" in job_id
        or "\\" in job_id
        or ".." in job_id
    ):
        raise HTTPException(status_code=404, detail="Job not found")
    output_root = OUTPUT_BASE.resolve()
    job_dir = (OUTPUT_BASE / job_id).resolve()
    if not job_dir.is_relative_to(output_root) or job_dir == output_root or not job_dir.is_dir():
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


@app.get("/api/jobs/postable")
def list_postable_jobs():
    entries: list[dict] = []
    if not OUTPUT_BASE.exists():
        return {"jobs": []}

    job_dirs = sorted(
        (p for p in OUTPUT_BASE.iterdir() if p.is_dir() and (p / "job.json").exists()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for job_dir in job_dirs:
        entry = _postable_job_entry(job_dir.name, job_dir)
        if entry:
            entries.append(entry)
    return {"jobs": entries}


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
    if not path or path.startswith("/") or "\\" in path:
        raise HTTPException(status_code=400, detail="Invalid path")
    parts = Path(path).parts
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="Path must be job_id/relative/file")
    job_id, rel = parts[0], str(Path(*parts[1:]))
    try:
        candidate = _safe_job_file(job_id, rel)
    except HTTPException as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=400, detail="Invalid path") from exc
        raise
    if candidate.is_file():
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
class PublishQualityRequest(BaseModel):
    job_id: Optional[str] = None
    video_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    hook_type: Optional[str] = None
    video_format: str = "short_form"
    product_slug: Optional[str] = None
    thumbnail_variant: str = "variant_a"


@app.post("/api/publish/quality")
def publish_quality_check(req: PublishQualityRequest):
    try:
        video_path = req.video_path
        thumb_path = req.thumbnail_path
        image_url = None
        if req.job_id and req.hook_type:
            resolved = resolve_job_assets(
                req.job_id,
                req.hook_type,
                req.video_format,
                product_slug=req.product_slug,
                jobs=jobs,
            )
            video_path = video_path or resolved.get("video_path")
            thumb_path = thumb_path or resolved.get("thumbnail_path")
            if req.thumbnail_variant in ("variant_b", "variant_c") and thumb_path:
                thumb_path = re.sub(r"variant_[abc]", req.thumbnail_variant, str(thumb_path))
            image_url = resolved.get("image_url")
            if not image_url and req.job_id in jobs:
                job = jobs[req.job_id]
                product = job.get("product_info") or {}
                if req.product_slug and job.get("mode") == "batch":
                    for pr in job.get("product_results") or []:
                        if job_slugify(pr.get("product_name", "")) == req.product_slug:
                            product = pr.get("product_info") or product
                            break
                image_url = (product.get("image_url") or "").strip() or None
        if not video_path:
            raise HTTPException(status_code=400, detail="video_path or job_id+hook_type required")
        return evaluate_publish_quality(
            video_path=video_path,
            thumbnail_path=thumb_path,
            video_format=req.video_format,
            image_url=image_url,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    thumbnail_variant: str = "variant_a"


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
            thumbnail_variant=req.thumbnail_variant,
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
            if not normalized.get("productName") and not normalized.get("product_name"):
                continue
            snake = as_snake_product_info(normalized)
            assessment = assess_product_completeness(snake)
            products.append({
                "normalized": normalized,
                "product_info": snake,
                "completeness": assessment,
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
            "productName": products[0]["normalized"].get("productName")
            or products[0]["normalized"].get("product_name"),
            "product_names": [
                p["normalized"].get("productName") or p["normalized"].get("product_name")
                for p in products
            ],
            "recommended_content_style": products[0]["recommended_content_style"],
            "normalized": products[0]["normalized"],
            "product_info": products[0].get("product_info"),
            "completeness_warnings": [
                {
                    "product_name": p.get("completeness", {}).get("product_name"),
                    "warnings": p.get("completeness", {}).get("warnings", []),
                    "blocking": p.get("completeness", {}).get("blocking", []),
                }
                for p in products
                if p.get("completeness", {}).get("warnings") or p.get("completeness", {}).get("blocking")
            ],
            "open_url": f"{base}/?apf_draft={token}",
        }

    single = product_payloads[0] if product_payloads else payload
    import_result = normalize_apf_payload(single if isinstance(single, dict) else payload)
    normalized = import_result["normalized"]
    recommended_content_style = import_result["recommended_content_style"]

    if not normalized.get("productName") and not normalized.get("product_name"):
        raise _UnlovedHTTPException(status_code=400, detail="APF payload did not include a product name.")

    snake = as_snake_product_info(normalized)
    assessment = assess_product_completeness(snake)

    doc = {
        "ok": True,
        "token": token,
        "created_at": _unloved_datetime.now(_unloved_timezone.utc).isoformat(),
        "payload": payload,
        "normalized": normalized,
        "product_info": snake,
        "completeness": assessment,
        "recommended_content_style": recommended_content_style,
    }

    path = _UNLOVED_APF_IMPORT_DIR / f"{token}.json"
    path.write_text(_unloved_json.dumps(doc, ensure_ascii=False, indent=2))

    base = _unloved_os.getenv("SHADOWCAST_PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
    return {
        "ok": True,
        "token": token,
        "productName": normalized.get("productName") or normalized.get("product_name"),
        "recommended_content_style": recommended_content_style,
        "normalized": normalized,
        "product_info": snake,
        "completeness": assessment,
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

def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    app.openapi_schema = customize_openapi(schema)
    return app.openapi_schema


app.openapi = _custom_openapi

# ── Serve Frontend ────────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
_SENTRY_LOADER_PLACEHOLDER = "__SENTRY_LOADER_KEY__"
_SENTRY_LOADER_TAG = (
    f'    <script src="https://js.sentry-cdn.com/{_SENTRY_LOADER_PLACEHOLDER}.min.js" '
    'crossorigin="anonymous" data-lazy="no"></script>\n'
)


def _serve_index_html() -> HTMLResponse:
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    loader_key = _sentry_frontend_loader_key()
    if loader_key:
        html = html.replace(_SENTRY_LOADER_PLACEHOLDER, loader_key)
    else:
        html = html.replace(_SENTRY_LOADER_TAG, "")
    return HTMLResponse(html)


if (FRONTEND_DIR / "index.html").exists():
    assets_dir = FRONTEND_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="static_assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        file_path = FRONTEND_DIR / full_path
        if file_path.exists() and file_path.is_file():
            if file_path.name == "index.html":
                return _serve_index_html()
            return FileResponse(str(file_path))
        return _serve_index_html()
else:
    @app.get("/")
    def root():
        return {"message": "ShadowCast API v4.0 — by Unloved Productions | Forged in Passion"}


if __name__ == "__main__":
    import uvicorn
    # Localhost-only trust model: default bind is loopback. Override with HOST=0.0.0.0 only if intentional.
    _host = os.getenv("HOST", "127.0.0.1")
    _port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host=_host, port=_port)

