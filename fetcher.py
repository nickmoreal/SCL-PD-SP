import os
import time
import random
from typing import Optional, Tuple
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Browser


class PageFetcher:
    """
    High-Reliability Cloudflare Bypass Engine for GitHub Actions & Cloud:
    - Reuses a single Chromium browser instance (fast startup).
    - Uses a fresh, isolated BrowserContext per request (prevents Cloudflare Turnstile session lock).
    - Headless mode with Ubuntu Linux container flags.
    """

    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        self._playwright = None
        self._browser: Optional[Browser] = None

    def _ensure_browser(self):
        if self._playwright is None:
            self._playwright = sync_playwright().start()

        if self._browser is None or not self._browser.is_connected():
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-infobars",
                "--window-size=1920,1080"
            ]
            
            kwargs = {
                "headless": True,
                "args": launch_args
            }
            if self.proxy:
                kwargs["proxy"] = {"server": self.proxy}

            self._browser = self._playwright.chromium.launch(**kwargs)

    def fetch(self, url: str, timeout_sec: int = 30) -> Tuple[Optional[str], str]:
        """Fetches product HTML in an isolated context to guarantee zero Cloudflare lock carryover."""
        ctx = None
        try:
            self._ensure_browser()
            
            # Fresh isolated context for every URL
            ctx = self._browser.new_context(
                user_agent=self.user_agent,
                viewport={"width": 1920, "height": 1080},
                locale="en-US"
            )
            
            page = ctx.new_page()

            # Block heavy tracking ads only to speed up loading
            def ad_filter(route):
                u = route.request.url.lower()
                if any(ad in u for ad in ["google-analytics", "doubleclick", "clarip", "klaviyo", "tiktok", "snapchat", "pinterest", "facebook"]):
                    route.abort()
                else:
                    route.continue_()

            page.route("**/*", ad_filter)

            # Navigate to Scheels URL
            page.goto(url, wait_until="domcontentloaded", timeout=20000)

            # Fast title/challenge resolution check
            for _ in range(12):
                title = page.title()
                if title and not any(k in title.lower() for k in ["just a moment", "attention required", "cloudflare", "challenge"]):
                    break
                time.sleep(0.25)

            content = page.content()

            return content, "Isolated Headless Context"
        except Exception as e:
            return None, f"Browser Fetch Error: {str(e)}"
        finally:
            if ctx:
                try:
                    ctx.close()
                except Exception:
                    pass
            # Rapid natural jitter between requests
            time.sleep(0.25)

    def close(self):
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
