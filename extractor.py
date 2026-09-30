from typing import Optional
from bs4 import BeautifulSoup
from models import ProductDetail
from fetcher import PageFetcher
from parsers.json_ld_parser import JsonLdParser
from parsers.dom_parser import DomParser


class ProductExtractor:
    """Extracts structured product data from Scheels and e-commerce stores."""

    def __init__(self, proxy: Optional[str] = None):
        self.fetcher = PageFetcher(proxy=proxy)

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
        html, method = self.fetcher.fetch(url)

        if not html:
            raise ValueError(f"Failed to fetch content from {url} ({method})")

        product = self.extract_from_html(html, url)
        return product

    def close(self):
        self.fetcher.close()
