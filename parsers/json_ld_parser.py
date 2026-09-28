import json
import re
from typing import Optional, Dict, Any, List
from bs4 import BeautifulSoup
from models import ProductDetail, ProductVariant


class JsonLdParser:
    """Extracts and merges all Schema.org Product and ProductGroup data from all JSON-LD scripts on the page."""

    @staticmethod
    def extract(soup: BeautifulSoup, url: str) -> Optional[ProductDetail]:
        scripts = soup.find_all("script", type="application/ld+json")
        all_product_nodes = []

        for s in scripts:
            if not s.string:
                continue
            try:
                data = json.loads(s.string.strip())
                nodes = JsonLdParser._find_all_product_nodes(data)
                all_product_nodes.extend(nodes)
            except Exception:
                continue

        if not all_product_nodes:
            return None

        product = ProductDetail(url=url)
        target_id_match = re.search(r"/p/([A-Za-z0-9\-_]+)", url)
        target_id = target_id_match.group(1).split("?")[0].replace(".html", "") if target_id_match else None

        for node in all_product_nodes:
            JsonLdParser._merge_node_into_product(node, product, target_id)

        return product

    @staticmethod
    def _find_all_product_nodes(data: Any) -> List[Dict[str, Any]]:
        nodes = []
        if isinstance(data, dict):
            t = data.get("@type")
            if t in ["Product", "ProductGroup"] or (isinstance(t, list) and any(x in t for x in ["Product", "ProductGroup"])):
                nodes.append(data)
            if "@graph" in data and isinstance(data["@graph"], list):
                for item in data["@graph"]:
                    nodes.extend(JsonLdParser._find_all_product_nodes(item))
        elif isinstance(data, list):
            for item in data:
                nodes.extend(JsonLdParser._find_all_product_nodes(item))
        return nodes

    @staticmethod
    def _merge_node_into_product(data: Dict[str, Any], product: ProductDetail, target_id: Optional[str]):
        if not product.title and data.get("name"):
            product.title = str(data["name"]).strip()

        if not product.brand and data.get("brand"):
            brand = data["brand"]
            if isinstance(brand, dict):
                product.brand = str(brand.get("name") or "").strip()
            elif isinstance(brand, str):
                product.brand = brand.strip()

        if not product.mpn:
            product.mpn = data.get("mpn") or data.get("productGroupId") or data.get("model")

        if not product.sku:
            product.sku = data.get("sku") or data.get("productID")
        if not product.gtin:
            product.gtin = data.get("gtin12") or data.get("gtin13") or data.get("gtin14") or data.get("gtin8") or data.get("gtin")
        if not product.upc:
            product.upc = data.get("gtin12") or (product.gtin if product.gtin and len(str(product.gtin)) == 12 else None)

        if not product.description and data.get("description"):
            desc = data["description"]
            clean_desc = BeautifulSoup(str(desc), "html.parser").get_text(separator=" ").strip()
            product.description = clean_desc

        image_data = data.get("image")
        if image_data:
            if isinstance(image_data, str) and image_data not in product.images:
                product.images.append(image_data)
            elif isinstance(image_data, list):
                for img in image_data:
                    if isinstance(img, str) and img not in product.images:
                        product.images.append(img)
                    elif isinstance(img, dict) and "url" in img and img["url"] not in product.images:
                        product.images.append(img["url"])
            elif isinstance(image_data, dict) and "url" in image_data and image_data["url"] not in product.images:
                product.images.append(image_data["url"])

        rating_data = data.get("aggregateRating")
        if rating_data and isinstance(rating_data, dict):
            try:
                product.rating = float(rating_data.get("ratingValue") or 0)
                product.review_count = int(rating_data.get("reviewCount") or rating_data.get("ratingCount") or 0)
            except (ValueError, TypeError):
                pass

        offers = data.get("offers")
        if offers:
            JsonLdParser._parse_offers(offers, product)

        has_variants = data.get("hasVariant", [])
        if isinstance(has_variants, list) and has_variants:
            sizes_list = list(product.sizes)
            colors_list = list(product.colors)
            prices = []
            selected_variant = None

            for var in has_variants:
                if not isinstance(var, dict):
                    continue
                v_sku = str(var.get("sku") or "")
                v_gtin = str(var.get("gtin") or var.get("gtin12") or var.get("gtin13") or "")
                v_size = str(var.get("size") or "")
                v_color = str(var.get("color") or "")
                v_name = str(var.get("name") or "")
                v_image = var.get("image")
                if isinstance(v_image, list) and v_image:
                    v_image = v_image[0]
                elif isinstance(v_image, dict) and "url" in v_image:
                    v_image = v_image["url"]

                v_offer = var.get("offers", {})
                v_price = None
                v_in_stock = True
                if isinstance(v_offer, dict):
                    try:
                        v_price = float(v_offer.get("price")) if v_offer.get("price") is not None else None
                    except (ValueError, TypeError):
                        pass
                    avail = str(v_offer.get("availability") or "").lower()
                    if "outofstock" in avail or "soldout" in avail:
                        v_in_stock = False

                if v_size and v_size not in sizes_list:
                    sizes_list.append(v_size)
                if v_color and v_color not in colors_list:
                    colors_list.append(v_color)
                if v_price is not None:
                    prices.append(v_price)

                variant_obj = ProductVariant(
                    sku=v_sku or None,
                    gtin=v_gtin or None,
                    upc=v_gtin if len(v_gtin) == 12 else None,
                    size=v_size or None,
                    color=v_color or None,
                    price=v_price,
                    in_stock=v_in_stock,
                    image_url=v_image
                )
                product.variants.append(variant_obj)

                if target_id and (v_sku == target_id or target_id in v_sku or (target_id.isdigit() and v_sku == target_id)):
                    selected_variant = variant_obj

            product.sizes = sizes_list
            product.colors = colors_list

            if selected_variant:
                product.sku = selected_variant.sku or product.sku
                product.gtin = selected_variant.gtin or product.gtin
                product.upc = selected_variant.upc or product.upc
                product.price = selected_variant.price if selected_variant.price is not None else product.price
                product.in_stock = selected_variant.in_stock
                product.stock_status = "InStock" if selected_variant.in_stock else "OutOfStock"
                if selected_variant.size and selected_variant.size not in product.sizes:
                    product.sizes.insert(0, selected_variant.size)
                if selected_variant.color and selected_variant.color not in product.colors:
                    product.colors.insert(0, selected_variant.color)
                if selected_variant.image_url and selected_variant.image_url not in product.images:
                    product.images = [selected_variant.image_url] + product.images
            else:
                if prices and product.price is None:
                    product.price = min(prices)
                    if max(prices) > min(prices):
                        product.regular_price = max(prices)
                if product.variants and product.in_stock:
                    product.in_stock = any(v.in_stock for v in product.variants)
                    product.stock_status = "InStock" if product.in_stock else "OutOfStock"
                if not product.sku and product.variants and product.variants[0].sku:
                    product.sku = product.variants[0].sku
                if not product.upc and product.variants and product.variants[0].upc:
                    product.upc = product.variants[0].upc

    @staticmethod
    def _parse_offers(offers: Any, product: ProductDetail):
        if isinstance(offers, dict):
            t = offers.get("@type")
            if t == "AggregateOffer":
                low_price = offers.get("lowPrice") or offers.get("price")
                high_price = offers.get("highPrice")
                product.currency = offers.get("priceCurrency") or product.currency or "USD"
                try:
                    product.price = float(low_price) if low_price is not None else product.price
                    product.regular_price = float(high_price) if high_price is not None else product.regular_price
                except (ValueError, TypeError):
                    pass
                JsonLdParser._check_availability(offers.get("availability"), product)
            else:
                product.currency = offers.get("priceCurrency") or product.currency or "USD"
                price_val = offers.get("price")
                try:
                    if price_val is not None and product.price is None:
                        product.price = float(price_val)
                except (ValueError, TypeError):
                    pass
                JsonLdParser._check_availability(offers.get("availability"), product)
                if not product.sku and offers.get("sku"):
                    product.sku = offers.get("sku")

        elif isinstance(offers, list):
            prices = []
            for off in offers:
                if not isinstance(off, dict):
                    continue
                p_val = off.get("price")
                try:
                    if p_val is not None:
                        prices.append(float(p_val))
                except (ValueError, TypeError):
                    pass
                if not product.currency and off.get("priceCurrency"):
                    product.currency = off.get("priceCurrency")
            if prices and product.price is None:
                product.price = min(prices)
                if max(prices) > min(prices):
                    product.regular_price = max(prices)

    @staticmethod
    def _check_availability(avail: Any, product: ProductDetail):
        if not avail:
            return
        avail_str = str(avail).lower()
        if "instock" in avail_str or "onlineonly" in avail_str or "limitedavailability" in avail_str:
            product.in_stock = True
            product.stock_status = "InStock"
        elif "outofstock" in avail_str or "soldout" in avail_str or "discontinued" in avail_str:
            product.in_stock = False
            product.stock_status = "OutOfStock"
        elif "preorder" in avail_str or "backorder" in avail_str:
            product.in_stock = True
            product.stock_status = "PreOrder"
