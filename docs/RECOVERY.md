# ShadowCast Recovery Guide

## 1) Purpose
ShadowCast generates faceless affiliate videos from structured product inputs and LLM-generated scripts.

## 2) Source Of Truth
- Repository: `https://github.com/unlovedproductions/shadowcast-.git`
- Default branch: `main`
- Local root: `/home/unloved/shadowcast-`

## 3) Dependencies
- Python 3.10+
- Virtual environment at `.venv/` (preferred; `venv/` acceptable as legacy alias)
- Install lock for CI parity: `backend/requirements.lock` (symlink `poetry.lock` at repo root)
- FFmpeg + ffprobe (optional `h264_nvenc` for faster encode)
- FastAPI runtime (`backend/app.py`)
- Optional: Ollama/OpenAI/custom providers depending on local settings
- Optional quality TTS: Kokoro (local ONNX in `backend/assets/kokoro/`), Piper, or OpenAI TTS

## 4) Secrets Inventory (names only)
- `INTERNAL_SERVICE_SECRET`
- LLM provider variables configured through backend env/UI settings
- Platform OAuth credentials for publish
- Optional: `SENTRY_DSN`, `SENTRY_FRONTEND_DSN`

## 5) Data To Back Up
- Generated assets under `backend/output/` (if present)
- Any local runtime data used for jobs/assets
- Optional local config files used for provider configuration
- Dropped music beds under `backend/assets/music/` (gitignored WAVs)
- Optional B-roll under `backend/assets/broll/`
- Optional Kokoro ONNX assets under `backend/assets/kokoro/`

## 6) Recovery A: New Machine
1. Clone:
   - `git clone https://github.com/unlovedproductions/shadowcast-.git`
2. Create and activate venv:
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
3. Install dependencies:
   - `pip install -r backend/requirements.txt`
4. Ensure FFmpeg is installed.
5. Restore backend env values (including optional Sentry DSNs).
6. Restore operator media:
   - `./scripts/fetch_operator_media.sh`
   - or copy backed-up `backend/assets/music/` (+ optional `broll/`, `kokoro/`)
7. Start app:
   - `python3 backend/app.py`
8. Verify health, readiness, and media library:
   - `curl -fsS http://127.0.0.1:8000/api/health`
   - `curl -fsS http://127.0.0.1:8000/api/readiness`
   - `curl -fsS http://127.0.0.1:8000/api/media-library`
9. Confirm music beds present before any live publish (or set `ALLOW_SYNTH_MUSIC_PUBLISH=1` only as escape hatch).

## 7) Recovery B: Corrupted Working Tree
1. Inspect local changes:
   - `git status`
2. Save if needed:
   - `git stash push -u`
3. Hard reset to remote:
   - `git fetch origin`
   - `git checkout main`
   - `git reset --hard origin/main`
4. Reinstall Python deps in `.venv`.
5. Re-fetch operator media if WAV/MP4 assets were wiped:
   - `./scripts/fetch_operator_media.sh`

## 8) Recovery C: Data Loss
ShadowCast is mostly stateless code + generated artifacts. If generated output is lost, regenerate from source inputs in APF/Mission Control. If music/B-roll binaries are lost, re-run `./scripts/fetch_operator_media.sh` (live publish will block without beds).

## 9) Verification Checklist
- `python3 -c "import fastapi, moviepy, PIL"`
- `curl -fsS http://127.0.0.1:8000/api/health >/dev/null`
- `curl -fsS http://127.0.0.1:8000/api/readiness`
- `curl -fsS http://127.0.0.1:8000/api/media-library`

## 10) Stack Dependencies
- APF and Mission Control expect shared `INTERNAL_SERVICE_SECRET`.
- Mission Control orchestrates ShadowCast job execution over API.

## 11) Last Verified
- Date: 2026-08-15
- Commit: `41ec621`
