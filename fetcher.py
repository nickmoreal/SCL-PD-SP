import os
import time
import random
import tempfile
from typing import Optional, Tuple
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, BrowserContext, Page

try:
    from playwright_stealth import stealth_sync
except ImportError:
    stealth_sync = None


class PageFetcher:
    """
    Cloudflare Bypass Engine for GitHub Actions & Linux Cloud:
    - Runs in headless mode compatible with GitHub Actions Ubuntu runners.
    - Uses persistent browser context for cookie and session clearance.
    - Masks automation signals with anti-bot evasion scripts.
    """

    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._user_data_dir = os.path.join(tempfile.gettempdir(), "scheels_cloud_profile")
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

    def fetch(self, url: str) -> Tuple[Optional[str], str]:
        """Fetches product HTML directly through the stealth cloud browser context."""
        page = None
        try:
            self._ensure_context()
            page = self._context.new_page()

            # Apply stealth plugin
            if stealth_sync:
                try:
                    stealth_sync(page)
                except Exception:
                    pass

            # Block heavy tracking ads only to speed up loading
            def ad_filter(route):
                u = route.request.url.lower()
                if any(ad in u for ad in ["google-analytics", "doubleclick", "clarip", "klaviyo", "tiktok", "snapchat", "pinterest", "facebook"]):
                    route.abort()
                else:
                    route.continue_()

            page.route("**/*", ad_filter)

            # Navigate to Scheels URL
            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Wait for content to render / Turnstile to complete
            for _ in range(12):
                title = page.title()
                if title and not any(k in title.lower() for k in ["just a moment", "attention required", "cloudflare", "challenge"]):
                    break
                time.sleep(1.0)

            time.sleep(1.5)
            content = page.content()

            if "Just a moment..." in content and "Challenge" in content:
                # Give an extra wait for Turnstile
                time.sleep(3.0)
                content = page.content()
                if "Just a moment..." in content and "Challenge" in content:
                    return None, "Blocked by Cloudflare Challenge"

            return content, "Headless Stealth Browser"
        except Exception as e:
            return None, f"Browser Fetch Error: {str(e)}"
        finally:
            if page and not page.is_closed():
                try:
                    page.close()
                except Exception:
                    pass

    def close(self):
        try:
            if self._context:
                self._context.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
