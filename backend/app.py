"""
ShadowCast — FastAPI Backend by Unloved Productions
Supports single product, batch CSV upload, content styles, and
research-based honest review generation.
"""

import csv
import io
import json
import os
import re
import time
import uuid
import threading
import traceback
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional

import llm_config
from script_generator import (
    generate_selected_scripts, HOOK_TYPES, HOOK_DESCRIPTIONS,
    CONTENT_STYLES, DEFAULT_CONTENT_STYLE,
)
from video_renderer import render_short_form_video, render_long_form_video
from youtube_assets_generator import generate_youtube_assets, save_posting_package_readable

app = FastAPI(title="ShadowCast by Unloved Productions", version="4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_BASE = Path(__file__).parent / "output"
OUTPUT_BASE.mkdir(exist_ok=True)

# ── In-memory job store ────────────────────────────────────────────────
jobs = {}


# ── Helpers ────────────────────────────────────────────────────────────
def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '_', text)
    text = text.strip('_')
    return text[:60] or "product"


def fmt_label(fmt: str) -> str:
    return "short_form" if fmt == "short_form" else "long_form"


def fmt_display(fmt: str) -> str:
    return "Short-Form" if fmt == "short_form" else "Long-Form"


# ── Pydantic Models ───────────────────────────────────────────────────
class LLMConfigRequest(BaseModel):
    provider: str = "openai"
    api_key: str = ""
    base_url: str = ""
    model: str = ""


class ProductInfo(BaseModel):
    product_name: str
    niche: str = "General"
    key_features: List[str] = []
    price: str = "$49.99"
    affiliate_link: str = "[YOUR_AFFILIATE_LINK]"
    keywords: List[str] = []
    target_audience: str = "General consumers"
    product_category: str = ""
    competitors: List[str] = []
    unique_selling_point: str = ""
    discount_info: str = ""
    coupon_code: str = ""
    # ── New trust-based fields ──
    common_complaints: str = ""
    common_praises: str = ""
    who_not_for: str = ""
    series_name: str = ""
    price_comparison: str = ""
    content_style: str = DEFAULT_CONTENT_STYLE


class GenerateRequest(BaseModel):
    product_info: ProductInfo
    hook_types: List[str] = ["curiosity"]
    formats: List[str] = ["short_form", "long_form"]
    content_style: str = DEFAULT_CONTENT_STYLE


class BatchGenerateRequest(BaseModel):
    products: List[ProductInfo]
    hook_types: List[str] = ["curiosity"]
    formats: List[str] = ["short_form", "long_form"]
    content_style: str = DEFAULT_CONTENT_STYLE


# ── CSV Parsing ───────────────────────────────────────────────────────
CSV_COLUMNS = [
    "product_name", "niche", "key_features", "price", "affiliate_link",
    "keywords", "target_audience", "product_category", "competitors",
    "unique_selling_point", "discount_info", "coupon_code",
    "common_complaints", "common_praises", "who_not_for",
    "series_name", "price_comparison", "content_style",
]


def parse_csv_products(csv_text: str) -> List[dict]:
    reader = csv.DictReader(io.StringIO(csv_text))
    products = []
    for row in reader:
        norm = {}
        for k, v in row.items():
            if k is None:
                continue
            nk = k.strip().lower().replace(" ", "_")
            norm[nk] = (v or "").strip()

        if not norm.get("product_name"):
            continue

        product = {
            "product_name": norm.get("product_name", ""),
            "niche": norm.get("niche", "General"),
            "key_features": [f.strip() for f in norm.get("key_features", "").split(",") if f.strip()],
            "price": norm.get("price", "$49.99"),
            "affiliate_link": norm.get("affiliate_link", "[YOUR_AFFILIATE_LINK]"),
            "keywords": [k.strip() for k in norm.get("keywords", "").split(",") if k.strip()],
            "target_audience": norm.get("target_audience", "General consumers"),
            "product_category": norm.get("product_category", norm.get("niche", "General")),
            "competitors": [c.strip() for c in norm.get("competitors", "").split(",") if c.strip()],
            "unique_selling_point": norm.get("unique_selling_point", ""),
            "discount_info": norm.get("discount_info", ""),
            "coupon_code": norm.get("coupon_code", ""),
            # New fields
            "common_complaints": norm.get("common_complaints", ""),
            "common_praises": norm.get("common_praises", ""),
            "who_not_for": norm.get("who_not_for", ""),
            "series_name": norm.get("series_name", ""),
            "price_comparison": norm.get("price_comparison", ""),
            "content_style": norm.get("content_style", DEFAULT_CONTENT_STYLE),
        }
        products.append(product)
    return products


# ── Single Product Generation Worker ──────────────────────────────────
def _run_single_product(job_id: str, product: dict, product_dir: Path,
                        hook_types: list, formats: list,
                        content_style: str,
                        step_offset: int, total_steps: int):
    job = jobs[job_id]
    slug = slugify(product["product_name"])
    step = step_offset

    # Use product-level content_style if set, otherwise job-level
    effective_style = product.get("content_style") or content_style

    all_scripts = {}
    all_yt_packages = {}
    product_results = {"product_name": product["product_name"], "hooks": {}}

    # Phase 1: Scripts
    for hook_type in hook_types:
        hook_name = hook_type.replace("_", " ").title()
        job["current_step"] = f"[{product['product_name']}] Generating {hook_name} scripts..."
        job["progress"] = int(step / total_steps * 100)

        try:
            scripts = generate_selected_scripts(product, hook_type, formats, effective_style)
            all_scripts[hook_type] = scripts.get("scripts", {})

            fname = f"{slug}_{hook_type}_scripts.json"
            with open(str(product_dir / fname), "w") as f:
                json.dump(scripts, f, indent=2)

            if hook_type not in product_results["hooks"]:
                product_results["hooks"][hook_type] = {}
            product_results["hooks"][hook_type]["scripts"] = fname
        except Exception as e:
            job["errors"].append(f"[{product['product_name']}] Script ({hook_type}): {str(e)}")
            traceback.print_exc()

        step += len(formats)
        job["progress"] = int(step / total_steps * 100)

    # Phase 2: Videos
    for hook_type in hook_types:
        hook_name = hook_type.replace("_", " ").title()
        scripts_data = all_scripts.get(hook_type, {})

        for fmt in formats:
            if fmt not in scripts_data:
                step += 1
                continue

            fl = fmt_display(fmt)
            job["current_step"] = f"[{product['product_name']}] Rendering {hook_name} {fl} video..."
            job["progress"] = int(step / total_steps * 100)

            try:
                fname = f"{slug}_{hook_type}_{fmt_label(fmt)}.mp4"
                video_path = str(product_dir / fname)
                if fmt == "short_form":
                    render_short_form_video(
                        scripts_data[fmt], video_path,
                        product_name=product.get('product_name', ''),
                        price=product.get('price', ''),
                        series_name=product.get('series_name', ''),
                    )
                else:
                    render_long_form_video(
                        scripts_data[fmt], video_path,
                        product_name=product.get('product_name', ''),
                        price=product.get('price', ''),
                        series_name=product.get('series_name', ''),
                    )

                if hook_type not in product_results["hooks"]:
                    product_results["hooks"][hook_type] = {}
                if "videos" not in product_results["hooks"][hook_type]:
                    product_results["hooks"][hook_type]["videos"] = {}
                product_results["hooks"][hook_type]["videos"][fmt] = fname
            except Exception as e:
                job["errors"].append(f"[{product['product_name']}] Video ({hook_type} {fmt}): {str(e)}")
                traceback.print_exc()

            step += 1
            job["progress"] = int(step / total_steps * 100)

    # Phase 3: YouTube Assets
    for hook_type in hook_types:
        hook_name = hook_type.replace("_", " ").title()
        scripts_data = all_scripts.get(hook_type, {})
        all_yt_packages[hook_type] = {}

        for fmt in formats:
            if fmt not in scripts_data:
                step += 1
                continue

            fl = fmt_display(fmt)
            job["current_step"] = f"[{product['product_name']}] Generating {hook_name} {fl} YouTube package..."
            job["progress"] = int(step / total_steps * 100)

            try:
                assets = generate_youtube_assets(product, scripts_data[fmt], fmt)
                all_yt_packages[hook_type][fmt] = assets

                fname = f"{slug}_{hook_type}_{fmt_label(fmt)}_youtube_package.json"
                with open(str(product_dir / fname), "w") as f:
                    json.dump(assets, f, indent=2)

                if hook_type not in product_results["hooks"]:
                    product_results["hooks"][hook_type] = {}
                if "youtube_assets" not in product_results["hooks"][hook_type]:
                    product_results["hooks"][hook_type]["youtube_assets"] = {}
                product_results["hooks"][hook_type]["youtube_assets"][fmt] = assets
            except Exception as e:
                job["errors"].append(f"[{product['product_name']}] YT assets ({hook_type} {fmt}): {str(e)}")
                traceback.print_exc()

            step += 1
            job["progress"] = int(step / total_steps * 100)

    # Save combined posting package
    try:
        fname = f"{slug}_YOUTUBE_POSTING_PACKAGE.txt"
        save_posting_package_readable(all_yt_packages, product, str(product_dir / fname))
    except Exception:
        pass

    return product_results, step


# ── Generation Workers ────────────────────────────────────────────────
def _steps_per_product(hook_types, formats):
    n_hooks = len(hook_types)
    n_fmts = len(formats)
    return n_hooks * n_fmts * 3


def _run_generation(job_id: str):
    job = jobs[job_id]
    job_dir = OUTPUT_BASE / job_id
    product = job["product_info"]
    hook_types = job["hook_types"]
    formats = job["formats"]
    content_style = job.get("content_style", DEFAULT_CONTENT_STYLE)
    total_steps = _steps_per_product(hook_types, formats)

    try:
        product_dir = job_dir
        result, _ = _run_single_product(
            job_id, product, product_dir, hook_types, formats,
            content_style, 0, total_steps
        )
        job["results"] = result.get("hooks", {})
        job["status"] = "complete"
        job["progress"] = 100
        job["current_step"] = "Done!"
    except Exception as e:
        job["status"] = "error"
        job["current_step"] = f"Error: {str(e)}"
        job["errors"].append(str(e))
        traceback.print_exc()


def _run_batch_generation(job_id: str):
    job = jobs[job_id]
    job_dir = OUTPUT_BASE / job_id
    products = job["products"]
    hook_types = job["hook_types"]
    formats = job["formats"]
    content_style = job.get("content_style", DEFAULT_CONTENT_STYLE)

    steps_per = _steps_per_product(hook_types, formats)
    total_steps = steps_per * len(products)
    step_offset = 0

    try:
        all_product_results = []

        for i, product in enumerate(products):
            slug = slugify(product["product_name"])
            product_dir = job_dir / slug
            product_dir.mkdir(exist_ok=True)

            job["current_step"] = f"Product {i+1}/{len(products)}: {product['product_name']}"

            result, step_offset = _run_single_product(
                job_id, product, product_dir, hook_types, formats,
                content_style, step_offset, total_steps
            )
            all_product_results.append(result)

        job["product_results"] = all_product_results

        zip_path = job_dir / "all_products.zip"
        with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(str(job_dir)):
                for file in files:
                    if file == "all_products.zip":
                        continue
                    full = os.path.join(root, file)
                    arcname = os.path.relpath(full, str(job_dir))
                    zf.write(full, arcname)

        job["status"] = "complete"
        job["progress"] = 100
        job["current_step"] = f"Done! {len(products)} products processed."
    except Exception as e:
        job["status"] = "error"
        job["current_step"] = f"Error: {str(e)}"
        job["errors"].append(str(e))
        traceback.print_exc()


# ── Endpoints ─────────────────────────────────────────────────────────

@app.get("/api/providers")
def get_providers():
    return {
        "providers": llm_config.PROVIDER_PRESETS,
        "current": {
            "provider": llm_config.get_config().provider,
            "base_url": llm_config.get_config().base_url,
            "model": llm_config.get_config().model,
            "has_api_key": bool(llm_config.get_config().api_key),
        },
    }


@app.post("/api/config")
def set_llm_config(req: LLMConfigRequest):
    cfg = llm_config.set_config(
        provider=req.provider, api_key=req.api_key,
        base_url=req.base_url, model=req.model,
    )
    return {
        "status": "ok", "provider": cfg.provider,
        "base_url": cfg.base_url, "model": cfg.model,
        "has_api_key": bool(cfg.api_key),
    }


@app.get("/api/hooks")
def get_hooks():
    return {
        "hooks": HOOK_TYPES,
        "descriptions": HOOK_DESCRIPTIONS,
    }


@app.get("/api/content-styles")
def get_content_styles():
    return {
        "styles": CONTENT_STYLES,
        "default": DEFAULT_CONTENT_STYLE,
    }


@app.get("/api/csv-template")
def get_csv_template():
    header = ",".join(CSV_COLUMNS)
    example1 = 'SoundCore Space A40 Earbuds,Tech / Audio,"ANC, 50hr battery, Hi-Res Audio",$79.99,https://amzn.to/example123,"wireless earbuds, ANC earbuds",Tech-savvy 18-35,Wireless Earbuds,"AirPods Pro 2, Sony WF-1000XM5",Premium ANC at half the price,20% off this week,SOUND20,"Occasional ANC cutouts, case scratches easily","Battery life is incredible, ANC rivals $200 earbuds","Audiophiles wanting wired quality, very small ears",Worth It or Waste?,AirPods Pro 2 costs $249 for similar ANC performance,honest_review'
    example2 = 'Anker 737 Power Bank,Tech / Accessories,"140W output, 24000mAh, LED display",$89.99,https://amzn.to/example456,"power bank, portable charger",Remote workers and travelers,Power Banks,"Baseus 100W, Ugreen 145W",Fastest charging power bank under $100,,,Heavy at 1.3 lbs,Charges MacBook Pro to 50% in 30 min,People who want ultralight travel gear,Budget Challenge,Baseus 100W costs $69 but charges 30% slower,budget_challenge'
    content = header + "\n" + example1 + "\n" + example2 + "\n"
    return HTMLResponse(content=content, media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=product_template.csv"})


# ── Single product generation ─────────────────────────────────────────
@app.post("/api/generate")
def start_generation(req: GenerateRequest):
    job_id = str(uuid.uuid4())[:8]
    job_dir = OUTPUT_BASE / job_id
    job_dir.mkdir(exist_ok=True)

    product = req.product_info.dict()
    if not product.get("product_category"):
        product["product_category"] = product.get("niche", "General")
    # Apply content style from request if product doesn't have one
    if not product.get("content_style") or product["content_style"] == DEFAULT_CONTENT_STYLE:
        product["content_style"] = req.content_style

    jobs[job_id] = {
        "id": job_id, "mode": "single",
        "status": "running", "progress": 0, "current_step": "Starting...",
        "product_info": product, "hook_types": req.hook_types,
        "formats": req.formats, "content_style": req.content_style,
        "results": {}, "errors": [],
        "created_at": time.time(),
    }

    thread = threading.Thread(target=_run_generation, args=(job_id,), daemon=True)
    thread.start()
    return {"job_id": job_id, "status": "running", "mode": "single"}


# ── Batch CSV upload ──────────────────────────────────────────────────
@app.post("/api/batch-upload")
async def batch_upload(
    file: UploadFile = File(...),
    hook_types: str = Form("curiosity"),
    formats: str = Form("short_form,long_form"),
    content_style: str = Form(DEFAULT_CONTENT_STYLE),
):
    content = await file.read()
    try:
        csv_text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        csv_text = content.decode("latin-1")

    products = parse_csv_products(csv_text)
    if not products:
        raise HTTPException(status_code=400, detail="No valid products found in CSV.")

    hook_list = [h.strip() for h in hook_types.split(",") if h.strip()]
    fmt_list = [f.strip() for f in formats.split(",") if f.strip()]

    job_id = str(uuid.uuid4())[:8]
    job_dir = OUTPUT_BASE / job_id
    job_dir.mkdir(exist_ok=True)

    jobs[job_id] = {
        "id": job_id, "mode": "batch",
        "status": "running", "progress": 0,
        "current_step": f"Starting batch: {len(products)} products...",
        "products": products, "hook_types": hook_list,
        "formats": fmt_list, "content_style": content_style,
        "product_results": [],
        "errors": [], "created_at": time.time(),
    }

    thread = threading.Thread(target=_run_batch_generation, args=(job_id,), daemon=True)
    thread.start()

    return {
        "job_id": job_id, "status": "running", "mode": "batch",
        "product_count": len(products),
        "products_found": [p["product_name"] for p in products],
    }


# ── Batch JSON upload ─────────────────────────────────────────────────
@app.post("/api/batch-generate")
def batch_generate(req: BatchGenerateRequest):
    products = [p.dict() for p in req.products]
    for p in products:
        if not p.get("product_category"):
            p["product_category"] = p.get("niche", "General")

    job_id = str(uuid.uuid4())[:8]
    job_dir = OUTPUT_BASE / job_id
    job_dir.mkdir(exist_ok=True)

    jobs[job_id] = {
        "id": job_id, "mode": "batch",
        "status": "running", "progress": 0,
        "current_step": f"Starting batch: {len(products)} products...",
        "products": products, "hook_types": req.hook_types,
        "formats": req.formats, "content_style": req.content_style,
        "product_results": [],
        "errors": [], "created_at": time.time(),
    }

    thread = threading.Thread(target=_run_batch_generation, args=(job_id,), daemon=True)
    thread.start()

    return {
        "job_id": job_id, "status": "running", "mode": "batch",
        "product_count": len(products),
        "products_found": [p["product_name"] for p in products],
    }


# ── Status & Results ──────────────────────────────────────────────────
@app.get("/api/status/{job_id}")
def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[job_id]
    resp = {
        "id": job["id"], "mode": job.get("mode", "single"),
        "status": job["status"], "progress": job["progress"],
        "current_step": job["current_step"], "errors": job["errors"],
    }
    if job.get("mode") == "batch":
        resp["product_count"] = len(job.get("products", []))
    return resp


@app.get("/api/results/{job_id}")
def get_results(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    job = jobs[job_id]
    resp = {
        "id": job["id"], "mode": job.get("mode", "single"),
        "status": job["status"], "progress": job["progress"],
        "current_step": job["current_step"], "errors": job["errors"],
    }
    if job.get("mode") == "batch":
        resp["product_results"] = job.get("product_results", [])
        resp["products"] = job.get("products", [])
        resp["hook_types"] = job.get("hook_types", [])
        resp["formats"] = job.get("formats", [])
    else:
        resp["product_info"] = job.get("product_info", {})
        resp["hook_types"] = job.get("hook_types", [])
        resp["formats"] = job.get("formats", [])
        resp["results"] = job.get("results", {})
    return resp


@app.get("/api/download/{job_id}/{path:path}")
def download_file(job_id: str, path: str):
    file_path = OUTPUT_BASE / job_id / path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    media_type = "video/mp4" if path.endswith(".mp4") else "application/json"
    if path.endswith(".txt"):
        media_type = "text/plain"
    if path.endswith(".zip"):
        media_type = "application/zip"
    return FileResponse(str(file_path), filename=file_path.name, media_type=media_type)


@app.get("/api/files/{job_id}")
def list_files(job_id: str):
    job_dir = OUTPUT_BASE / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="Job not found")
    files = []
    for root, dirs, filenames in os.walk(str(job_dir)):
        for fn in filenames:
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, str(job_dir))
            files.append({
                "path": rel,
                "name": fn,
                "size": os.path.getsize(full),
                "type": "video" if fn.endswith(".mp4") else "text" if fn.endswith(".txt") else "json" if fn.endswith(".json") else "zip" if fn.endswith(".zip") else "other",
            })
    return {"job_id": job_id, "files": files}


# ── Serve Frontend ────────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

if (FRONTEND_DIR / "index.html").exists():
    assets_dir = FRONTEND_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="static_assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        file_path = FRONTEND_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(FRONTEND_DIR / "index.html"))
else:
    @app.get("/")
    def root():
        return {"message": "ShadowCast API v4.0 — by Unloved Productions | Forged in Passion"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
