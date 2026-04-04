# ShadowCast — Setup Guide

## by Unloved Productions | Forged in Passion
### Optimized for Razer Blade 15 Advanced

**ShadowCast** is a faceless text-only affiliate video generator built with a **trust-first approach** — honest reviews, elimination rounds, comparison battles, and budget challenges that build credibility and convert better than generic hype content. No need to buy or test products; all content is research-based using public specs, reviews, and comparison data.

> *"Creating software for the problems you didn't know you had"* — Unloved Productions

---

## Your Machine Specs

| Component | Spec | LLM Capability |
|-----------|------|----------------|
| **GPU** | NVIDIA RTX 3080 Laptop (16GB GDDR6 VRAM) | Runs 7B-14B models natively, 32B with offload |
| **RAM** | 32GB DDR4 3200MHz | Supports CPU offload for larger models |
| **CPU** | Intel i9-11900H (8C/16T, up to 4.9GHz) | Fast model loading and video rendering |
| **CUDA** | 8.6 (Ampere, 6144 CUDA cores) | Full cuBLAS acceleration for LLMs |
| **Storage** | 1TB NVMe PCIe 4.0 | Fast model loading from disk |

---

## Quick Start (5 Minutes)

### Step 1: Install Prerequisites

**Python 3.8+:**
```
python --version
```
If not installed, download from [python.org/downloads](https://python.org/downloads). Check "Add Python to PATH" during install.

**FFmpeg** (required for video rendering):
```
winget install ffmpeg
```
Or download from [ffmpeg.org/download.html](https://ffmpeg.org/download.html) and add the `bin` folder to your system PATH.

### Step 2: Install Python Dependencies

```bash
cd webapp/backend
pip install -r requirements.txt
```

### Step 3: Configure Your LLM Provider

```bash
cp .env.example .env
```
Edit `.env` and uncomment ONE provider option (see detailed LLM Setup below).

Or skip this step — you can configure everything through the app's Settings panel.

### Step 4: Launch the App

```bash
python app.py
```

Open your browser to: **http://localhost:8000**

---

## LLM Setup — Choose Your Provider

### Option A: Ollama (FREE — Recommended for Your Machine)

Ollama is the easiest way to run LLMs locally. Zero cost, runs entirely on your Razer Blade 15.

**Install Ollama:**
1. Go to https://ollama.com/download
2. Download and install the Windows version
3. Ollama runs as a background service automatically

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

**Why Qwen2.5 specifically?** It's the best open model at following structured JSON instructions, which is critical for this app. Llama and Mistral sometimes produce malformed JSON with smaller quantizations. Qwen2.5 is consistently reliable.

### Option B: LM Studio (FREE — GUI Alternative)

LM Studio gives you a visual interface for downloading and managing models. Some people prefer this over the command line.

1. Download from https://lmstudio.ai
2. In the Discover tab, search for "Qwen2.5-14B-Instruct-GGUF"
3. Download the Q5_K_M quantization
4. Go to the Server tab, load the model, click "Start Server"
5. In the video generator Settings, select "LM Studio" and save

### Option C: OpenAI API (Paid — Easiest, No Local Setup)

If you want to get started immediately:

1. Go to https://platform.openai.com/api-keys
2. Click "Create new secret key" → Select "Service account"
3. Copy the key (you won't see it again)
4. Make sure you have credits loaded at platform.openai.com/settings/organization/billing
5. In the app Settings, select "OpenAI API", paste your key, save

Cost: ~$0.02 per video without voiceover. See the cost estimate document for detailed breakdowns.

### Option D: Any OpenAI-Compatible API

Works with vLLM, text-generation-webui, LocalAI, etc. In Settings, select "Custom" and enter your server URL and model name.

---

## Content Styles (What Makes This Different)

Instead of generic "Top 10 Best" videos that every channel makes, this app generates 6 trust-building content styles:

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
| `ModuleNotFoundError` | Run `pip install -r backend/requirements.txt` again |
| `ffmpeg not found` | Install ffmpeg and make sure it's in your PATH |
| Ollama not connecting | Make sure Ollama is running: `ollama list` should show models |
| Out of VRAM | Switch to a smaller model (8B instead of 14B), close other GPU apps |
| Video rendering slow | Long-form videos take 2-5 min. Short-form is much faster. |
| JSON parse errors | Use Qwen2.5 models — they're best at structured JSON output |
| Model loading slow first time | Normal — first inference loads model into VRAM. Subsequent requests are fast. |
| Port 8000 in use | Edit last line of `app.py`: change `port=8000` to `port=8001` |
| Bootloader issues on your machine | Fix your NVMe bootloader first, then install the app. The app itself is lightweight. |

---

## File Structure

```
webapp/
├── backend/
│   ├── app.py                      # FastAPI server (main entry point)
│   ├── script_generator.py         # Trust-based script generation (9 hooks, 6 styles)
│   ├── video_renderer.py           # MP4 video rendering engine
│   ├── youtube_assets_generator.py # YouTube SEO package generator
│   ├── tts_generator.py            # Optional voiceover (gTTS — free)
│   ├── llm_config.py              # LLM provider config + model recommendations
│   ├── .env.example               # Environment config template
│   ├── requirements.txt           # Python dependencies
│   └── assets/                    # Fonts for video rendering
├── frontend/
│   └── index.html                 # Web UI (single-page app)
├── product_template.csv           # Batch upload template with all fields
└── SETUP_GUIDE.md                 # This file
```
