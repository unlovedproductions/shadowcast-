# Changelog

All notable changes to ShadowCast are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Root `README.md` and `docs/SOCIAL_READINESS.md` (dual-bar posting readiness).
- Product still support via `image_url` (`product_media.py`) for hero segments and thumbnails.
- Drop-in music beds under `backend/assets/music/` with synth fallback.
- Publish soft-gate against gTTS-only live uploads (`ALLOW_GTTS_PUBLISH` escape hatch).
- Long-form/short-form `.srt` sidecars from TTS timing (`caption_srt.py`).
- Native Instagram Reels / TikTok `post_info` fields in `posting_package_adapter.py`.
- Pre-publish QA: `POST /api/publish/quality` + frontend **Pre-Publish QA** button.
- Optional WhisperX forced-align behind `SHADOWCAST_WHISPERX_ALIGN=1` (`whisperx_align.py`).
- Optional long-form B-roll pads (`broll.py`, `backend/assets/broll/`).
- Publish UI A/B/C thumbnail pick (`thumbnail_variant` on batch publish).
- Hardened Rumble Playwright selectors + dry-run vs live notes in RUNBOOK.
- Playwright E2E tiers (mocked + live) and quality-gate scripts under `scripts/quality/`.
- Style-rules RAG runtime + corpus under `backend/eval/rag_corpus/`.
- TTS-first audio-driven timing, Shorts burn-in captions, entity lower-thirds, two-pass loudnorm.
- `job_store` extraction and optional `SHADOWCAST_BATCH_WORKERS`.

### Changed

- Docs synced to current architecture (ARCHITECTURE, RUNBOOK, RECOVERY, RAG_DESIGN, style matrix).
- API/UI prefer quality TTS when available (`SHADOWCAST_TTS_DEFAULT` to force off).
- Canonical venv documented as `.venv`.

### Security

- Localhost-default bind (`HOST`/`PORT`); documented CORS and service-key schemes (see 4.1.0).

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

[Unreleased]: https://github.com/unlovedproductions/shadowcast-/compare/main...HEAD
[4.1.0]: https://github.com/unlovedproductions/shadowcast-/releases/tag/v4.1.0
