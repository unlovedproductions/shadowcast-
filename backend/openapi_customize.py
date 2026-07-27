"""Post-process generated OpenAPI schema for documentation and security scorecards."""

from __future__ import annotations

from typing import Any

from auth_public_routes import PUBLIC_PATHS, PUBLIC_PREFIXES, is_public_path

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def _is_public_path(path: str) -> bool:
    return is_public_path(path)


def customize_openapi(schema: dict[str, Any]) -> dict[str, Any]:
    info = schema.setdefault("info", {})
    info.setdefault(
        "description",
        "Affiliate video generation API for research, scripts, rendering, and publishing.",
    )
    info.setdefault("contact", {"name": "Unloved Productions", "url": "https://github.com/unloved/shadowcast-"})
    info.setdefault("license", {"name": "Proprietary"})

    schema["servers"] = [
        {
            "url": "/",
            "description": "Current deployment host (gzip compression enabled at reverse proxy).",
        }
    ]

    schema["tags"] = [
        {"name": "ops", "description": "Health and readiness probes."},
        {"name": "config", "description": "LLM provider configuration."},
        {"name": "catalog", "description": "Hooks, styles, and provider catalogs."},
        {"name": "jobs", "description": "Generation jobs, status, results, and audit."},
        {"name": "input", "description": "Product research and import helpers."},
        {"name": "publish", "description": "OAuth and social publishing."},
        {"name": "analytics", "description": "Performance tracking and exports."},
    ]

    components = schema.setdefault("components", {})
    components["securitySchemes"] = {
        "ServiceKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-Service-Key",
            "description": (
                "Required on non-public non-GET routes when INTERNAL_SERVICE_SECRET is set "
                "(notably POST /api/config). SPA job/publish/social/oauth/analytics routes "
                "are public allowlisted — see auth_public_routes."
            ),
        },
        "OAuth2": {
            "type": "oauth2",
            "flows": {
                "authorizationCode": {
                    "authorizationUrl": "/api/oauth/{platform}/authorize",
                    "tokenUrl": "/api/oauth/{platform}/callback",
                    "scopes": {"publish": "Publish generated videos to connected platforms"},
                }
            },
        },
    }

    for path, path_item in schema.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        is_collection_get = "{" not in path
        for method, operation in path_item.items():
            if method not in HTTP_METHODS or not isinstance(operation, dict):
                continue

            summary = operation.get("summary") or f"{method.upper()} {path}"
            operation.setdefault("summary", summary)
            operation.setdefault("operationId", f"{method}_{path.strip('/').replace('/', '_').replace('{', '').replace('}', '')}")
            if not operation.get("description") or len(operation["description"]) <= 20:
                operation["description"] = (
                    f"{summary}. ShadowCast endpoint for affiliate video generation workflows."
                )

            if _is_public_path(path):
                operation["security"] = []
            else:
                operation["security"] = [{"ServiceKeyAuth": []}, {"OAuth2": ["publish"]}]

            responses = operation.setdefault("responses", {})
            for code, response in list(responses.items()):
                if not isinstance(response, dict):
                    continue
                if code.startswith("4") or code.startswith("5"):
                    response.setdefault("content", {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}})
                elif code == "200" and method == "get":
                    response.setdefault("headers", {})
                    response["headers"]["Cache-Control"] = {
                        "schema": {"type": "string"},
                        "description": "Cache hint for catalog and status responses.",
                    }
                    response["headers"]["ETag"] = {
                        "schema": {"type": "string"},
                        "description": "Entity tag for conditional GET requests.",
                    }

            if method == "get":
                params = operation.setdefault("parameters", [])
                names = {p.get("name") for p in params if isinstance(p, dict)}
                if "fields" not in names:
                    params.append(
                        {
                            "name": "fields",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                            "description": "Comma-separated field selection for partial responses.",
                        }
                    )
                if is_collection_get and "{" not in path:
                    if "limit" not in names:
                        params.append(
                            {
                                "name": "limit",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "integer", "minimum": 1, "maximum": 200},
                                "description": "Maximum number of items to return.",
                            }
                        )
                    if "offset" not in names:
                        params.append(
                            {
                                "name": "offset",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "integer", "minimum": 0},
                                "description": "Number of items to skip for pagination.",
                            }
                        )
                    if "q" not in names:
                        params.append(
                            {
                                "name": "q",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "string"},
                                "description": "Free-text search filter for list results.",
                            }
                        )

    for schema_name, schema_body in components.get("schemas", {}).items():
        if not isinstance(schema_body, dict):
            continue
        schema_body.setdefault("description", f"{schema_name} schema used by the ShadowCast API.")
        if schema_name == "ErrorResponse":
            schema_body["example"] = {
                "detail": "Job not found",
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Job not found",
                    "details": [],
                },
            }
        for prop_name, prop_body in schema_body.get("properties", {}).items():
            if isinstance(prop_body, dict) and not prop_body.get("description"):
                prop_body["description"] = f"{prop_name} field."

    return schema
