"""Rumble browser publisher via Playwright."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from credentials_store import CredentialsStore

RUMBLE_UPLOAD_URL = "https://rumble.com/upload.php"
RUMBLE_LOGIN_URL = "https://rumble.com/login"


class RumblePublisher:
    def __init__(self, store: CredentialsStore | None = None):
        self.store = store or CredentialsStore()

    def save_session_from_cookies(self, cookies: list[dict[str, Any]]) -> None:
        self.store.save("rumble", {"cookies": cookies, "status": "connected"})

    def publish(
        self,
        video_path: str,
        payload: dict[str, Any],
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if dry_run:
            return {
                "status": "success",
                "platform": "rumble",
                "post_id": "dry_run_rumble",
                "url": "https://rumble.com/c/dry_run",
                "dry_run": True,
                "title": payload.get("title"),
            }

        creds = self.store.load("rumble")
        if not creds or not creds.get("cookies"):
            raise ValueError("Rumble not connected — complete browser login first")

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright not installed — run: pip install playwright && playwright install chromium") from exc

        cookies = creds["cookies"]
        title = payload.get("title", "Video")
        description = payload.get("description", "")
        tags = payload.get("tags", [])
        category = payload.get("category", "Entertainment")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            context.add_cookies(cookies)
            page = context.new_page()
            page.goto(RUMBLE_UPLOAD_URL, wait_until="networkidle")

            page.fill('input[name="title"], #title, [placeholder*="Title"]', title)
            page.fill('textarea[name="description"], #description, [placeholder*="Description"]', description)

            if tags:
                tags_str = ", ".join(tags)
                tag_sel = 'input[name="tags"], #tags, [placeholder*="tag" i]'
                if page.locator(tag_sel).count():
                    page.fill(tag_sel, tags_str)

            cat_sel = 'select[name="category"], #category'
            if page.locator(cat_sel).count():
                try:
                    page.select_option(cat_sel, label=category)
                except Exception:
                    pass

            file_input = page.locator('input[type="file"]')
            file_input.set_input_files(str(Path(video_path).resolve()))

            for checkbox in page.locator('input[type="checkbox"]').all():
                try:
                    if not checkbox.is_checked():
                        checkbox.check()
                except Exception:
                    pass

            submit = page.locator('button[type="submit"], input[type="submit"], button:has-text("Publish"), button:has-text("Upload")')
            if submit.count():
                submit.first.click()
                page.wait_for_load_state("networkidle", timeout=120000)

            url = page.url
            post_id = url.rstrip("/").split("/")[-1] if "rumble.com" in url else "rumble_post"
            new_cookies = context.cookies()
            self.save_session_from_cookies(new_cookies)
            browser.close()

        return {"status": "success", "platform": "rumble", "post_id": post_id, "url": url}

    def login_and_capture_session(self, username: str, password: str) -> list[dict[str, Any]]:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(RUMBLE_LOGIN_URL, wait_until="networkidle")
            page.fill('input[name="username"], input[type="email"], #username', username)
            page.fill('input[name="password"], input[type="password"], #password', password)
            page.locator('button[type="submit"], input[type="submit"]').first.click()
            page.wait_for_load_state("networkidle", timeout=60000)
            cookies = page.context.cookies()
            browser.close()
        self.save_session_from_cookies(cookies)
        return cookies
