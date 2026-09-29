from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone


@dataclass
class ProductVariant:
    variant_id: Optional[str] = None
    sku: Optional[str] = None
    upc: Optional[str] = None
    gtin: Optional[str] = None
    size: Optional[str] = None
    color: Optional[str] = None
    price: Optional[float] = None
    regular_price: Optional[float] = None
    in_stock: bool = True
    stock_quantity: Optional[int] = None
    image_url: Optional[str] = None
    attributes: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProductDetail:
    url: str
    title: str = ""
    brand: Optional[str] = None
    price: Optional[float] = None
    regular_price: Optional[float] = None
    sale_price: Optional[float] = None
    currency: str = "USD"
    in_stock: bool = True
    stock_status: str = "InStock"
    sku: Optional[str] = None
    upc: Optional[str] = None
    gtin: Optional[str] = None
    mpn: Optional[str] = None
    sizes: List[str] = field(default_factory=list)
    colors: List[str] = field(default_factory=list)
    description: str = ""
    images: List[str] = field(default_factory=list)
    rating: Optional[float] = None
    review_count: Optional[int] = None
    specifications: Dict[str, str] = field(default_factory=dict)
    variants: List[ProductVariant] = field(default_factory=list)
    scraped_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw_json_ld: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_summary_dict(self) -> Dict[str, Any]:
        return {
            "URL": self.url,
            "Title": self.title,
            "Brand": self.brand or "",
            "Price": self.price if self.price is not None else "",
            "Regular Price": self.regular_price if self.regular_price is not None else "",
            "Sale Price": self.sale_price if self.sale_price is not None else "",
            "Currency": self.currency,
            "Stock Status": self.stock_status,
            "In Stock": "Yes" if self.in_stock else "No",
            "SKU": self.sku or "",
            "UPC/GTIN": self.upc or self.gtin or "",
            "MPN": self.mpn or "",
            "Available Sizes": ", ".join(self.sizes),
            "Available Colors": ", ".join(self.colors),
            "Rating": self.rating if self.rating is not None else "",
            "Review Count": self.review_count if self.review_count is not None else "",
            "Images Count": len(self.images),
            "Main Image": self.images[0] if self.images else "",
            "Description": (self.description[:300] + "...") if len(self.description) > 300 else self.description,
            "Scraped At": self.scraped_at
        }
