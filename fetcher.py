import os
import time
import random
from typing import Optional, Tuple
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
from playwright.sync_api import sync_playwright, Browser, BrowserContext


class PageFetcher:
    """
    High-Stability Cloudflare-Proof Fetcher for Cloud & GitHub Actions:
    - Keeps single Chromium browser process alive.
    - Creates fresh isolated page per URL (prevents Cloudflare session lock).
    - Blocks only third-party trackers while allowing Cloudflare verification JS.
    - Automatic TLS fingerprint fallback.
    """

    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        self.headers = {
            "User-Agent": self.user_agent,
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
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    def _ensure_context(self):
        if self._playwright is None:
            self._playwright = sync_playwright().start()

        if self._browser is None or not self._browser.is_connected():
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

        if self._context is None:
            self._context = self._browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=self.user_agent,
                locale="en-US",
                timezone_id="America/Chicago"
            )
            # Stealth overrides
            self._context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            """)

    def fetch_browser_stealth(self, url: str, timeout_sec: int = 25) -> Tuple[Optional[str], str]:
        """Fetches URL in a fresh isolated page to guarantee zero Cloudflare state carry-over."""
        page = None
        try:
            self._ensure_context()
            page = self._context.new_page()

            # Block heavy tracking ads only (do not block cloudflare or first-party assets)
            def tracker_filter(route):
                u = route.request.url.lower()
                if any(ad in u for ad in ["google-analytics", "doubleclick", "clarip", "klaviyo", "tiktok", "snapchat", "pinterest", "facebook"]):
                    route.abort()
                else:
                    route.continue_()

            page.route("**/*", tracker_filter)

            page.goto(url, wait_until="domcontentloaded", timeout=timeout_sec * 1000)

            # Wait for legit title/content
            for _ in range(12):
                title = page.title()
                if title and not any(k in title.lower() for k in ["just a moment", "attention required", "cloudflare", "challenge"]):
                    break
                time.sleep(0.8)

            time.sleep(1.0)
            content = page.content()

            if "Just a moment..." in content and "Challenge" in content:
                # If challenge remained, try TLS fallback
                return self.fetch_fast_tls(url)

            return content, "Stealth Page"
        except Exception as e:
            # Fallback to fast TLS
            res, code, method = self.fetch_fast_tls(url)
            if res and "Just a moment..." not in res:
                return res, method
            return None, f"Browser Error: {str(e)}"
        finally:
            if page and not page.is_closed():
                try:
                    page.close()
                except Exception:
                    pass

    def fetch_fast_tls(self, url: str) -> Tuple[Optional[str], int, str]:
        """Fast HTTP request with Chrome TLS fingerprint impersonation."""
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
            return None, 0, f"TLS Error: {str(e)}"

    def fetch(self, url: str) -> Tuple[Optional[str], str]:
        """Dual-strategy fetch with fresh tab & respectful human pacing."""
        # Add 1.0s - 1.8s random human pacing between requests
        time.sleep(random.uniform(1.0, 1.8))

        html, method = self.fetch_browser_stealth(url)
        if html and "Just a moment..." not in html:
            return html, method

        # Retry once after 2s pause if first attempt had challenge
        time.sleep(2.0)
        html, method = self.fetch_browser_stealth(url, timeout_sec=30)
        if html and "Just a moment..." not in html:
            return html, method

        return None, "Failed after retries"

    def close(self):
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
