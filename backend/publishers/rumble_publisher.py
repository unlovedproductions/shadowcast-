"""Rumble browser publisher via Playwright."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from credentials_store import CredentialsStore

RUMBLE_UPLOAD_URL = "https://rumble.com/upload.php"
RUMBLE_LOGIN_URL = "https://rumble.com/login"

# Prefer stable name/id selectors; fall back to placeholders / roles.
_TITLE_SELECTORS = (
    'input[name="title"]',
    "#title",
    'input[placeholder*="Title" i]',
    'input[aria-label*="title" i]',
)
_DESC_SELECTORS = (
    'textarea[name="description"]',
    "#description",
    'textarea[placeholder*="Description" i]',
    'textarea[aria-label*="description" i]',
)
_TAG_SELECTORS = (
    'input[name="tags"]',
    "#tags",
    'input[placeholder*="tag" i]',
    'input[aria-label*="tag" i]',
)
_CATEGORY_SELECTORS = (
    'select[name="category"]',
    "#category",
    'select[aria-label*="categor" i]',
)
_FILE_SELECTORS = (
    'input[type="file"][accept*="video"]',
    'input[type="file"]',
)
_SUBMIT_SELECTORS = (
    'button[type="submit"]',
    'input[type="submit"]',
    'button:has-text("Publish")',
    'button:has-text("Upload")',
    'button:has-text("Submit")',
)
_LOGIN_USER_SELECTORS = (
    'input[name="username"]',
    'input[type="email"]',
    "#username",
    'input[autocomplete="username"]',
)
_LOGIN_PASS_SELECTORS = (
    'input[name="password"]',
    'input[type="password"]',
    "#password",
)


def _first_locator(page, selectors: tuple[str, ...]):
    for sel in selectors:
        loc = page.locator(sel)
        try:
            if loc.count() > 0:
                return loc.first
        except Exception:
            continue
    return None


def _fill_first(page, selectors: tuple[str, ...], value: str) -> bool:
    loc = _first_locator(page, selectors)
    if loc is None:
        return False
    loc.fill(value)
    return True


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
                "note": "Dry-run only — no browser upload. Live publish needs connected Rumble cookies.",
            }

        creds = self.store.load("rumble")
        if not creds or not creds.get("cookies"):
            raise ValueError("Rumble not connected — complete browser login first")

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright not installed — run: pip install playwright && playwright install chromium"
            ) from exc

        cookies = creds["cookies"]
        title = payload.get("title", "Video")
        description = payload.get("description", "")
        tags = payload.get("tags", [])
        category = payload.get("category", "Entertainment")
        video_file = str(Path(video_path).resolve())
        if not Path(video_file).is_file():
            raise FileNotFoundError(f"Rumble video missing: {video_file}")

        browser = None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                context.add_cookies(cookies)
                page = context.new_page()
                page.goto(RUMBLE_UPLOAD_URL, wait_until="domcontentloaded", timeout=90000)
                page.wait_for_timeout(1500)

                if "login" in page.url.lower():
                    raise RuntimeError("Rumble session expired — reconnect via browser login")

                if not _fill_first(page, _TITLE_SELECTORS, title):
                    raise RuntimeError("Rumble upload: title field not found (selectors stale)")
                if not _fill_first(page, _DESC_SELECTORS, description):
                    # Description optional on some layouts
                    pass

                if tags:
                    tags_str = ", ".join(str(t) for t in tags)
                    _fill_first(page, _TAG_SELECTORS, tags_str)

                cat = _first_locator(page, _CATEGORY_SELECTORS)
                if cat is not None:
                    try:
                        cat.select_option(label=category)
                    except Exception:
                        try:
                            cat.select_option(value=category)
                        except Exception:
                            pass

                file_input = _first_locator(page, _FILE_SELECTORS)
                if file_input is None:
                    raise RuntimeError("Rumble upload: file input not found (selectors stale)")
                file_input.set_input_files(video_file)

                # Only toggle obvious terms/consent boxes — never spray-check every input.
                for sel in (
                    'input[type="checkbox"][name*="term" i]',
                    'input[type="checkbox"][name*="agree" i]',
                    'input[type="checkbox"][id*="term" i]',
                    'input[type="checkbox"][id*="agree" i]',
                ):
                    for box in page.locator(sel).all():
                        try:
                            if not box.is_checked():
                                box.check()
                        except Exception:
                            pass

                submit = _first_locator(page, _SUBMIT_SELECTORS)
                if submit is None:
                    raise RuntimeError("Rumble upload: submit button not found (selectors stale)")
                submit.click()
                try:
                    page.wait_for_load_state("networkidle", timeout=120000)
                except Exception:
                    page.wait_for_timeout(5000)

                url = page.url
                if "login" in url.lower():
                    raise RuntimeError("Rumble session expired — reconnect via browser login")
                body_text = page.locator("body").inner_text().lower()
                if any(token in body_text for token in ("upload failed", "error uploading", "invalid file")):
                    raise RuntimeError("Rumble upload page reported an error after submit")

                post_id = url.rstrip("/").split("/")[-1] if "rumble.com" in url else ""
                if not post_id or post_id in ("upload.php", "upload"):
                    raise RuntimeError(
                        "Rumble publish did not return a video URL — check selectors / session"
                    )

                new_cookies = context.cookies()
                self.save_session_from_cookies(new_cookies)
                browser.close()
                browser = None
        finally:
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass

        return {"status": "success", "platform": "rumble", "post_id": post_id, "url": url}

    def login_and_capture_session(self, username: str, password: str) -> list[dict[str, Any]]:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(RUMBLE_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
            if not _fill_first(page, _LOGIN_USER_SELECTORS, username):
                raise RuntimeError("Rumble login: username field not found")
            if not _fill_first(page, _LOGIN_PASS_SELECTORS, password):
                raise RuntimeError("Rumble login: password field not found")
            submit = _first_locator(
                page,
                ('button[type="submit"]', 'input[type="submit"]', 'button:has-text("Log")'),
            )
            if submit is None:
                raise RuntimeError("Rumble login: submit button not found")
            submit.click()
            page.wait_for_load_state("networkidle", timeout=60000)
            cookies = page.context.cookies()
            browser.close()
        self.save_session_from_cookies(cookies)
        return cookies
