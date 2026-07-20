# Changelog

All notable changes to ShadowCast are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [4.1.0] - 2026-07-20

### Added

- Typed API response models for health, readiness, job lifecycle, and config routes.
- Standardized error payload shape (`detail` + nested `error` object) with backward-compatible `detail`.
- OpenAPI customization layer for security schemes, pagination parameters, and documentation.
- HTTP integration tests (`tests/test_api_routes.py`) for ops, config, catalog, input, and job routes.
- Quality gate scripts vendored under `scripts/quality/` (API linter, scorecard, breaking-change detector, ship-gate, changelog tools, RAG architect tools).
- GitHub Actions workflow `.github/workflows/quality-gates.yml`.
- Pre-commit hooks for OpenAPI freshness and API linting.
- RAG design document and evaluation fixtures for future retrieval-augmented generation.
- `backend/eval/artifacts/` baseline audit outputs for API lint, scorecard, and ship-gate.

### Changed

- CORS origins now configurable via `CORS_ORIGINS` (defaults to localhost); set `CORS_ALLOW_ALL=1` only for local dev.
- Credential encryption key derivation uses scrypt instead of raw SHA-256.
- OpenAPI export includes app description, servers, contact, and response schemas for core routes.

### Security

- Documented `X-Service-Key` and OAuth2 security schemes in OpenAPI for protected admin/publish routes.

[Unreleased]: https://github.com/unloved/shadowcast-/compare/v4.1.0...HEAD
[4.1.0]: https://github.com/unloved/shadowcast-/releases/tag/v4.1.0
