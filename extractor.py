from typing import Optional
import re
from bs4 import BeautifulSoup
from models import ProductDetail
from fetcher import PageFetcher
from parsers.json_ld_parser import JsonLdParser
from parsers.dom_parser import DomParser


class ProductExtractor:
    """Extracts structured product data from Scheels and e-commerce stores."""

    def __init__(self, proxy: Optional[str] = None):
        self.fetcher = PageFetcher(proxy=proxy)

    @staticmethod
    def clean_url(url: str) -> str:
        """
        Normalizes Scheels URLs by removing trailing slashes and converting long slugs
        to direct canonical /p/{id} URLs to prevent 301/302 Cloudflare redirect traps.
        e.g. /p/evoshield-pro-srz-2.0-batters-leg-guard/891226-WB57269/ -> https://www.scheels.com/p/891226-WB57269
        """
        url = url.strip()
        if "scheels.com/p/" in url:
            # Match master ID at the end of the /p/ path
            m = re.search(r"scheels\.com/p/(?:[^/]+/)?([A-Za-z0-9\-_]+)/?(?:\?.*)?$", url)
            if m:
                prod_id = m.group(1)
                # Keep query params if any
                query = ""
                if "?" in url:
                    query = "?" + url.split("?", 1)[1]
                return f"https://www.scheels.com/p/{prod_id}{query}"
        return url.rstrip("/")

    def extract_from_html(self, html: str, url: str) -> ProductDetail:
        soup = BeautifulSoup(html, "html.parser")

        # Step 1: Extract structured data from JSON-LD Schema.org
        product = JsonLdParser.extract(soup, url)
        if not product:
            product = ProductDetail(url=url)

        # Step 2: Enrich and fill missing fields using DOM selectors and swatches
        product = DomParser.enrich(product, soup)

        return product

    def extract_from_url(self, url: str, mode: str = "auto") -> ProductDetail:
        # Normalize URL to avoid redirect traps
        target_url = self.clean_url(url)

        html, method = self.fetcher.fetch(target_url)

        if not html:
            # Fallback to original url if cleaned failed
            if target_url != url:
                html, method = self.fetcher.fetch(url)

        if not html:
            raise ValueError(f"Failed to fetch content from {url} ({method})")

        product = self.extract_from_html(html, url)
        return product

    def close(self):
        self.fetcher.close()
