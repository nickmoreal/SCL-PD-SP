import os
import time
import random
import tempfile
from typing import Optional, Tuple
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
from playwright.sync_api import sync_playwright, BrowserContext, Page


class PageFetcher:
    """
    Production-Grade Dual Tier Fetcher:
    Tier 1: curl_cffi TLS impersonation with Chrome 124 TLS cipher fingerprint.
    Tier 2: Headful/Stealth Playwright Chromium with persistent session storage.
    """

    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
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
        self._context: Optional[BrowserContext] = None

    def _get_http_session(self):
        if self._session is None:
            self._session = cffi_requests.Session(impersonate="chrome124")
        return self._session

    def fetch_fast_tls(self, url: str) -> Tuple[Optional[str], int, str]:
        """Fast HTTP request with TLS fingerprint impersonation."""
        try:
            session = self._get_http_session()
            proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
            resp = session.get(
                url,
                headers=self.headers,
                proxies=proxies,
                timeout=15
            )
            text = resp.text
            if resp.status_code == 200 and "Just a moment..." not in text:
                return text, 200, "Fast TLS HTTP"
            return text, resp.status_code, f"HTTP {resp.status_code}"
        except Exception as e:
            return None, 0, f"TLS Error: {str(e)}"

    def _ensure_browser(self):
        if self._playwright is None:
            self._playwright = sync_playwright().start()

        if self._context is None:
            user_data = os.path.expanduser(r"~\.gemini\antigravity\scratch\browser_session")
            os.makedirs(user_data, exist_ok=True)
            
            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=user_data,
                headless=False,
                viewport={"width": 1366, "height": 768},
                user_agent=self.headers["User-Agent"],
                args=["--disable-blink-features=AutomationControlled"]
            )

    def fetch_browser(self, url: str, timeout_sec: int = 30) -> Tuple[Optional[str], str]:
        try:
            self._ensure_browser()
            page = self._context.pages[0] if self._context.pages else self._context.new_page()

            page.goto(url, wait_until="domcontentloaded", timeout=timeout_sec * 1000)

            for _ in range(15):
                title = page.title()
                if title and not any(k in title.lower() for k in ["just a moment", "attention required", "cloudflare"]):
                    break
                time.sleep(0.8)

            time.sleep(1.2)
            content = page.content()
            return content, "Browser Session"
        except Exception as e:
            return None, f"Browser Error: {str(e)}"

    def fetch(self, url: str) -> Tuple[Optional[str], str]:
        # Strategy 1: Fast TLS request
        html, code, method = self.fetch_fast_tls(url)
        if html and "Just a moment..." not in html:
            return html, method

        # Strategy 2: Persistent Browser Session
        html, method = self.fetch_browser(url)
        if html and "Just a moment..." not in html:
            return html, method

        return None, "Failed to bypass challenge"

    def close(self):
        try:
            if self._context:
                self._context.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
