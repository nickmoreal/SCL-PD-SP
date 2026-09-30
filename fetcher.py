import os
import time
import random
from typing import Optional, Tuple
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page


class PageFetcher:
    """
    Cloudflare-Resistant Stealth Page Fetcher for GitHub Actions & Cloud Runners:
    - Persistent Playwright context with real browser fingerprinting.
    - Cloudflare Turnstile bypass handling with dynamic challenge waits.
    - Automatic curl_cffi TLS impersonation fallback.
    """

    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        self.headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "sec-ch-ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        }
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    def _ensure_browser(self):
        """Initializes stealth browser context with anti-detection scripts."""
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
                "--disable-infobars",
                "--window-size=1920,1080"
            ]
        }
        if self.proxy:
            launch_kwargs["proxy"] = {"server": self.proxy}

        self._browser = self._playwright.chromium.launch(**launch_kwargs)
        self._context = self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=self.user_agent,
            locale="en-US",
            timezone_id="America/Chicago"
        )

        # Inject stealth scripts to hide automation
        self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)

        self._page = self._context.new_page()

    def fetch_browser_fast(self, url: str, timeout_sec: int = 25) -> Tuple[Optional[str], str]:
        """Navigates to URL and waits through Cloudflare challenges automatically."""
        try:
            self._ensure_browser()
            self._page.goto(url, wait_until="domcontentloaded", timeout=timeout_sec * 1000)

            # Check for Cloudflare Turnstile / Challenge
            for i in range(12):
                title = self._page.title()
                # If page is legitimate and not a challenge page
                if title and "Just a moment" not in title and "Attention Required" not in title and "Cloudflare" not in title:
                    break
                time.sleep(1)

            # Give a brief moment for dynamic hydration
            time.sleep(1.2)
            content = self._page.content()

            if "Just a moment..." in content and "Challenge" in content:
                # Still challenge? Try TLS HTTP fallback
                return self.fetch_fast(url)

            return content, "Stealth Persistent Browser"
        except Exception as e:
            # Fallback to fast TLS curl_cffi on browser error
            res, code, method = self.fetch_fast(url)
            if res and "Just a moment..." not in res:
                return res, method
            return None, f"Browser Fetch Error: {str(e)}"

    def fetch_fast(self, url: str) -> Tuple[Optional[str], int, str]:
        """Fast HTTP request with Chrome 124 TLS fingerprint impersonation."""
        try:
            proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
            resp = cffi_requests.get(
                url,
                impersonate="chrome124",
                headers=self.headers,
                proxies=proxies,
                timeout=15
            )
            if resp.status_code == 200 and "Just a moment..." not in resp.text:
                return resp.text, 200, "Fast TLS HTTP"
            return resp.text, resp.status_code, f"HTTP {resp.status_code} (Challenge)"
        except Exception as e:
            return None, 0, f"Error: {str(e)}"

    def fetch_stealth_browser(self, url: str, timeout_sec: int = 25) -> Tuple[Optional[str], str]:
        return self.fetch_browser_fast(url, timeout_sec)

    def close(self):
        """Closes browser session."""
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
