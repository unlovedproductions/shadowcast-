# ShadowCast Architecture

## Intent
ShadowCast converts structured affiliate product data into short-form and long-form video assets.

## Runtime Components
- FastAPI backend in `backend/app.py`
- Script generation modules (including trust-first styles and hook logic)
- Rendering pipeline (`video_renderer`, overlays, effects)
- Frontend UI (`frontend/index.html`)

## Key Dependencies
- `fastapi`, `uvicorn` for API/server
- `moviepy`, `Pillow`, `numpy`, `scipy` for media processing
- optional provider clients (`openai`, local provider integrations)

## Integration Points
- APF direct-import payloads for product metadata
- Mission Control orchestration calls for job lifecycle
- Shared `INTERNAL_SERVICE_SECRET` for machine-to-machine requests

## Data Flow (high level)
1. Input payload received from UI/API.
2. Script generated based on selected content style/hooks.
3. Video rendered with overlays, timing, and assets.
4. Output package emitted for publishing workflow.
