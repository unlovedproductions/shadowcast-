# ShadowCast — Complete Setup Guide

## by Unloved Productions | Forged in Passion

**ShadowCast** is a faceless text-only affiliate video generator built with a **trust-first approach** — honest reviews, elimination rounds, comparison battles, and budget challenges that build credibility and convert better than generic hype content. No need to buy or test products; all content is research-based using public specs, reviews, and comparison data.

> *"Creating software for the problems you didn't know you had"* — Unloved Productions

---

## Operational docs

- `README.md` — product overview and quickstart
- `docs/RECOVERY.md` — disaster-recovery playbook
- `docs/RUNBOOK.md` — startup/shutdown and operator checks
- `docs/ARCHITECTURE.md` — system structure and integration points
- `docs/RAG_DESIGN.md` — product + style-rules RAG
- `docs/STYLE_RENDERING_CHECKLIST.md` / `docs/STYLE_MATRIX_RUNBOOK.md` — style × format verification
- `backend/eval/rag_corpus/RENDERER_CONTRACT.md` — LLM ↔ renderer contract
- `docs/SOCIAL_READINESS.md` — posting-quality readiness score

TTS-first timing (segment duration follows measured speech), Shorts burn-in captions, music ducking, and two-pass loudnorm (~−14 LUFS) are part of the assemble pipeline when TTS/audio are enabled.

### Operator media (required for live publish)

```bash
./scripts/fetch_operator_media.sh
```

Drops Mixkit beds into `backend/assets/music/{mood}.wav` and B-roll into `backend/assets/broll/`. Inventory: `GET /api/media-library`. Live publish blocks when music beds are missing unless `ALLOW_SYNTH_MUSIC_PUBLISH=1`. Details: `docs/RUNBOOK.md`, `backend/assets/music/ATTRIBUTION.md`.

### Quality TTS (Kokoro local ONNX)

```bash
pip install kokoro-onnx soundfile
# download kokoro-v1.0.onnx + voices-v1.0.bin into backend/assets/kokoro/
# https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0
```

Piper and OpenAI TTS also qualify. gTTS is smoke-only (`ALLOW_GTTS_PUBLISH=1` to force live).

### Optional env (ops)

| Variable | Purpose |
|----------|---------|
| `SENTRY_DSN` / `SENTRY_FRONTEND_DSN` / `SENTRY_ENVIRONMENT` | Error monitoring |
| `SHADOWCAST_FFMPEG_CODEC` | `auto` (NVENC when available), `libx264`, or `h264_nvenc` |
| `SHADOWCAST_VIDEO_PRESET` | Encode preset |
| `SHADOWCAST_TTS_PRONUNCIATIONS` / `SHADOWCAST_TTS_CROSSFADE` | VO lexicon + seam crossfade |
| `ALLOW_SYNTH_MUSIC_PUBLISH` | Escape hatch for live publish without music beds |
| `SHADOWCAST_REQUIRE_PRODUCT_IMAGE` | Fail pre-publish QA when `image_url` missing |

---

## Your Machine Specs (Razer Blade 15 Advanced)

> Personal reference for the primary Unloved Productions workstation — not a hard requirement for ShadowCast.

| Component | Spec | LLM Capability |
|-----------|------|----------------|
| **GPU** | NVIDIA RTX 3080 Laptop (16GB GDDR6 VRAM) | Runs 7B-14B models natively, 32B with offload |
| **RAM** | 32GB DDR4 3200MHz | Supports CPU offload for larger models |
| **CPU** | Intel i9-11900H (8C/16T, up to 4.9GHz) | Fast model loading and video rendering |
| **CUDA** | 8.6 (Ampere, 6144 CUDA cores) | Full cuBLAS acceleration for LLMs |
| **Storage** | 1TB NVMe PCIe 4.0 | Fast model loading from disk |

---

## Ubuntu Linux Setup (Full Walkthrough)

This section covers everything from a fresh Ubuntu install to running ShadowCast. Tested on Ubuntu 22.04 and 24.04.

### Step 1: System Update

Open a terminal and run:

```bash
sudo apt update && sudo apt upgrade -y
```

### Step 2: Install Python 3 and pip

Ubuntu 22.04+ comes with Python 3 pre-installed, but you need pip and venv:

```bash
sudo apt install -y python3 python3-pip python3-venv
```

Verify the installation:

```bash
python3 --version
pip3 --version
```

You should see Python 3.10+ and pip 22+.

### Step 3: Install FFmpeg

FFmpeg is required for video rendering. Install it from the Ubuntu repos:

```bash
sudo apt install -y ffmpeg
```

Verify:

```bash
ffmpeg -version
```

You should see version 4.4+ or higher.

### Step 4: Install NVIDIA Drivers and CUDA (For Local LLM Support)

**Skip this step if you only plan to use OpenAI API.** This is only needed for running local LLMs on your GPU.

Check if NVIDIA drivers are already installed:

```bash
nvidia-smi
```

If you see your RTX 3080 listed with driver version, skip to Step 5.

If not installed, add the NVIDIA PPA and install:

```bash
sudo add-apt-repository -y ppa:graphics-drivers/ppa
sudo apt update
sudo apt install -y nvidia-driver-535
```

Reboot after installing:

```bash
sudo reboot
```

After reboot, verify:

```bash
nvidia-smi
```

You should see your RTX 3080 with 16GB VRAM listed.

**Install CUDA Toolkit** (needed for GPU-accelerated LLM inference):

```bash
sudo apt install -y nvidia-cuda-toolkit
```

Verify:

```bash
nvcc --version
```

### Step 5: Clone the Repository

```bash
cd ~
git clone https://github.com/unlovedproductions/shadowcast-.git
cd shadowcast-
```

### Step 6: Create a Python Virtual Environment

Using a virtual environment keeps ShadowCast's dependencies isolated from your system Python:

```bash
python3 -m venv venv
source venv/bin/activate
```

Your terminal prompt should now show `(venv)` at the beginning. **You need to run `source venv/bin/activate` every time you open a new terminal to use ShadowCast.**

To make this easier, you can add an alias to your `.bashrc`:

```bash
echo 'alias shadowcast="cd ~/shadowcast- && source venv/bin/activate && python3 backend/app.py"' >> ~/.bashrc
source ~/.bashrc
```

Now you can just type `shadowcast` to launch the app.

### Step 7: Install Python Dependencies

With the virtual environment activated:

```bash
pip install -r backend/requirements.txt
```

This installs FastAPI, moviepy, Pillow, OpenAI client, gTTS, and all other dependencies. Takes about 1-2 minutes.

If you get any errors about missing system libraries:

```bash
sudo apt install -y build-essential libffi-dev libssl-dev libjpeg-dev zlib1g-dev
pip install -r backend/requirements.txt
```

### Step 8: Install Fonts

The video renderer uses Montserrat and Bebas Neue fonts. They're included in `backend/assets/`, but you can also install them system-wide for other apps:

```bash
sudo apt install -y fonts-noto fonts-noto-color-emoji
```

The bundled fonts in `backend/assets/` are used automatically — no extra configuration needed.

### Step 9: Configure Your LLM Provider

```bash
cd backend
cp .env.example .env
nano .env
```

Uncomment ONE provider section in the `.env` file (see the LLM Setup section below for details). Or skip this — you can configure everything through the web UI's Settings panel.

Press `Ctrl+X`, then `Y`, then `Enter` to save and exit nano.

### Step 10: Launch ShadowCast

```bash
cd ~/shadowcast-
source venv/bin/activate
python3 backend/app.py
```

Open your browser to: **http://localhost:8000**

You should see the ShadowCast interface with the dark pink and black theme.

**To run in the background** (so you can close the terminal):

```bash
nohup python3 backend/app.py > shadowcast.log 2>&1 &
echo $! > shadowcast.pid
```

To stop it later:

```bash
kill $(cat shadowcast.pid)
```

### Step 11: Create a Desktop Shortcut (Optional)

Create a `.desktop` file so you can launch ShadowCast from your app menu:

```bash
cat > ~/.local/share/applications/shadowcast.desktop << 'EOF'
[Desktop Entry]
Name=ShadowCast
Comment=Faceless Affiliate Video Generator by Unloved Productions
Exec=bash -c "cd ~/shadowcast- && source venv/bin/activate && python3 backend/app.py & sleep 2 && xdg-open http://localhost:8000"
Icon=video-display
Terminal=false
Type=Application
Categories=AudioVideo;Video;
EOF
```

### Step 12: Auto-Start on Boot (Optional)

Create a systemd service so ShadowCast starts automatically when you log in:

```bash
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/shadowcast.service << EOF
[Unit]
Description=ShadowCast Video Generator
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/shadowcast-
ExecStart=%h/shadowcast-/venv/bin/python3 %h/shadowcast-/backend/app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable shadowcast.service
systemctl --user start shadowcast.service
```

Check status:

```bash
systemctl --user status shadowcast.service
```

To stop:

```bash
systemctl --user stop shadowcast.service
```

---

## Windows Setup

### Step 1: Install Prerequisites

**Python 3.10+:**

Download from [python.org/downloads](https://python.org/downloads). **Check "Add Python to PATH"** during installation. This is critical.

Verify in Command Prompt or PowerShell:

```
python --version
```

**FFmpeg:**

```
winget install ffmpeg
```

Or download from [ffmpeg.org/download.html](https://ffmpeg.org/download.html), extract it, and add the `bin` folder to your system PATH.

Verify:

```
ffmpeg -version
```

### Step 2: Clone and Set Up

```
git clone https://github.com/unlovedproductions/shadowcast-.git
cd shadowcast-
python -m venv venv
venv\Scripts\activate
pip install -r backend\requirements.txt
```

### Step 3: Configure and Launch

```
copy backend\.env.example backend\.env
```

Edit `backend\.env` with Notepad to set your LLM provider, or configure through the web UI.

```
python backend\app.py
```

Open **http://localhost:8000** in your browser.

---

## macOS Setup

### Step 1: Install Prerequisites

**Homebrew** (if not installed):

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

**Python 3 and FFmpeg:**

```bash
brew install python ffmpeg
```

### Step 2: Clone and Set Up

```bash
git clone https://github.com/unlovedproductions/shadowcast-.git
cd shadowcast-
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

### Step 3: Configure and Launch

```bash
cp backend/.env.example backend/.env
nano backend/.env
```

Set your LLM provider, or configure through the web UI.

```bash
python3 backend/app.py
```

Open **http://localhost:8000** in your browser.

---

## LLM Setup — Choose Your Provider

### Option A: Ollama (FREE — Recommended for Your Machine)

Ollama is the easiest way to run LLMs locally. Zero cost, runs entirely on your Razer Blade 15.

**Install Ollama on Ubuntu:**

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

This installs Ollama and sets it up as a systemd service that starts automatically.

Verify it's running:

```bash
ollama --version
systemctl status ollama
```

**Install Ollama on Windows:**

Download from https://ollama.com/download and run the installer. Ollama runs as a background service automatically.

**Pull a Model — Recommendations for Your RTX 3080 (16GB VRAM):**

| Model | Pull Command | VRAM | Quality | Speed | Best For |
|-------|-------------|------|---------|-------|----------|
| **Qwen2.5-14B** (recommended) | `ollama pull qwen2.5:14b-instruct-q5_K_M` | ~12GB | Best | ~15 tok/s | Single product, high quality scripts |
| **Mistral-Nemo-12B** | `ollama pull mistral-nemo:12b-instruct-q5_K_M` | ~10GB | Great | ~20 tok/s | Daily use, good balance |
| **Llama-3.1-8B** | `ollama pull llama3.1:8b-instruct-q6_K` | ~7GB | Good | ~35 tok/s | Batch jobs, quick drafts |
| **Phi-3.5-Mini** | `ollama pull phi3.5:3.8b-mini-instruct-q6_K` | ~4GB | Decent | ~50 tok/s | Testing, rapid iteration |
| **Qwen2.5-32B** (max quality) | `ollama pull qwen2.5:32b-instruct-q4_K_M` | ~20GB* | Premium | ~5 tok/s | Final production scripts |

*The 32B model exceeds your 16GB VRAM — Ollama automatically offloads extra layers to your 32GB system RAM. It works, just slower. Best for final production runs when quality matters most.

**My recommendation:** Start with **Qwen2.5-14B**. It fits perfectly in your 16GB VRAM, leaves ~4GB headroom for the OS, and produces excellent scripts with reliable JSON output. Switch to the 8B model when batch-processing many products for speed.

**Configure in the app:**

1. Open http://localhost:8000
2. Click the Settings gear icon (top right)
3. Select "Ollama (Local — FREE)"
4. Set model to: `qwen2.5:14b-instruct-q5_K_M`
5. Click Save

**Or configure via .env file:**

```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b-instruct-q5_K_M
```

**Why Qwen2.5 specifically?** It's the best open model at following structured JSON instructions, which is critical for this app. Llama and Mistral sometimes produce malformed JSON with smaller quantizations. Qwen2.5 is consistently reliable.

**Ollama Troubleshooting on Ubuntu:**

```bash
# Check if Ollama is running
systemctl status ollama

# Restart Ollama
sudo systemctl restart ollama

# View Ollama logs
journalctl -u ollama -f

# List downloaded models
ollama list

# Test a model directly
ollama run qwen2.5:14b-instruct-q5_K_M "Hello, are you working?"

# Check GPU usage while running
nvidia-smi
```

### Option B: LM Studio (FREE — GUI Alternative)

LM Studio gives you a visual interface for downloading and managing models. Some people prefer this over the command line.

1. Download from https://lmstudio.ai (available for Linux, Windows, macOS)
2. In the Discover tab, search for "Qwen2.5-14B-Instruct-GGUF"
3. Download the Q5_K_M quantization
4. Go to the Server tab, load the model, click "Start Server"
5. In the ShadowCast Settings, select "LM Studio" and save

**LM Studio .env config:**

```bash
LLM_PROVIDER=lm_studio
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_MODEL=qwen2.5-14b-instruct
```

### Option C: OpenAI API (Paid — Easiest, No Local Setup)

If you want to get started immediately without any local LLM setup:

1. Go to https://platform.openai.com/api-keys
2. Click "Create new secret key" → Select "Service account"
3. Copy the key (you won't see it again)
4. Make sure you have credits loaded at platform.openai.com/settings/organization/billing
5. In the app Settings, select "OpenAI API", paste your key, save

**OpenAI .env config:**

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4.1-mini
```

Cost: ~$0.02 per video without voiceover. See the cost estimate document for detailed breakdowns.

### Option D: Any OpenAI-Compatible API

Works with vLLM, text-generation-webui, LocalAI, etc. In Settings, select "Custom" and enter your server URL and model name.

**Custom .env config:**

```bash
LLM_PROVIDER=custom
CUSTOM_BASE_URL=http://localhost:5000/v1
CUSTOM_API_KEY=your-key-if-needed
CUSTOM_MODEL=your-model-name
```

---

## Content Styles (What Makes This Different)

Instead of generic "Top 10 Best" videos that every channel makes, ShadowCast generates 6 trust-building content styles:

| Style | What It Does | Why It Works |
|-------|-------------|--------------|
| **Honest Review** (default) | Balanced pros AND cons, "Who It's NOT For" section | Viewers trust you because you're not just selling |
| **Elimination Round** | Show products you REJECTED, then reveal the winner | Massive credibility — you told them what NOT to buy |
| **Worth It or Waste?** | Test marketing claims against real review data | Series format, viewers come back for more |
| **Budget Challenge** | Best product under a specific price limit | Relatable for budget-conscious audiences |
| **VS Battle** | Head-to-head spec comparison, clear winner | High search volume, comparison shoppers ready to buy |
| **Standard Promo** | Classic features-and-benefits promotion | Quick promotional content when trust is already built |

Set the style per product in the form, in the CSV batch file, or as a global default.

---

## Hook Types (9 Total)

**Standard (what every channel uses):** Curiosity, Problem-Agitation, Listicle, Urgency, Contrarian

**Advanced (your competitive edge):**

- **Data Bomb** — "87% of people return this product. Here's the one they keep."
- **Confession** — "I've been recommending the wrong product. Here's the truth."
- **Comparison Trap** — "$200 vs $40. They perform identically. Here's proof."
- **Myth Buster** — "Everyone says you need to spend $300. That's a lie."

---

## Product Input Fields

### Core Fields

- **Product Name** — The product you're promoting
- **Key Features** — Main selling points (comma-separated)
- **Price** — Current price
- **Affiliate Link** — Your URL (auto-placed throughout all generated assets)

### Research Fields (Better Content, No Buying Required)

- **Competitors** — Competing products (used for eliminations and comparisons)
- **Common Complaints** — What reviewers complain about (from Amazon/Reddit). If blank, the AI generates plausible complaints from its training data.
- **Common Praises** — What reviewers love. Same as above.
- **Who This Is NOT For** — Specific people who should NOT buy this. Builds massive trust.
- **Price Comparison** — How price compares to competitors (e.g., "AirPods Pro costs $249 for similar features")

### Channel Building Fields

- **Series Name** — Recurring series name (e.g., "Worth It or Waste?", "The $50 Challenge")
- **Content Style** — Which style to use for this product
- **Target Audience** — Who this product is for

---

## Research Workflow (Zero Budget)

You don't need to buy any products. Here's the workflow:

1. **Find affiliate products** — Amazon Associates, ShareASale, Impact, CJ Affiliate
2. **Quick research (5 min per product):**
   - Amazon: Sort reviews by "Most Helpful" — note top 3 complaints and top 3 praises
   - Reddit: Search "[product name] review" — note real user opinions
   - Google: "[product] vs [competitor]" — note key differences
3. **Fill in the form** — Paste complaints, praises, competitor info
4. **Generate** — AI creates honest, research-backed scripts using language like "reviewers consistently say," "specs show," "based on 2,000+ reviews"
5. **Post** — Use the YouTube posting package as a copy-paste guide

The AI is specifically instructed to use research-based framing, never claiming personal testing experience.

---

## Batch Upload (CSV)

Process multiple products at once:

1. Click "Batch Upload (CSV)" tab
2. Download the template (includes all new trust-based fields)
3. Fill in your products — one row per product
4. Upload and generate

Each product gets its own folder with clearly named files:

```
output/
  job_id/
    soundcore_space_a40/
      soundcore_space_a40_curiosity_short_form.mp4
      soundcore_space_a40_curiosity_long_form.mp4
      soundcore_space_a40_curiosity_short_form_youtube_package.json
      soundcore_space_a40_YOUTUBE_POSTING_PACKAGE.txt
    anker_737_power_bank/
      anker_737_power_bank_data_bomb_short_form.mp4
      ...
    all_products.zip
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError` | Make sure your venv is activated: `source venv/bin/activate`, then `pip install -r backend/requirements.txt` |
| `ffmpeg not found` | `sudo apt install -y ffmpeg` |
| `No module named 'PIL'` | `pip install Pillow` |
| Ollama not connecting | Check status: `systemctl status ollama`. Restart: `sudo systemctl restart ollama` |
| `CUDA out of memory` | Switch to a smaller model (8B instead of 14B), or close other GPU apps. Check with `nvidia-smi` |
| Video rendering slow | Long-form videos take 2-5 min. Short-form is much faster on CPU. Try `SHADOWCAST_FFMPEG_CODEC=auto` if ffmpeg has NVENC |
| Live publish blocked (music) | Run `./scripts/fetch_operator_media.sh` or set `ALLOW_SYNTH_MUSIC_PUBLISH=1` |
| Media library missing moods | `curl -fsS http://127.0.0.1:8000/api/media-library` — drop `{mood}.wav` under `backend/assets/music/` |
| Kokoro unavailable | Install `kokoro-onnx` + place `kokoro-v1.0.onnx` and `voices-v1.0.bin` in `backend/assets/kokoro/` |
| JSON parse errors from LLM | Use Qwen2.5 models — they're best at structured JSON output. Avoid smaller quantizations (Q2, Q3) |
| Model loading slow first time | Normal — first inference loads model into VRAM. Subsequent requests are fast |
| Port 8000 in use | Run with `PORT=8001 python3 backend/app.py` (bind via `HOST`/`PORT` env; do not edit `app.py`) |
| Prefer `.venv` | Canonical env is `.venv` (`python3 -m venv .venv`); `venv/` remains a legacy alias |
| `Permission denied` on Linux | Make sure you own the directory: `sudo chown -R $USER:$USER ~/shadowcast-` |
| `externally-managed-environment` error | Use a venv (Step 6 above) or add `--break-system-packages` flag to pip |
| Fonts look wrong | Run `sudo apt install -y fonts-noto` and restart the app |
| Can't access from another device on LAN | Set `HOST=0.0.0.0` in `backend/.env` (default is `127.0.0.1` for localhost-only trust), restart, then use your machine's IP |
| Firewall blocking port 8000 | `sudo ufw allow 8000/tcp` |

---

## Updating ShadowCast

To pull the latest version:

```bash
cd ~/shadowcast-
git pull origin main
source venv/bin/activate
pip install -r backend/requirements.txt
```

If you've made local changes and get merge conflicts:

```bash
git stash
git pull origin main
git stash pop
```

---

## Uninstalling

```bash
# Stop the service if running
systemctl --user stop shadowcast.service
systemctl --user disable shadowcast.service
rm ~/.config/systemd/user/shadowcast.service

# Remove the app
rm -rf ~/shadowcast-

# Remove the desktop shortcut
rm ~/.local/share/applications/shadowcast.desktop

# Remove Ollama (if installed)
sudo systemctl stop ollama
sudo systemctl disable ollama
sudo rm /usr/local/bin/ollama
rm -rf ~/.ollama
```

---

## File Structure

```
shadowcast-/
├── backend/
│   ├── app.py                      # FastAPI server (main entry point)
│   ├── script_generator.py         # Trust-based script generation (9 hooks, 6 styles)
│   ├── video_renderer.py           # MP4 video rendering engine with kinetic effects
│   ├── kinetic_effects.py          # Word-by-word, typewriter, impact scale, etc.
│   ├── brand_overlays.py           # Branded intro/outro, lower thirds, engagement cards
│   ├── youtube_assets_generator.py # YouTube SEO package generator
│   ├── tts_generator.py            # Voiceover (Kokoro/Piper/OpenAI/gTTS)
│   ├── tts_pronounce.py            # Pronunciation lexicon
│   ├── media_library.py            # Music/B-roll inventory API
│   ├── llm_config.py              # LLM provider config + model recommendations
│   ├── .env.example               # Environment config template
│   ├── requirements.txt           # Python dependencies
│   └── assets/                    # Fonts for video rendering
├── frontend/
│   ├── index.html                 # Web UI (single-page app)
│   └── assets/
│       └── LOGO_README.txt        # Drop your logo.png here
├── product_template.csv           # Batch upload template with all fields
├── SETUP_GUIDE.md                 # This file
└── .gitignore                     # Git ignore rules
```

---

## Support

For issues, feature requests, or contributions, visit the GitHub repo:
https://github.com/unlovedproductions/shadowcast-

**Unloved Productions** — *Forged in Passion*
