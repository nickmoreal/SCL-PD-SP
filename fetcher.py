import os
import time
import random
from typing import Optional, Tuple
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page


class PageFetcher:
    """
    High-Reliability Multi-Tier Page Fetcher:
    Tier 1: TLS Fingerprint Impersonation (curl_cffi with browser headers) - Fast & Bypasses Cloudflare
    Tier 2: Real Headless Chromium with Challenge Resolver & Navigation Delays
    """

    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        }
        self._session = None
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    def _get_session(self):
        if self._session is None:
            self._session = cffi_requests.Session(impersonate="chrome124")
        return self._session

    def fetch_fast_tls(self, url: str) -> Tuple[Optional[str], int, str]:
        """Direct TLS Fingerprint fetch using persistent session with realistic headers."""
        try:
            session = self._get_session()
            proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
            resp = session.get(
                url,
                headers=self.headers,
                proxies=proxies,
                timeout=18
            )
            text = resp.text
            if resp.status_code == 200:
                if "Just a moment..." not in text and ("@type" in text or "product" in text.lower()):
                    return text, 200, "Fast TLS HTTP"
            return text, resp.status_code, f"HTTP {resp.status_code} (Challenge)"
        except Exception as e:
            return None, 0, f"TLS Error: {str(e)}"

    def _ensure_browser(self):
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
            user_agent=self.headers["User-Agent"],
            locale="en-US"
        )

        self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)

        self._page = self._context.new_page()

    def fetch_browser_stealth(self, url: str, timeout_sec: int = 30) -> Tuple[Optional[str], str]:
        """Browser fetch that waits for Cloudflare Turnstile to solve before capturing content."""
        try:
            self._ensure_browser()
            self._page.goto(url, wait_until="domcontentloaded", timeout=timeout_sec * 1000)

            # Wait for legit title and content
            for _ in range(15):
                title = self._page.title()
                if title and not any(k in title.lower() for k in ["just a moment", "attention required", "cloudflare", "challenge"]):
                    break
                time.sleep(1)

            # Allow React/Next.js hydration
            time.sleep(1.5)
            content = self._page.content()

            if "Just a moment..." in content and "Challenge" in content:
                # If still challenge in browser, fallback to TLS
                res, code, method = self.fetch_fast_tls(url)
                if res and "Just a moment..." not in res:
                    return res, method
                return None, "Blocked by Challenge"

            return content, "Stealth Browser"
        except Exception as e:
            try:
                if self._page:
                    self._page.close()
                self._page = self._context.new_page() if self._context else None
            except Exception:
                pass
            return None, f"Browser Error: {str(e)}"

    def fetch(self, url: str) -> Tuple[Optional[str], str]:
        """Dual-strategy fetch with automatic retry."""
        # Step 1: Try stealth browser
        html, method = self.fetch_browser_stealth(url)
        if html and "Just a moment..." not in html:
            return html, method

        # Step 2: Fallback to Fast TLS session
        html, code, method = self.fetch_fast_tls(url)
        if html and "Just a moment..." not in html:
            return html, method

        # Step 3: Wait 2s and retry once
        time.sleep(2)
        html, method = self.fetch_browser_stealth(url, timeout_sec=35)
        if html and "Just a moment..." not in html:
            return html, method

        return None, "Failed after retries"

    def close(self):
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
