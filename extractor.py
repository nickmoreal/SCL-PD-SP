from typing import Optional, Dict, Any, List
from bs4 import BeautifulSoup
from models import ProductDetail
from parsers.json_ld_parser import JsonLdParser
from parsers.dom_parser import DomParser
from fetcher import PageFetcher


class ProductExtractor:
    """Main Orchestrator for extracting product details from any e-commerce URL."""

    def __init__(self, proxy: Optional[str] = None):
        self.fetcher = PageFetcher(proxy=proxy)

    def extract_from_html(self, html: str, url: str) -> ProductDetail:
        soup = BeautifulSoup(html, "html.parser")
        
        # Step 1: Extract structured data from JSON-LD Schema.org
        product = JsonLdParser.extract(soup, url)
        if not product:
            product = ProductDetail(url=url)

        # Step 2: Enrich and fill missing fields using DOM selectors
        product = DomParser.enrich(product, soup)

        return product

    def extract_from_url(self, url: str, mode: str = "auto") -> ProductDetail:
        html = None
        fetch_method = "Unknown"

        if mode == "auto":
            html, code, method = self.fetcher.fetch_fast(url)
            fetch_method = method
            if not html or "Just a moment..." in html or code != 200:
                print(f"[Auto] Fast fetch returned status {code}. Switching to stealth browser...")
                html, method = self.fetcher.fetch_stealth_browser(url)
                fetch_method = method
                if not html or "Just a moment..." in html:
                    print("[Auto] Switching to interactive browser session...")
                    html, method = self.fetcher.fetch_interactive_browser(url)
                    fetch_method = method
        elif mode == "fast":
            html, code, fetch_method = self.fetcher.fetch_fast(url)
        elif mode == "stealth":
            html, fetch_method = self.fetcher.fetch_stealth_browser(url)
        elif mode == "interactive":
            html, fetch_method = self.fetcher.fetch_interactive_browser(url)

        if not html:
            raise ValueError(f"Failed to fetch content from {url} ({fetch_method})")

        product = self.extract_from_html(html, url)
        return product
