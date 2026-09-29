import os
import time
from typing import Optional, Tuple
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page


class PageFetcher:
    """
    High-Performance Page Fetcher:
    - Reuses a single persistent Playwright Chromium browser instance across thousands of URLs.
    - Blocks images, fonts, media, and third-party trackers for lightning-fast page loading.
    - Fast TLS HTTP fallback.
    """

    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    def _ensure_browser(self):
        """Initializes and keeps a single browser context open across all URLs."""
        if self._page is not None and not self._page.is_closed():
            return

        if self._playwright is None:
            self._playwright = sync_playwright().start()

        launch_kwargs = {
            "headless": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-extensions",
                "--disable-images",
                "--blink-settings=imagesEnabled=false"
            ]
        }
        if self.proxy:
            launch_kwargs["proxy"] = {"server": self.proxy}

        self._browser = self._playwright.chromium.launch(**launch_kwargs)
        self._context = self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent=self.headers["User-Agent"]
        )

        self._page = self._context.new_page()

        # Intercept and block heavy media, fonts, images, and marketing trackers
        def route_filter(route):
            req = route.request
            rtype = req.resource_type
            url_lower = req.url.lower()

            if rtype in ["image", "media", "font"]:
                route.abort()
            elif any(tracker in url_lower for tracker in [
                "google-analytics", "doubleclick", "clarip", "klaviyo",
                "tiktok", "snapchat", "pinterest", "facebook", "syndi",
                "turnto", "snowplow", "adroll", "rakuten", "gladly"
            ]):
                route.abort()
            else:
                route.continue_()

        self._page.route("**/*", route_filter)

    def fetch_browser_fast(self, url: str, timeout_sec: int = 20) -> Tuple[Optional[str], str]:
        """Fetches page HTML using the persistent, reusable browser with media blocking."""
        try:
            self._ensure_browser()
            self._page.goto(url, wait_until="domcontentloaded", timeout=timeout_sec * 1000)

            # Wait briefly for title or product schema
            for _ in range(8):
                title = self._page.title()
                if title and "Just a moment" not in title and len(title) > 0:
                    break
                time.sleep(0.3)

            time.sleep(0.5)
            content = self._page.content()
            return content, "Reusable Stealth Browser"
        except Exception as e:
            # If current page errored or crashed, reset page
            try:
                if self._page:
                    self._page.close()
                self._page = self._context.new_page() if self._context else None
            except Exception:
                pass
            return None, f"Browser Fetch Error: {str(e)}"

    def fetch_fast(self, url: str) -> Tuple[Optional[str], int, str]:
        """Fast HTTP request with TLS fingerprint impersonation."""
        try:
            proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
            resp = cffi_requests.get(
                url,
                impersonate="chrome124",
                headers=self.headers,
                proxies=proxies,
                timeout=10
            )
            if resp.status_code == 200 and "Just a moment..." not in resp.text:
                return resp.text, 200, "Fast TLS HTTP"
            return resp.text, resp.status_code, f"HTTP {resp.status_code} (Challenge)"
        except Exception as e:
            return None, 0, f"Error: {str(e)}"

    def fetch_stealth_browser(self, url: str, timeout_sec: int = 15) -> Tuple[Optional[str], str]:
        """Alias to high-speed reusable browser."""
        return self.fetch_browser_fast(url, timeout_sec)

    def close(self):
        """Closes the browser cleanly when all scraping is finished."""
        try:
            if self._page and not self._page.is_closed():
                self._page.close()
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
