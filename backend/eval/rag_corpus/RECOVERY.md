# ShadowCast Recovery Guide

## 1) Purpose
ShadowCast generates faceless affiliate videos from structured product inputs and LLM-generated scripts.

## 2) Source Of Truth
- Repository: `https://github.com/unlovedproductions/shadowcast-.git`
- Default branch: `main`
- Local root: `/home/unloved/shadowcast-`

## 3) Dependencies
- Python 3.10+
- Virtual environment at `venv/`
- FFmpeg
- FastAPI runtime (`backend/app.py`)
- Optional: Ollama/OpenAI/custom providers depending on local settings

## 4) Secrets Inventory (names only)
- `INTERNAL_SERVICE_SECRET`
- LLM provider variables configured through backend env/UI settings

## 5) Data To Back Up
- Generated assets under `output/` (if present)
- Any local runtime data used for jobs/assets
- Optional local config files used for provider configuration

## 6) Recovery A: New Machine
1. Clone:
   - `git clone https://github.com/unlovedproductions/shadowcast-.git`
2. Create and activate venv:
   - `python3 -m venv venv`
   - `source venv/bin/activate`
3. Install dependencies:
   - `pip install -r backend/requirements.txt`
4. Ensure FFmpeg is installed.
5. Restore backend env values.
6. Start app:
   - `python3 backend/app.py`
7. Verify health endpoint.

## 7) Recovery B: Corrupted Working Tree
1. Inspect local changes:
   - `git status`
2. Save if needed:
   - `git stash push -u`
3. Hard reset to remote:
   - `git fetch origin`
   - `git checkout main`
   - `git reset --hard origin/main`
4. Reinstall Python deps in venv.

## 8) Recovery C: Data Loss
ShadowCast is mostly stateless code + generated artifacts. If generated output is lost, regenerate from source inputs in APF/Mission Control.

## 9) Verification Checklist
- `python3 -c "import fastapi, moviepy, PIL"`
- `curl -fsS http://localhost:8000/api/health >/dev/null`

## 10) Stack Dependencies
- APF and Mission Control expect shared `INTERNAL_SERVICE_SECRET`.
- Mission Control orchestrates ShadowCast job execution over API.

## 11) Last Verified
- Date: 2026-07-09
- Commit: `53c7ae1`
