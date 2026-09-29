import os
import time
import json
from typing import Optional, Tuple
from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
from playwright.sync_api import sync_playwright


class PageFetcher:
    """
    Multi-strategy page fetcher:
    1. TLS Fingerprint Fast HTTP (curl_cffi)
    2. Headless / Stealth Playwright Browser
    3. Interactive Session for Cloudflare Protected Sites (Scheels, Nike, etc.)
    """

    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def fetch_fast(self, url: str) -> Tuple[Optional[str], int, str]:
        """Fast HTTP request with TLS fingerprint impersonation."""
        try:
            proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
            resp = cffi_requests.get(
                url,
                impersonate="chrome124",
                headers=self.headers,
                proxies=proxies,
                timeout=15
            )
            if resp.status_code == 200:
                if "Just a moment..." not in resp.text:
                    return resp.text, 200, "Fast TLS HTTP"
            return resp.text, resp.status_code, f"HTTP {resp.status_code} (Challenge or Blocked)"
        except Exception as e:
            return None, 0, f"Error: {str(e)}"

    def fetch_stealth_browser(self, url: str, timeout_sec: int = 15) -> Tuple[Optional[str], str]:
        """Automated Playwright browser with stealth configurations."""
        try:
            with sync_playwright() as p:
                launch_kwargs = {
                    "headless": True,
                    "args": [
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-dev-shm-usage"
                    ]
                }
                if self.proxy:
                    launch_kwargs["proxy"] = {"server": self.proxy}

                browser = p.chromium.launch(**launch_kwargs)
                context = browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent=self.headers["User-Agent"]
                )
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_sec * 1000)
                
                for _ in range(5):
                    time.sleep(1)
                    title = page.title()
                    if "Just a moment" not in title and len(title) > 0:
                        break

                content = page.content()
                browser.close()
                return content, "Headless Stealth Browser"
        except Exception as e:
            return None, f"Playwright Error: {str(e)}"

    def fetch_interactive_browser(self, url: str) -> Tuple[Optional[str], str]:
        """
        Interactive Headful Browser session for sites with Cloudflare Turnstile / Bot Verification.
        """
        try:
            with sync_playwright() as p:
                user_data = os.path.expanduser(r"~\.gemini\antigravity\scratch\browser_session")
                os.makedirs(user_data, exist_ok=True)
                
                context = p.chromium.launch_persistent_context(
                    user_data_dir=user_data,
                    headless=False,
                    viewport={"width": 1366, "height": 768},
                    user_agent=self.headers["User-Agent"],
                    args=["--disable-blink-features=AutomationControlled"]
                )
                page = context.pages[0] if context.pages else context.new_page()
                print(f"[Session] Navigating to: {url}")
                page.goto(url)

                print("[Session] Waiting for page load...")
                for i in range(30):
                    time.sleep(1)
                    title = page.title()
                    if "Just a moment" not in title and "Challenge" not in title and len(title) > 0:
                        print(f"[Session] Reached page: {title}")
                        break

                time.sleep(3)
                content = page.content()
                context.close()
                return content, "Interactive Session Browser"
        except Exception as e:
            return None, f"Interactive Browser Error: {str(e)}"
