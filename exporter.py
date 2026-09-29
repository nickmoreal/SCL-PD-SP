import json
import csv
from typing import List
import pandas as pd
from models import ProductDetail


class ProductExporter:
    """Exports extracted product details to JSON, CSV, and formatted Excel files."""

    @staticmethod
    def to_json(products: List[ProductDetail], filepath: str, indent: int = 2):
        data = [p.to_dict() for p in products]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        print(f"[Exporter] Saved JSON to: {filepath}")

    @staticmethod
    def to_csv(products: List[ProductDetail], filepath: str):
        rows = [p.to_summary_dict() for p in products]
        if not rows:
            return
        keys = rows[0].keys()
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(rows)
        print(f"[Exporter] Saved CSV to: {filepath}")

    @staticmethod
    def to_excel(products: List[ProductDetail], filepath: str):
        # ── Sheet 1: Products (one row per URL) ────────────────────────────────
        summary_rows = [p.to_summary_dict() for p in products]
        df_summary = pd.DataFrame(summary_rows)

        # ── Sheet 2: Variants (one row per SKU/size/color combination) ─────────
        variant_rows = []
        for p in products:
            if p.variants:
                for v in p.variants:
                    availability = "InStock" if v.in_stock else "OutOfStock"
                    row = {
                        "Product URL":      p.url,
                        "Product Title":    p.title,
                        "Brand":            p.brand or "",
                        "Style / MPN":      p.mpn or "",
                        "Variant SKU":      v.sku or "",
                        "UPC / GTIN":       v.upc or v.gtin or "",
                        "Size":             v.size or "",
                        "Color":            v.color or "",
                        "Price":            v.price if v.price is not None else "",
                        "Regular Price":    v.regular_price if v.regular_price is not None else "",
                        "Currency":         p.currency,
                        "Stock Status":     availability,
                        "In Stock":         "Yes" if v.in_stock else "No",
                        "Image URL":        v.image_url or (p.images[0] if p.images else ""),
                    }
                    # Include any extra attributes
                    for k, val in (v.attributes or {}).items():
                        if k not in row:
                            row[k] = val
                    variant_rows.append(row)
            else:
                # No variants — add a single row from the master product
                variant_rows.append({
                    "Product URL":      p.url,
                    "Product Title":    p.title,
                    "Brand":            p.brand or "",
                    "Style / MPN":      p.mpn or "",
                    "Variant SKU":      p.sku or "",
                    "UPC / GTIN":       p.upc or p.gtin or "",
                    "Size":             ", ".join(p.sizes),
                    "Color":            ", ".join(p.colors),
                    "Price":            p.price if p.price is not None else "",
                    "Regular Price":    p.regular_price if p.regular_price is not None else "",
                    "Currency":         p.currency,
                    "Stock Status":     p.stock_status,
                    "In Stock":         "Yes" if p.in_stock else "No",
                    "Image URL":        p.images[0] if p.images else "",
                })

        df_variants = pd.DataFrame(variant_rows) if variant_rows else pd.DataFrame(
            [{"Note": "No variants found"}])

        # ── Sheet 3: Specifications ────────────────────────────────────────────
        spec_rows = []
        for p in products:
            for k, val in p.specifications.items():
                spec_rows.append({
                    "Product Title": p.title,
                    "Attribute":     k,
                    "Value":         val,
                    "URL":           p.url
                })
        df_specs = pd.DataFrame(spec_rows) if spec_rows else pd.DataFrame(
            [{"Note": "No specifications found"}])

        # ── Write workbook ────────────────────────────────────────────────────
        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            df_summary.to_excel(writer, sheet_name="Products", index=False)
            df_variants.to_excel(writer, sheet_name="Variants", index=False)
            df_specs.to_excel(writer, sheet_name="Specifications", index=False)

            # Auto-fit column widths for readability
            for sheet_name in ["Products", "Variants", "Specifications"]:
                ws = writer.sheets[sheet_name]
                for col in ws.columns:
                    max_len = max(
                        (len(str(cell.value)) if cell.value else 0 for cell in col),
                        default=10
                    )
                    ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)

        print(f"[Exporter] Saved Excel workbook to: {filepath}")
