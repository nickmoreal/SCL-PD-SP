import os
import time
import random
import tempfile
from typing import Optional, Tuple
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
from playwright.sync_api import sync_playwright, BrowserContext, Page

try:
    from playwright_stealth import stealth_sync
except ImportError:
    stealth_sync = None


class PageFetcher:
    """
    Cloudflare Bypass Engine for GitHub Actions & Cloud:
    - Persistent user profile keeps cf_clearance cookies active across all URLs.
    - Full stealth evasion masking headless automation markers.
    - Rapid tab lifecycle with zero session carry-over locks.
    """

    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._user_data_dir = os.path.join(tempfile.gettempdir(), "scheels_browser_profile")
        os.makedirs(self._user_data_dir, exist_ok=True)

    def _ensure_context(self):
        if self._playwright is None:
            self._playwright = sync_playwright().start()

        if self._context is None:
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-infobars",
                "--window-size=1920,1080",
                "--lang=en-US,en"
            ]
            
            kwargs = {
                "user_data_dir": self._user_data_dir,
                "headless": True,
                "viewport": {"width": 1920, "height": 1080},
                "user_agent": self.user_agent,
                "locale": "en-US",
                "timezone_id": "America/Chicago",
                "args": launch_args,
                "ignore_default_args": ["--enable-automation"]
            }
            if self.proxy:
                kwargs["proxy"] = {"server": self.proxy}

            self._context = self._playwright.chromium.launch_persistent_context(**kwargs)

    def fetch_browser_stealth(self, url: str, timeout_sec: int = 25) -> Tuple[Optional[str], str]:
        page = None
        try:
            self._ensure_context()
            page = self._context.new_page()

            # Apply playwright-stealth if installed
            if stealth_sync:
                stealth_sync(page)

            # Block heavy tracking ads only
            def ad_filter(route):
                u = route.request.url.lower()
                if any(ad in u for ad in ["google-analytics", "doubleclick", "clarip", "klaviyo", "tiktok", "snapchat", "pinterest", "facebook"]):
                    route.abort()
                else:
                    route.continue_()

            page.route("**/*", ad_filter)

            # Navigate to product URL
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_sec * 1000)

            # Wait for legit product page or title
            for _ in range(12):
                title = page.title()
                if title and not any(k in title.lower() for k in ["just a moment", "attention required", "cloudflare", "challenge"]):
                    break
                time.sleep(0.8)

            time.sleep(1.0)
            content = page.content()

            if "Just a moment..." in content and "Challenge" in content:
                return None, "Blocked by Challenge"

            return content, "Stealth Persistent Context"
        except Exception as e:
            return None, f"Browser Error: {str(e)}"
        finally:
            if page and not page.is_closed():
                try:
                    page.close()
                except Exception:
                    pass

    def fetch(self, url: str) -> Tuple[Optional[str], str]:
        # Pacing between requests
        time.sleep(random.uniform(0.8, 1.5))

        html, method = self.fetch_browser_stealth(url)
        if html and "Just a moment..." not in html:
            return html, method

        # Retry once if challenge appeared
        time.sleep(2.0)
        html, method = self.fetch_browser_stealth(url, timeout_sec=30)
        if html and "Just a moment..." not in html:
            return html, method

        return None, "Failed after retry"

    def close(self):
        try:
            if self._context:
                self._context.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
