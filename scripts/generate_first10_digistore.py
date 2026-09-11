#!/usr/bin/env python3
"""Batch-generate short+long honest_review videos for APF Digistore products 1-10."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("LLM_FALLBACK_CHAIN", "ollama")

from apf_import import as_snake_product_info, normalize_apf_payload  # noqa: E402

APF_EXPORTS = Path("/home/unloved/APF/exports")
BASE_URL = "http://127.0.0.1:8000"
HOOK = "curiosity"
FORMATS = ["short_form", "long_form"]

# Web-verified product stills (official/vendor pages; used when APF export has none).
IMAGE_URLS: dict[str, str] = {
    "1": "https://uswaterrevolution.com/wp-content/uploads/image065.webp",  # vendor hero, not the op-builder sound icon
    "2": "https://assets.advancedbionutritionals.com/Images/Products-2020/Advanced-Amino-Formula/1bottle.png",
    "3": "https://geniuswave.org/images/prd-img-mini.webp",
    "4": "https://medicinal-garden-kit.com/assets/img/medicinal-garden-kit-ten-herbs-collage.webp",
    "5": "https://www.askaprepper.com/wp-content/uploads/2020/12/Self-Sufficient-Backyard-LOGO-250.jpg",
    "6": "https://www.your-creatory.com/wp-content/plugins/wp-youtube-lyte/lyteCache.php?origThumbUrl=https%3A%2F%2Fi.ytimg.com%2Fvi%2FDEi-PVAmTKY%2Fhqdefault.jpg",
    "7": "https://wealthsignaloriginal.com/vsl/images/product-hero.png",
    "8": "https://i.ytimg.com/vi/ckUtokXQu64/hqdefault.jpg",
    "9": "https://assets.advancedbionutritionals.com/Images/Products/CircO2/1box.png",
    "10": "https://assets.advancedbionutritionals.com/Images/Landing-Pages-2020/Mitochondrial-2023/High-Design/header-bottle.png",
}

# Web-verified overlays keyed by APF source_product_id (plan table).
OVERLAYS: dict[str, dict] = {
    "1": {
        "product_name": "Joseph's Well DIY Atmospheric Water Generator Guide",
        "niche": "Off-grid water / prepper DIY",
        "product_category": "DIY water independence guides",
        "price": "$83.45",
        "keywords": [
            "Joseph's Well review",
            "atmospheric water generator DIY",
            "off-grid water",
            "megadrought",
            "prepper water",
        ],
        "key_features": [
            "Digital DIY guide for building an atmospheric water generator",
            "Video tutorials and printable blueprints",
            "Materials list; build cost often $150–$400 in parts",
            "Output depends on humidity; realistic DIY ceiling around 10 gal/day",
            "60-day Digistore24 money-back guarantee",
        ],
        "competitors": ["Aqua Tower DIY AWG guide", "Commercial Watergen units", "SOURCE Hydropanels"],
        "unique_selling_point": "Step-by-step DIY guide to condense drinking water from ambient air — not a shipped device.",
        "common_praises": "Real AWG physics; low entry price vs commercial units; useful in humid climates for backup water.",
        "common_complaints": "Sales pages overstate gallons per day; dry climates see weak output; requires DIY build time and electricity.",
        "who_not_for": "Buyers expecting a plug-and-play device; arid regions under 30% humidity; people who won't source parts or build.",
        "price_comparison": "Commercial AWG units cost thousands; this guide plus parts is far cheaper but you build it yourself.",
        "target_audience": "Preppers, homesteaders, and off-grid households researching humidity-based water backup",
    },
    "2": {
        "product_name": "Advanced Amino Formula",
        "niche": "Sports nutrition / healthy aging",
        "product_category": "Essential amino acid supplements",
        "price": "$39.95",
        "keywords": [
            "Advanced Amino Formula review",
            "essential amino acids",
            "muscle after 40",
            "Advanced Bionutritionals",
            "vegan EAA tablets",
        ],
        "key_features": [
            "All 8 essential amino acids in vegan tablets",
            "150 tablets; 5 tablets daily (30-day bottle)",
            "Formulated by Dr. Frank Shallenberger / Advanced Bionutritionals",
            "90-day money-back guarantee",
            "Sold via Digistore24 checkout",
        ],
        "competitors": ["PerfectAmino", "BCAA-only stacks", "Whey protein"],
        "unique_selling_point": "Complete EAA profile for adults 40+ focused on muscle maintenance and daily energy.",
        "common_praises": "Easy tablet format; vegan; users report better recovery and tone over weeks.",
        "common_complaints": "Five pills daily is a lot; results take weeks; premium vs generic aminos.",
        "who_not_for": "People wanting instant muscle gains; those who prefer flavored protein shakes only.",
        "price_comparison": "Single bottle $39.95; multi-bottle bundles lower per-bottle cost on official site.",
        "target_audience": "Active adults 40+ preserving lean muscle and stamina",
    },
    "3": {
        "product_name": "The Genius Wave",
        "niche": "Mindfulness / focus audio",
        "product_category": "Digital binaural audio programs",
        "price": "$49.86",
        "keywords": [
            "Genius Wave review",
            "theta binaural beats",
            "7 minute audio",
            "focus audio",
            "brainwave entrainment",
        ],
        "key_features": [
            "7-minute daily binaural/isochronic audio track (MP3 download)",
            "Marketed for theta brainwave relaxation and focus",
            "Requires stereo headphones",
            "One-time digital purchase; check checkout for current price",
            "Money-back window varies by funnel — verify at purchase",
        ],
        "competitors": ["Headspace", "Free YouTube binaural tracks", "Brain.fm"],
        "unique_selling_point": "Short daily audio ritual for relaxation and focus — not a pill or device.",
        "common_praises": "Low effort; some listeners like the quick daily routine.",
        "common_complaints": "Aggressive upsells at checkout; NASA-style claims are marketing; free alternatives exist.",
        "who_not_for": "Buyers expecting guaranteed IQ gains or clinical proof from one audio file.",
        "price_comparison": "Similar audio programs often $39 one-time; compare to subscription meditation apps.",
        "target_audience": "Adults wanting a low-effort daily focus or calm ritual",
    },
    "4": {
        "product_name": "Medicinal Garden Kit",
        "niche": "Herbal gardening / self-reliance",
        "product_category": "Heirloom medicinal seed kits",
        "price": "$72.91",
        "keywords": [
            "Medicinal Garden Kit review",
            "Nicole Apelian",
            "heirloom herb seeds",
            "backyard pharmacy",
            "medicinal garden",
        ],
        "key_features": [
            "10 non-GMO heirloom medicinal herb seed packets",
            "Printed Herbal Medicinal Guide: From Seeds to Remedies",
            "Physical kit shipped; bonus digital guides on many funnels",
            "365-day money-back on official ClickBank/Digistore funnels",
            "Educational gardening — not a substitute for medical care",
        ],
        "competitors": ["Burpee herb seed packs", "Strictly Medicinal seeds", "Local nursery herb starts"],
        "unique_selling_point": "Curated medicinal herb garden starter with remedy prep instructions.",
        "common_praises": "Beginner-friendly; good gift for homesteaders; Apelian credibility.",
        "common_complaints": "Premium vs buying seed packets separately; growing results vary by climate.",
        "who_not_for": "Apartment dwellers without grow space; anyone treating this as medical treatment.",
        "price_comparison": "Official funnels often ~$59 plus shipping; this Digistore cart shows $72.91.",
        "target_audience": "Homesteaders and natural-health gardeners building a backyard herb patch",
    },
    "5": {
        "product_name": "The Self-Sufficient Backyard",
        "niche": "Homesteading / self-reliance",
        "product_category": "Homesteading guidebooks",
        "price": "$50.99",
        "keywords": [
            "Self-Sufficient Backyard review",
            "Ron Melchiore",
            "Johanna Melchiore",
            "homesteading book",
            "food independence",
        ],
        "key_features": [
            "266-page guide by Ron and Johanna Melchiore",
            "100+ homestead projects: garden, water, energy, food preservation",
            "Digital PDF and printed options depending on funnel",
            "60-day money-back guarantee on official offers",
            "Authors lived off-grid 40+ years",
        ],
        "competitors": ["The Encyclopedia of Country Living", "Storey homestead guides", "Mother Earth News books"],
        "unique_selling_point": "Practical homestead playbook from long-term off-grid practitioners.",
        "common_praises": "Actionable projects; broad scope; strong Amazon reader ratings.",
        "common_complaints": "Needs yard or land; not for apartments; some topics are introductory.",
        "who_not_for": "Apartment renters; advanced homesteaders wanting specialist depth only.",
        "price_comparison": "Official digital often $37; this Digistore checkout is $50.99.",
        "target_audience": "Homeowners and preppers planning backyard food and energy independence",
    },
    "6": {
        "product_name": "Love Your Serger Online Course",
        "niche": "Sewing / crafts education",
        "product_category": "Online serger courses",
        "price": "$67.00",
        "keywords": [
            "Love Your Serger review",
            "serger course",
            "overlocker tutorial",
            "your-creatory",
            "sewing class",
        ],
        "key_features": [
            "44 HD video lessons (~6+ hours) from your-creatory.com",
            "Threading, tension, troubleshooting, 22 stitch types",
            "Bonus tote bag and cushion projects",
            "Lifetime access; 60-day Digistore24 refund",
            "Promo code love5d sometimes available on sales page",
        ],
        "competitors": ["Craftsy serger classes", "YouTube serger tutorials", "Dealer machine classes"],
        "unique_selling_point": "Structured serger mastery course for any brand of overlock machine.",
        "common_praises": "Clear teaching; good for beginners; rewatchable videos.",
        "common_complaints": "You need a serger already; list price marketing vs promo price confusion.",
        "who_not_for": "Non-sewers; people without a serger or overlocker.",
        "price_comparison": "Listed at $199 MSRP; promo checkout $67 on Digistore24.",
        "target_audience": "Home sewists intimidated by threading and tension on their serger",
        "coupon_code": "love5d",
    },
    "7": {
        "product_name": "The Wealth Signal",
        "niche": "Mindset / personal development audio",
        "product_category": "Digital audio self-help",
        "price": "$51.32",
        "keywords": [
            "Wealth Signal review",
            "9 word script",
            "mindset audio",
            "abundance meditation",
            "theta audio",
        ],
        "key_features": [
            "Digital audio plus PDF guide (instant download)",
            "7–10 minute daily alpha/theta entrainment track",
            "9-word wealth script framing — mindset tool not investing advice",
            "One-time purchase; upsells may appear at checkout",
            "Refund window varies by funnel — verify at purchase",
        ],
        "competitors": ["Headspace", "Think and Grow Rich audiobook", "Free meditation apps"],
        "unique_selling_point": "Short daily audio aimed at money mindset blocks — not stock picks or signals.",
        "common_praises": "Low time commitment; some users like the ritual.",
        "common_complaints": "Manifestation marketing oversells outcomes; not financial advice.",
        "who_not_for": "Anyone expecting guaranteed income or investment returns.",
        "price_comparison": "Public funnels often $39; this Digistore cart is $51.32.",
        "target_audience": "Adults exploring mindset routines around money stress — not traders",
    },
    "8": {
        "product_name": "Primal Grow Pro",
        "niche": "Men's wellness supplements",
        "product_category": "Male enhancement supplements",
        "price": "$94.19",
        "keywords": [
            "Primal Grow Pro review",
            "male enhancement supplement",
            "libido support",
            "men's vitality",
            "Digistore24",
        ],
        "key_features": [
            "Herbal capsule formula (maca, horny goat weed, tribulus, L-arginine, etc.)",
            "Marketed for libido and stamina — not FDA approved to treat disease",
            "60-day refund policy via payment processor",
            "Proprietary blend — exact doses often undisclosed",
            "Talk to a doctor if you take heart or BP meds",
        ],
        "competitors": ["Transparent Labs men's health", "Legit telehealth ED options", "Generic maca/tribulus"],
        "unique_selling_point": "All-in-one herbal male vitality capsule stack sold online.",
        "common_praises": "Some report mild energy or libido bump.",
        "common_complaints": "Size-increase claims not proven; scam-detector flags; refund hassle reports.",
        "who_not_for": "Men on nitrates or ED prescriptions; buyers expecting guaranteed enlargement.",
        "price_comparison": "Often ~$69–$94 per bottle on funnels; multi-bottle packs discount per bottle.",
        "target_audience": "Men researching herbal libido support with skeptical expectations",
    },
    "9": {
        "product_name": "CircO2 Nitric Oxide Booster",
        "niche": "Heart health / circulation supplements",
        "product_category": "Nitric oxide lozenges",
        "price": "$49.95",
        "keywords": [
            "CircO2 review",
            "nitric oxide lozenge",
            "circulation supplement",
            "Advanced Bionutritionals",
            "beetroot NO booster",
        ],
        "key_features": [
            "Quick-dissolve sublingual lozenge by Advanced Bionutritionals",
            "Beetroot nitrate and L-citrulline style NO support blend",
            "30 lozenges per box; one daily typical dose",
            "90-day money-back guarantee on official site",
            "Not intended to treat heart disease — ask doctor if on BP meds",
        ],
        "competitors": ["HumanN SuperBeets", "Neo40", "Generic beetroot powder"],
        "unique_selling_point": "Fast-dissolve lozenge format for nitric oxide support vs pills alone.",
        "common_praises": "Some users report energy and workout stamina bump.",
        "common_complaints": "Taste strong; mixed vendor reviews (~3.8/5); not a substitute for medical care.",
        "who_not_for": "Anyone on blood pressure or ED meds without doctor approval.",
        "price_comparison": "Official 1-box often $59.95; this Digistore cart shows $49.95.",
        "target_audience": "Active adults 40+ exploring circulation and energy support supplements",
    },
    "10": {
        "product_name": "Advanced Mitochondrial Formula",
        "niche": "Healthy aging / cellular energy",
        "product_category": "Mitochondrial support supplements",
        "price": "$79.95",
        "keywords": [
            "Advanced Mitochondrial Formula review",
            "CoQ10 PQQ supplement",
            "mitochondrial support",
            "Advanced Bionutritionals",
            "energy after 40",
        ],
        "key_features": [
            "11-nutrient blend: CoQ10, PQQ, acetyl-L-carnitine, D-ribose, curcumin, and more",
            "2 capsules daily; 60-tablet bottle (30-day supply)",
            "Vegan, non-GMO; Advanced Bionutritionals / Digistore24",
            "90-day money-back guarantee",
            "Supports cellular energy — not a disease treatment",
        ],
        "competitors": ["Life Extension Mitochondrial Essentials", "MitoQ", "Standalone CoQ10"],
        "unique_selling_point": "Multi-ingredient mitochondrial stack vs single CoQ10 only.",
        "common_praises": "Users report less afternoon fatigue over 4–8 weeks.",
        "common_complaints": "Premium price; some ingredient doses below clinical trial levels.",
        "who_not_for": "People expecting overnight energy fixes; those on blood thinners without MD guidance.",
        "price_comparison": "Multi-bottle bundles lower per-bottle cost on official Advanced Bionutritionals site.",
        "target_audience": "Adults 40+ with fatigue exploring mitochondrial cofactor supplements",
    },
}


def _http(
    method: str,
    path: str,
    body: dict | None = None,
    timeout: int = 120,
    retries: int = 30,
) -> dict:
    url = f"{BASE_URL}{path}"
    data = None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ConnectionResetError) as exc:
            last_err = exc
            if attempt + 1 >= retries:
                break
            time.sleep(min(30, 5 + attempt * 2))
    raise RuntimeError(f"HTTP {method} {path} failed after {retries} tries: {last_err}") from last_err


def load_exports() -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    for path in sorted(APF_EXPORTS.glob("*_shadowcast_enriched.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        pid = str((doc.get("product") or {}).get("source_product_id") or "").strip()
        if pid and pid not in by_id:
            by_id[pid] = doc
    return by_id


def apply_overlay(doc: dict, overlay: dict, product_id: str) -> dict:
    out = json.loads(json.dumps(doc))
    imp = out.setdefault("shadowcast_import", {})
    imp.update({k: v for k, v in overlay.items() if k != "review_brief_patch"})
    if img := IMAGE_URLS.get(product_id):
        imp["image_url"] = img
    if rb_patch := overlay.get("review_brief_patch"):
        brief = out.setdefault("review_brief", {})
        brief.update(rb_patch)
    imp["content_style"] = "honest_review"
    return out


def to_product_info(doc: dict, product_id: str = "") -> dict:
    result = normalize_apf_payload(doc)
    info = as_snake_product_info(result["normalized"])
    if product_id and (img := IMAGE_URLS.get(product_id)):
        info["image_url"] = img
    return info


def start_job(product_info: dict) -> str:
    payload = {
        "product_info": product_info,
        "hook_types": [HOOK],
        "formats": FORMATS,
        "content_style": "honest_review",
        "audio_enabled": True,
        "audio_mood": "auto",
        "use_tts": True,
        "tts_provider": "auto",
        "video_preset": "medium",
    }
    resp = _http("POST", "/api/generate", payload)
    job_id = resp.get("job_id")
    if not job_id:
        raise RuntimeError(f"Generate missing job_id: {resp}")
    return job_id


def wait_job(job_id: str, timeout_sec: int = 9000) -> dict:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        status = _http("GET", f"/api/status/{job_id}")
        st = status.get("status")
        step = status.get("current_step") or ""
        prog = status.get("progress")
        print(f"  [{job_id}] {st} {prog}% — {step}", flush=True)
        if st in ("completed", "partial", "failed", "error", "cancelled"):
            if st in ("failed", "error", "cancelled"):
                raise RuntimeError(f"Job {job_id} ended with status={st}: {status.get('errors')}")
            summary = status.get("summary") or {}
            expected = int(summary.get("videos_expected") or 0)
            ready = int(summary.get("videos_ready") or 0)
            if expected and ready < expected:
                raise RuntimeError(
                    f"Job {job_id} incomplete ({ready}/{expected} videos): {status.get('errors')}"
                )
            return status
        time.sleep(20)
    raise TimeoutError(f"Job {job_id} timed out after {timeout_sec}s")


def publish_quality(job_id: str, fmt: str) -> dict:
    try:
        return _http(
            "POST",
            "/api/publish/quality",
            {
                "job_id": job_id,
                "hook_type": HOOK,
                "video_format": fmt,
            },
            retries=2,
        )
    except RuntimeError as exc:
        return {"overall": "SKIP", "detail": str(exc)}


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text.strip("_")[:60] or "product"


def _job_has_product_image(job_id: str) -> bool:
    job_json = REPO / "backend" / "output" / job_id / "job.json"
    if not job_json.is_file():
        return False
    try:
        info = json.loads(job_json.read_text(encoding="utf-8")).get("product_info") or {}
        return bool(str(info.get("image_url") or "").strip())
    except (OSError, json.JSONDecodeError):
        return False


def _product_videos_complete(product_name: str) -> tuple[str | None, bool]:
    slug = slugify(product_name)
    best: tuple[float, str] | None = None
    for job_dir in (REPO / "backend" / "output").glob("*"):
        if not job_dir.is_dir() or len(job_dir.name) != 8:
            continue
        short = job_dir / f"{slug}_{HOOK}_short_form.mp4"
        long = job_dir / f"{slug}_{HOOK}_long_form.mp4"
        if not (short.is_file() and long.is_file() and short.stat().st_size > 0 and long.stat().st_size > 0):
            continue
        if not _job_has_product_image(job_dir.name):
            continue
        mtime = max(short.stat().st_mtime, long.stat().st_mtime)
        if best is None or mtime > best[0]:
            best = (mtime, job_dir.name)
    if best:
        return best[1], True
    return None, False


def _gate_qa_failed(pid: str, args: argparse.Namespace, qa_short: dict, qa_long: dict) -> bool:
    """Only product 1 gate stops the batch on pre-publish QA FAIL."""
    if not (args.gate_only and pid == "1"):
        return False
    return qa_short.get("overall") == "FAIL" or qa_long.get("overall") == "FAIL"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", default="1-10", help="Product ids e.g. 1 or 1-10 or 1,3,5")
    parser.add_argument("--gate-only", action="store_true", help="Only run product 1 gate")
    parser.add_argument("--resume", action="store_true", help="Skip products that already have short+long MP4s")
    args = parser.parse_args()

    if "-" in args.ids and "," not in args.ids:
        a, b = args.ids.split("-", 1)
        wanted = [str(i) for i in range(int(a), int(b) + 1)]
    else:
        wanted = [x.strip() for x in args.ids.split(",") if x.strip()]

    exports = load_exports()
    missing = [i for i in wanted if i not in exports]
    if missing:
        print(f"Missing export JSON for ids: {missing}", file=sys.stderr)
        return 1

    results = []
    for pid in wanted:
        overlay = OVERLAYS.get(pid)
        if not overlay:
            print(f"No overlay for id {pid}", file=sys.stderr)
            return 1
        doc = apply_overlay(exports[pid], overlay, pid)
        product_info = to_product_info(doc, pid)
        name = product_info.get("product_name", pid)
        print(f"\n=== Product {pid}: {name} ===", flush=True)
        if args.resume:
            job_id, done = _product_videos_complete(name)
            if done and job_id:
                print(f"  resume: skip generate — existing job {job_id}", flush=True)
                qa_short = publish_quality(job_id, "short_form")
                qa_long = publish_quality(job_id, "long_form")
                print(f"  QA short={qa_short.get('overall')} long={qa_long.get('overall')}", flush=True)
                results.append(
                    {
                        "product_id": pid,
                        "product_name": name,
                        "job_id": job_id,
                        "qa_short": qa_short.get("overall"),
                        "qa_long": qa_long.get("overall"),
                        "resumed": True,
                    }
                )
                if pid == "1" and args.gate_only:
                    break
                if _gate_qa_failed(pid, args, qa_short, qa_long):
                    print("QA FAIL — stopping batch.", file=sys.stderr)
                    break
                continue
        print(f"  price={product_info.get('price')} image_url={'yes' if product_info.get('image_url') else 'NO'}", flush=True)
        job_id = start_job(product_info)
        print(f"  started job {job_id}", flush=True)
        wait_job(job_id)
        qa_short = publish_quality(job_id, "short_form")
        qa_long = publish_quality(job_id, "long_form")
        print(f"  QA short={qa_short.get('overall')} long={qa_long.get('overall')}", flush=True)
        results.append(
            {
                "product_id": pid,
                "product_name": name,
                "job_id": job_id,
                "qa_short": qa_short.get("overall"),
                "qa_long": qa_long.get("overall"),
            }
        )
        if pid == "1" and args.gate_only:
            break
        if _gate_qa_failed(pid, args, qa_short, qa_long):
            print("QA FAIL — stopping batch.", file=sys.stderr)
            break

    out_path = REPO / "backend" / "output" / "first10_digistore_results.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
