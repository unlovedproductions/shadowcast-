"""Shared public-route allowlist for HTTP middleware and OpenAPI security.

Browser UI and local tooling call these without X-Service-Key.
Non-public non-GET routes require INTERNAL_SERVICE_SECRET when set
(primarily POST /api/config and any future admin-only endpoints).
"""

from __future__ import annotations

PUBLIC_PATHS = {
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
    "/api/import-apf/direct",
    "/api/batch-generate",
    "/api/scrape-amazon",
    "/api/youtube-research",
    "/api/readiness",
    "/api/media-library",
    "/api/openapi.json",
}

PUBLIC_PREFIXES = (
    "/api/status/",
    "/api/results/",
    "/api/retry-missing/",
    "/api/cancel/",
    "/api/audit/",
    "/api/download/",
    "/api/files/",
    "/api/bg-",
    "/api/analytics",
    "/api/social",
    "/api/oauth",
    "/api/publish",
    "/api/media",
    "/api/tracking-link",
    "/api/jobs/",
    "/api/import-apf/direct/",
)


def is_public_path(path: str) -> bool:
    if path in PUBLIC_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES)
