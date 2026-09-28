import re
from typing import List, Dict, Optional, Tuple
from bs4 import BeautifulSoup
from models import ProductDetail, ProductVariant


class DomParser:
    """Fallback and enrichment parser that extracts product details directly from HTML DOM."""

    @staticmethod
    def enrich(product: ProductDetail, soup: BeautifulSoup) -> ProductDetail:
        if not product.title:
            product.title = DomParser._extract_title(soup)

        if not product.brand:
            product.brand = DomParser._extract_brand(soup)

        if product.price is None:
            price, regular_price, sale_price = DomParser._extract_prices(soup)
            product.price = price
            product.regular_price = regular_price
            product.sale_price = sale_price

        if product.stock_status == "InStock" and not product.raw_json_ld:
            product.in_stock, product.stock_status = DomParser._extract_stock(soup)

        # Extract Sizes & Colors
        sizes, colors = DomParser._extract_sizes_and_colors(soup)
        if sizes:
            for s in sizes:
                if s not in product.sizes:
                    product.sizes.append(s)
        if colors:
            for c in colors:
                if c not in product.colors:
                    product.colors.append(c)

        # If product has no variants (or only 1 default) but page has multiple color/size swatches:
        # Extract swatch-based variants so every color gets its SKU, UPC, and Image!
        DomParser._enrich_swatch_variants(product, soup)

        if not product.images:
            product.images = DomParser._extract_images(soup)

        if not product.description:
            product.description = DomParser._extract_description(soup)

        specs = DomParser._extract_specifications(soup)
        if specs:
            product.specifications.update(specs)
            for k, val in specs.items():
                k_lower = k.lower()
                if "upc" in k_lower or "barcode" in k_lower or "gtin" in k_lower:
                    if not product.upc:
                        product.upc = val
                elif "sku" in k_lower or "item #" in k_lower or "style #" in k_lower:
                    if not product.sku:
                        product.sku = val
                elif "brand" in k_lower or "manufacturer" in k_lower:
                    if not product.brand:
                        product.brand = val
                elif "mpn" in k_lower:
                    if not product.mpn:
                        product.mpn = val

        if not product.upc or not product.sku or not product.mpn:
            upc, sku = DomParser._extract_identifiers_regex(soup)
            if not product.upc and upc:
                product.upc = upc
            if not product.sku and sku:
                product.sku = sku
            if not product.mpn and sku:
                product.mpn = sku

        return product

    @staticmethod
    def _enrich_swatch_variants(product: ProductDetail, soup: BeautifulSoup):
        """When JSON-LD doesn't have ProductGroup variants, build them from DOM color/size swatches."""
        if len(product.variants) > 1:
            # Already has rich variants from ProductGroup
            return

        html_text = str(soup)
        swatch_variants = []
        seen_colors = set()

        for el in soup.find_all(attrs={"aria-label": True}):
            al = el["aria-label"].strip()
            color_m = re.match(r"^color:\s*(.+)$", al, re.I)
            if not color_m:
                continue

            color_name = color_m.group(1).strip()
            if color_name in seen_colors:
                continue
            seen_colors.add(color_name)

            # Find SKU from background-image url or data attributes
            style_attr = el.get("style", "")
            sku_match = re.search(r"scheelspoc/(\d+)", style_attr)
            variant_sku = sku_match.group(1) if sku_match else None

            # Full image url
            img_match = re.search(r'url\("([^"]+)"\)', style_attr)
            img_url = img_match.group(1).split("?")[0] if img_match else None

            # Look for 12-digit UPC starting with variant_sku in the HTML
            variant_upc = None
            if variant_sku:
                upc_match = re.search(rf"\b({variant_sku}\d)\b", html_text)
                if upc_match:
                    variant_upc = upc_match.group(1)
                elif len(variant_sku) == 12:
                    variant_upc = variant_sku

            swatch_variants.append(ProductVariant(
                sku=variant_sku or product.sku,
                upc=variant_upc or product.upc,
                gtin=variant_upc or product.gtin,
                color=color_name,
                size=product.sizes[0] if len(product.sizes) == 1 else None,
                price=product.price,
                regular_price=product.regular_price,
                in_stock=True,
                image_url=img_url or (product.images[0] if product.images else None)
            ))

        if len(swatch_variants) > 1:
            product.variants = swatch_variants
            # Also ensure all colors are populated
            product.colors = list(seen_colors)

    @staticmethod
    def _extract_title(soup: BeautifulSoup) -> str:
        for sel in [
            "h1.product-title", "h1.pdp-title", "h1.product-name", "h1[data-testid='product-name']",
            "h1.product__title", ".product-detail__title", "h1"
        ]:
            elem = soup.select_one(sel)
            if elem and elem.get_text().strip():
                return elem.get_text().strip()

        meta = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "twitter:title"})
        if meta and meta.get("content"):
            return meta["content"].strip()

        if soup.title and soup.title.string:
            title_text = soup.title.string.strip()
            title_text = re.split(r"\|| - | — ", title_text)[0].strip()
            return title_text
        return ""

    @staticmethod
    def _extract_brand(soup: BeautifulSoup) -> Optional[str]:
        for sel in [
            ".product-brand", ".brand-name", "a.product-brand", "[data-testid='brand-name']",
            ".pdp-brand", ".vendor", ".product__vendor"
        ]:
            elem = soup.select_one(sel)
            if elem and elem.get_text().strip():
                return elem.get_text().strip()

        meta = soup.find("meta", property="product:brand") or soup.find("meta", attrs={"name": "brand"})
        if meta and meta.get("content"):
            return meta["content"].strip()

        if soup.title and soup.title.string:
            first_word = soup.title.string.split()[0]
            if first_word.lower() in ["nike", "adidas", "under", "stanley", "yeti", "hoka", "on", "sitka", "vortex", "evoshield"]:
                return first_word.capitalize()
        return None

    @staticmethod
    def _extract_prices(soup: BeautifulSoup) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        price = None
        regular_price = None
        sale_price = None

        meta_price = soup.find("meta", property="product:price:amount") or soup.find("meta", property="og:price:amount")
        if meta_price and meta_price.get("content"):
            try:
                price = float(meta_price["content"].replace("$", "").replace(",", "").strip())
            except ValueError:
                pass

        price_selectors = [
            ".price-sales", ".sales .value", ".product-price", ".pdp-price", ".price__current",
            ".sale-price", ".price-regular", "[data-testid='product-price']", ".current-price",
            ".price .value", ".price"
        ]
        for sel in price_selectors:
            elem = soup.select_one(sel)
            if elem:
                text = elem.get_text().strip()
                matches = re.findall(r"\$\s*([0-9]+(?:\.[0-9]{2})?)", text)
                if matches:
                    try:
                        extracted = float(matches[0])
                        if price is None:
                            price = extracted
                        break
                    except ValueError:
                        pass

        strike_selectors = [".price-standard", ".strike-through", ".price__was", ".original-price", ".was-price"]
        for sel in strike_selectors:
            elem = soup.select_one(sel)
            if elem:
                text = elem.get_text().strip()
                matches = re.findall(r"\$\s*([0-9]+(?:\.[0-9]{2})?)", text)
                if matches:
                    try:
                        regular_price = float(matches[0])
                        if price and regular_price > price:
                            sale_price = price
                        break
                    except ValueError:
                        pass

        return price, regular_price, sale_price

    @staticmethod
    def _extract_stock(soup: BeautifulSoup) -> Tuple[bool, str]:
        meta = soup.find("meta", property="product:availability") or soup.find("meta", property="og:availability")
        if meta and meta.get("content"):
            val = meta["content"].lower()
            if "instock" in val or "in stock" in val:
                return True, "InStock"
            elif "outofstock" in val or "out of stock" in val:
                return False, "OutOfStock"

        text_lower = soup.get_text().lower()
        if "out of stock" in text_lower or "sold out" in text_lower or "currently unavailable" in text_lower:
            for sel in [".out-of-stock-badge", ".sold-out", ".product-unavailable", "button[disabled].add-to-cart"]:
                if soup.select_one(sel):
                    return False, "OutOfStock"

        return True, "InStock"

    @staticmethod
    def _extract_sizes_and_colors(soup: BeautifulSoup) -> Tuple[List[str], List[str]]:
        sizes = []
        colors = []

        # 1. Look for modern Tailwind/React aria labels and swatch attributes
        for el in soup.find_all(["div", "button", "a", "span"]):
            for attr_name, attr_val in el.attrs.items():
                val_str = str(attr_val).strip()
                if not val_str:
                    continue
                # Color pattern (e.g. "color: Black/White", "Color: Nude Tone")
                color_m = re.match(r"^color:\s*([A-Za-z0-9\s/_\-]+)$", val_str, re.I)
                if color_m:
                    c_clean = color_m.group(1).strip()
                    if c_clean and len(c_clean) < 40 and c_clean not in colors:
                        colors.append(c_clean)

                # Size pattern (e.g. "sockSize: Large", "size: Medium", "size: 10.5")
                size_m = re.match(r"^(?:sockSize|size|waist|length|shoeSize):\s*([A-Za-z0-9\.\s/_\-]+?)(?:\s+currently|\s+out|\s+limited|$)", val_str, re.I)
                if size_m:
                    s_clean = size_m.group(1).strip()
                    if s_clean and len(s_clean) < 25 and s_clean not in sizes:
                        sizes.append(s_clean)

        # 2. Standard CSS Selectors fallback
        size_selectors = [
            "select[name*='size'] option", ".size-selector button", ".size-swatches button",
            "[data-attr='size'] button", ".variant-option-size", "ul.sizes li button",
            ".size-pill", ".size-attribute button", "[data-testid*='size']"
        ]
        for sel in size_selectors:
            elems = soup.select(sel)
            for el in elems:
                val = el.get_text().strip()
                if val and not re.search(r"select|choose|please|chart|guide", val, re.I) and len(val) < 25:
                    if val not in sizes:
                        sizes.append(val)

        color_selectors = [
            ".color-swatches [title]", ".color-selector button", "[data-attr='color'] [title]",
            "select[name*='color'] option", ".swatch-color", ".color-name",
            "[data-attr-value-name]", "[data-testid*='color']"
        ]
        for sel in color_selectors:
            elems = soup.select(sel)
            for el in elems:
                val = el.get("title") or el.get("data-attr-value-name") or el.get_text().strip()
                if val and not re.search(r"select|choose|please", val, re.I) and len(val) < 40:
                    if val not in colors:
                        colors.append(val)

        return sizes, colors

    @staticmethod
    def _extract_images(soup: BeautifulSoup) -> List[str]:
        images = []
        meta_img = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
        if meta_img and meta_img.get("content"):
            images.append(meta_img["content"].strip())

        img_selectors = [
            ".product-gallery img", ".pdp-gallery img", ".product__media img",
            ".main-image img", "[data-testid='product-image']", ".carousel-item img"
        ]
        for sel in img_selectors:
            elems = soup.select(sel)
            for el in elems:
                src = el.get("src") or el.get("data-src") or el.get("data-zoom-src")
                if src and src.startswith("http") and not any(x in src.lower() for x in ["icon", "logo", "badge"]):
                    if src not in images:
                        images.append(src)

        return images

    @staticmethod
    def _extract_description(soup: BeautifulSoup) -> str:
        for sel in [
            ".product-description", ".pdp-description", "#description", ".description-text",
            "[data-testid='product-description']", ".product-details__description"
        ]:
            elem = soup.select_one(sel)
            if elem and elem.get_text().strip():
                return elem.get_text(separator=" ").strip()

        meta_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            return meta_desc["content"].strip()
        return ""

    @staticmethod
    def _extract_specifications(soup: BeautifulSoup) -> Dict[str, str]:
        specs = {}
        for table in soup.select("table.specifications, table.product-specs, .pdp-specs table, table"):
            for row in table.select("tr"):
                cols = row.select("th, td")
                if len(cols) == 2:
                    k = cols[0].get_text().strip()
                    v = cols[1].get_text().strip()
                    if k and v and len(k) < 50:
                        specs[k] = v

        for dl in soup.select("dl.specs, dl.product-features, .pdp-attributes dl"):
            dts = dl.select("dt")
            dds = dl.select("dd")
            for dt, dd in zip(dts, dds):
                k = dt.get_text().strip()
                v = dd.get_text().strip()
                if k and v:
                    specs[k] = v

        for item in soup.find_all(["li", "p", "div", "span"]):
            text = item.get_text(separator=" | ").strip()
            if ":" in text and "|" in text and len(text) < 400:
                parts = text.split("|")
                for p in parts:
                    if ":" in p:
                        sub_parts = p.split(":", 1)
                        k = sub_parts[0].strip()
                        v = sub_parts[1].strip()
                        if k and v and len(k) < 35 and len(v) < 100:
                            specs[k] = v

        return specs

    @staticmethod
    def _extract_identifiers_regex(soup: BeautifulSoup) -> Tuple[Optional[str], Optional[str]]:
        text = soup.get_text()
        upc = None
        sku = None

        upc_match = re.search(r"\bUPC(?:\s*[:#-]?\s*)([0-9]{12})\b", text, re.I)
        if upc_match:
            upc = upc_match.group(1)

        sku_match = re.search(r"\b(?:SKU|Item\s*#|Style\s*#)(?:\s*[:#-]?\s*)([A-Za-z0-9\-_]{4,20})\b", text, re.I)
        if sku_match:
            sku = sku_match.group(1)

        return upc, sku
