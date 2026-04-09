# ShadowCast — Trust-Based Faceless Affiliate Video Generator

**ShadowCast** is a professional-grade, faceless text-only video production engine designed for high-conversion affiliate marketing. Unlike generic AI video tools, ShadowCast employs a **trust-first approach**, generating research-based "Honest Reviews," "Elimination Rounds," and "VS Battles" that build genuine credibility with audiences without requiring physical product testing.

---

## 🚀 Key Capabilities

### 1. Multi-Format Video Rendering
- **Short-Form (9:16):** Optimized for TikTok, YouTube Shorts, and Instagram Reels with high-retention kinetic typography.
- **Long-Form (16:9):** Structured for full YouTube reviews and comparison guides.
- **Kinetic Typography Engine:** Features word-by-word reveals, impact scaling, and highlight sweeps to maintain viewer engagement.

### 2. Trust-First Content Styles
ShadowCast moves beyond simple "hype" to provide structured marketing formats:
- **Honest Review:** Balanced pros and cons with "Who This Is NOT For" segments.
- **Elimination Round:** Suspension-building format that rejects competitors to reveal a "winner."
- **VS Battle:** Spec-by-spec head-to-head comparisons between products.
- **Budget Challenge:** Identifies the best value-for-money options under specific price points.

### 3. Automated Research & Sourcing
- **Amazon Scraper:** Extracts specs, pricing, and real user sentiment (praises/complaints) directly from Amazon.
- **YouTube Research:** Integrated autocomplete and long-tail keyword discovery for SEO-optimized topic selection.
- **LLM-Driven Scripting:** Uses local (Ollama) or cloud (OpenAI) models to synthesize research into compelling scripts.

### 4. Full Publishing Packages
- **SEO Assets:** Generates optimized titles, 2000+ character descriptions, and tag sets.
- **Engagement Tools:** Produces pinned comments, community post templates, and reply scripts.
- **Thumbnail Generator:** Creates high-click-through-rate thumbnail sets with branded badges.

### 5. Affiliate Performance & Analytics
- **Attribution:** Built-in tracking link generator for monitoring clicks across platforms.
- **Performance Dashboard:** Tracks video-level and product-level ROI metrics.
- **Social Posting:** Integrated API support for direct scheduling to Instagram and TikTok.

### 6. Enhanced Branding & Testing
- **Channel Profile Picture Integration:** Seamlessly integrates your YouTube channel profile picture into branded intros and outros, automatically circularized for a professional look.
- **Comprehensive Testing Plan:** Designed for real-world validation, ensuring every feature, hook, and content style is tested to generate high-quality content for your review channel.

---

## 🛠 Tech Stack
- **Backend:** FastAPI (Python 3.10+)
- **Rendering:** MoviePy, PIL (Pillow), FFmpeg
- **AI/LLM:** OpenAI API or Local LLM (Ollama, LM Studio)
- **Frontend:** HTML5/JS (Single-page application)
- **Database:** JSON-based persistent storage for jobs and analytics

---

## 📦 Installation & Setup

### Prerequisites
- Python 3.10+
- FFmpeg
- NVIDIA GPU (Optional, for local LLM acceleration)

### Quick Start
1. **Clone the repo:**
   ```bash
   git clone https://github.com/unlovedproductions/shadowcast-.git
   cd shadowcast-
   ```
2. **Setup Environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r backend/requirements.txt
   ```
3. **Launch:**
   ```bash
   python3 backend/app.py
   ```
4. **Access:** Open `http://localhost:8000` in your browser.

---

## 🤝 Integration with APF
ShadowCast is designed to work seamlessly with the **Affiliate Product Finder (APF)**. You can export "Hidden Gem" products discovered in APF as a JSON package and import them directly into ShadowCast for instant, batch video production.

---

## ⚖️ License & Disclaimer
Created by **Unloved Productions**. This tool is intended for affiliate marketing research and content generation. Users are responsible for ensuring compliance with platform-specific disclosure requirements (e.g., FTC guidelines).
