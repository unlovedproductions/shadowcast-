#!/usr/bin/env python3
"""Run ShadowCast eval fixtures against LLM generators or validators."""

import argparse
import json
import sys
import time
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
BACKEND = EVAL_DIR.parent
sys.path.insert(0, str(BACKEND))

from content_styles import normalize_content_style
from output_validators import validate_script_output, validate_youtube_assets

FIXTURES = EVAL_DIR / "fixtures"
PRODUCTS = FIXTURES / "products"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_product(filename: str) -> dict:
    return _load_json(PRODUCTS / filename)


def _load_mock_script(key: str) -> dict:
    return _load_json(FIXTURES / "mock_scripts.json")[key]


def _run_script_case(case: dict, live: bool) -> dict:
    product = _load_product(case["product"])
    content_style = normalize_content_style(case["content_style"])
    hook_type = case["hook_type"]
    fmt = case["format"]
    product = {**product, "content_style": content_style}

    result = {
        "id": case["id"],
        "type": "script",
        "format": fmt,
        "content_style": content_style,
        "passed": False,
        "errors": [],
        "live": live,
    }

    if live:
        from script_generator import generate_long_form_script, generate_short_form_script
        from script_postprocessor import enrich_script
        try:
            if fmt == "short_form":
                output = generate_short_form_script(product, hook_type, content_style)
            else:
                output = generate_long_form_script(product, hook_type, content_style)
            output = enrich_script(output, product, content_style)
        except Exception as exc:
            result["errors"] = [f"LLM call failed: {exc}"]
            return result
    else:
        output = _mock_script_output(fmt, content_style, hook_type, product)

    ok, errors = validate_script_output(output, content_style, fmt)
    result["passed"] = ok
    result["errors"] = errors
    if not live:
        result["note"] = "dry-run with synthetic output"
    return result


def _mock_script_output(fmt: str, content_style: str, hook_type: str, product: dict) -> dict:
    base = {
        "hook_type": hook_type,
        "content_style": content_style,
        "format": fmt,
        "title_suggestion": f"{product['product_name']} Review",
    }
    if fmt == "short_form":
        segs = [
            {"segment_id": 1, "text": "Hook line", "text_style": "headline_bold", "duration": 2},
            {"segment_id": 2, "text": "Main benefit", "text_style": "pros", "duration": 2},
            {"segment_id": 3, "text": "Check the link", "text_style": "cta_button", "duration": 2},
        ]
        if content_style == "honest_review":
            segs.insert(2, {"segment_id": 4, "text": "One limitation", "text_style": "cons", "duration": 2})
        if content_style == "elimination":
            segs.insert(1, {"segment_id": 5, "text": "Reject option", "text_style": "elimination", "duration": 2, "layout": "winner_reveal"})
        if content_style == "vs_battle":
            segs.insert(1, {"segment_id": 6, "text": "A vs B", "text_style": "comparison", "duration": 2, "layout": "vs_split"})
            segs.insert(2, {"segment_id": 7, "text": "Score", "text_style": "scorecard", "duration": 2, "layout": "scorecard"})
        if content_style == "budget_challenge":
            segs.insert(1, {"segment_id": 8, "text": "Under $50", "text_style": "stat_number", "duration": 2, "layout": "price_compare"})
        if content_style == "worth_it_or_waste":
            segs.insert(2, {"segment_id": 9, "text": "Worth it", "text_style": "verdict", "duration": 2})
        base["segments"] = segs
    else:
        chapters = [
            {"chapter_name": "Intro", "segments": [{"segment_id": 1, "text": "Hook", "text_style": "headline_bold", "duration": 3}]},
            {"chapter_name": "Body", "segments": [{"segment_id": 2, "text": "Detail", "text_style": "subtitle", "duration": 3}]},
            {"chapter_name": "Outro", "segments": [{"segment_id": 3, "text": "CTA", "text_style": "cta_button", "duration": 3}]},
        ]
        if content_style == "honest_review":
            chapters[1]["segments"].append({"segment_id": 4, "text": "Limitation", "text_style": "cons", "duration": 3})
        if content_style == "elimination":
            chapters[1]["segments"].append({"segment_id": 5, "text": "Cut", "text_style": "elimination", "duration": 3, "layout": "winner_reveal"})
        if content_style == "vs_battle":
            chapters[1]["segments"].append({"segment_id": 6, "text": "Vs", "text_style": "comparison", "duration": 3, "layout": "vs_split"})
        if content_style == "budget_challenge":
            chapters[1]["segments"].append({"segment_id": 7, "text": "Prices", "text_style": "stat_number", "duration": 3, "layout": "price_compare"})
        if content_style == "worth_it_or_waste":
            chapters[2]["segments"].insert(0, {"segment_id": 8, "text": "Verdict", "text_style": "verdict", "duration": 3})
        base["chapters"] = chapters
    return base


def _run_youtube_case(case: dict, live: bool) -> dict:
    product = _load_product(case["product"])
    script = _load_mock_script(case["mock_script"])
    fmt = case["format"]

    result = {
        "id": case["id"],
        "type": "youtube_assets",
        "format": fmt,
        "passed": False,
        "errors": [],
        "live": live,
    }

    if live:
        from youtube_assets_generator import generate_youtube_assets
        try:
            output = generate_youtube_assets(product, script, fmt)
        except Exception as exc:
            result["errors"] = [f"LLM call failed: {exc}"]
            return result
    else:
        link = product.get("affiliate_link", "")
        output = {
            "seo_title": f"{product['product_name']} Honest Review",
            "tags": ["review", "buyer guide", "pros cons", "worth it", "budget"],
            "pinned_comment": f"Honest take after research. Link: {link} — worth it for commuters?",
            "seo_description": "Pros and cons overview for shoppers.",
        }

    ok, errors = validate_youtube_assets(output, product.get("affiliate_link", ""))
    result["passed"] = ok
    result["errors"] = errors
    if not live:
        result["note"] = "dry-run with synthetic output"
    return result


def run_eval(cases: list, live: bool, filter_ids: set | None = None) -> dict:
    results = []
    for case in cases:
        if filter_ids and case["id"] not in filter_ids:
            continue
        if case["type"] == "script":
            results.append(_run_script_case(case, live))
        elif case["type"] == "youtube_assets":
            results.append(_run_youtube_case(case, live))
        else:
            results.append({"id": case.get("id", "?"), "passed": False, "errors": [f"unknown type {case['type']}"]})
    passed = sum(1 for r in results if r.get("passed"))
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "live": live,
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }


def _merge_into_live_baseline(report: dict, output_path: Path, all_case_ids: list[str]) -> dict:
    """Merge filtered live runs into an existing baseline without dropping other cases."""
    existing_map: dict[str, dict] = {}
    if output_path.exists():
        prior = _load_json(output_path)
        for row in prior.get("results", []):
            if isinstance(row, dict) and row.get("id"):
                existing_map[row["id"]] = row

    for row in report.get("results", []):
        if isinstance(row, dict) and row.get("id"):
            existing_map[row["id"]] = row

    merged_results: list[dict] = []
    for case_id in all_case_ids:
        if case_id in existing_map:
            merged_results.append(existing_map[case_id])
        else:
            merged_results.append(
                {
                    "id": case_id,
                    "passed": None,
                    "pending_live": True,
                    "note": "Run with LLM_EVAL=1 and --live to populate",
                }
            )

    passed = sum(1 for row in merged_results if row.get("passed") is True)
    failed = sum(1 for row in merged_results if row.get("passed") is False)
    pending = sum(1 for row in merged_results if row.get("pending_live"))
    return {
        "timestamp": report["timestamp"],
        "live": report["live"],
        "required_pass_ids": all_case_ids,
        "total": len(all_case_ids),
        "passed": passed,
        "failed": failed,
        "pending_live": pending,
        "results": merged_results,
    }


def compare_results(current: dict, baseline: dict) -> tuple[bool, list[str]]:
    issues = []
    baseline_map = {r["id"]: r for r in baseline.get("results", [])}
    for r in current.get("results", []):
        cid = r["id"]
        if cid not in baseline_map:
            continue
        if baseline_map[cid].get("passed") and not r.get("passed"):
            issues.append(f"{cid}: regression (was pass, now fail: {r.get('errors')})")
    return len(issues) == 0, issues


def main():
    parser = argparse.ArgumentParser(description="ShadowCast prompt eval runner")
    parser.add_argument("--fixture", default=str(FIXTURES / "eval_set.json"))
    parser.add_argument("--output", "-o", help="Write results JSON")
    parser.add_argument("--live", action="store_true", help="Call LLM (requires provider)")
    parser.add_argument("--filter", help="Comma-separated case IDs")
    parser.add_argument("--compare", help="Baseline results JSON for no-regression check")
    args = parser.parse_args()

    spec = _load_json(Path(args.fixture))
    cases = spec["cases"]
    filter_ids = set(x.strip() for x in args.filter.split(",")) if args.filter else None

    report = run_eval(cases, live=args.live, filter_ids=filter_ids)

    if args.compare:
        baseline = _load_json(Path(args.compare))
        ok, issues = compare_results(report, baseline)
        report["compare_ok"] = ok
        report["regressions"] = issues
        if not ok:
            print("REGRESSION DETECTED:", file=sys.stderr)
            for issue in issues:
                print(f"  - {issue}", file=sys.stderr)

    summary = f"{report['passed']}/{report['total']} passed (live={report['live']})"
    print(summary)

    if args.output:
        output_path = Path(args.output)
        all_case_ids = [case["id"] for case in cases]
        if output_path.name == "eval_live_baseline.json" or (filter_ids and output_path.exists()):
            report = _merge_into_live_baseline(report, output_path, all_case_ids)
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Wrote {args.output}")

    if args.compare and not report.get("compare_ok", True):
        sys.exit(1)
    if report["failed"] > 0 and args.live:
        sys.exit(1)


if __name__ == "__main__":
    main()
