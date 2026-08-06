# ShadowCast

Faceless kinetic affiliate video generator by Unloved Productions.

ShadowCast turns structured product data (CSV, APF import, or Amazon URL enrichment) into trust-first review videos — honest reviews, elimination rounds, VS battles, budget challenges — then packages YouTube SEO assets, thumbnails, and multi-platform publish payloads.

## What it produces

| Format | Resolution | Aspect |
|--------|------------|--------|
| `short_form` | 1080×1920 | 9:16 Shorts / Reels / TikTok |
| `long_form` | 1920×1080 | 16:9 YouTube |

Pipeline: **product → LLM scripts → TTS (optional/recommended) → MoviePy kinetic text + overlays → ffmpeg mux (ducking + loudnorm) → YouTube package + thumbnails → publish**.

## Honest boundaries

- Motion-graphics / kinetic typography product — not UGC filming or diffusion gen-video.
- Product stills are supported when `image_url` is provided **or auto-extracted from APF vendor sales/offer pages** (og:image / product `<img>`); otherwise procedural backgrounds.
- Optional long-form B-roll pads when clips exist under `backend/assets/broll/` (see ATTRIBUTION).
- Ship-quality voice needs Kokoro, Piper, or OpenAI TTS (gTTS is smoke-only).
- Postable checklist: Pre-Publish QA, `.srt` sidecars, thumb A/B/C pick, dry-run before live.
- See [docs/SOCIAL_READINESS.md](docs/SOCIAL_READINESS.md) for dual-bar readiness scores (~88% / ~72% after P0–P2).

## Quickstart

```bash
cd shadowcast-
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
# system: ffmpeg + ffprobe on PATH
python3 backend/app.py
# open http://127.0.0.1:8000
```

Override bind with `HOST` / `PORT` (defaults `127.0.0.1:8000`).

## Docs

| Doc | Purpose |
|-----|---------|
| [SETUP_GUIDE.md](SETUP_GUIDE.md) | Full install (Linux/Windows), LLM, TTS |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | Daily ops, E2E, quality gates |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Modules and data flow |
| [docs/SOCIAL_READINESS.md](docs/SOCIAL_READINESS.md) | Posting-quality score + roadmap |
| [docs/RAG_DESIGN.md](docs/RAG_DESIGN.md) | Product + style-rules RAG |
| [docs/STYLE_RENDERING_CHECKLIST.md](docs/STYLE_RENDERING_CHECKLIST.md) | Style × format matrix |
| [docs/RECOVERY.md](docs/RECOVERY.md) | Disaster recovery |
| [CHANGELOG.md](CHANGELOG.md) | Release notes |
| [future-improvements/](future-improvements/) | Deferred staged-pipeline rewrite |

## Stack

FastAPI + MoviePy + Pillow + ffmpeg · optional Ollama/OpenAI LLM · Kokoro/Piper/OpenAI/gTTS · YouTube / Meta / TikTok / Rumble publishers.

## Repo

https://github.com/unlovedproductions/shadowcast-
