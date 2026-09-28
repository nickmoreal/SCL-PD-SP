import os
import json
import time
from typing import List
import gspread
from google.oauth2.service_account import Credentials
from extractor import ProductExtractor
from exporter import ProductExporter
from models import ProductDetail


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]


def get_gspread_client():
    """Authenticate with Google Sheets via Service Account JSON file or Environment Variable."""
    # Check if JSON string is provided in environment (for GitHub Actions Secrets)
    creds_json_str = os.environ.get("GCP_SA_KEY")
    if creds_json_str:
        info = json.loads(creds_json_str)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        return gspread.authorize(creds)

    # Local fallback file
    local_creds_path = "credentials.json"
    if os.path.exists(local_creds_path):
        creds = Credentials.from_service_account_file(local_creds_path, scopes=SCOPES)
        return gspread.authorize(creds)

    raise ValueError("Missing Google Service Account credentials! Set GCP_SA_KEY env var or provide credentials.json.")


def run_sheets_scraper():
    sheet_name = os.environ.get("SHEET_NAME", "Scheels_Products")
    mode = os.environ.get("SCRAPE_MODE", "auto")
    print(f"[Sheets] Connecting to Google Sheet: '{sheet_name}' (Mode: {mode})...")

    gc = get_gspread_client()
    try:
        sh = gc.open(sheet_name)
    except gspread.exceptions.SpreadsheetNotFound:
        raise ValueError(f"Sheet '{sheet_name}' not found! Make sure it is created and shared with the service account email.")

    # 1. Read URLs from "Input_URLs" sheet
    try:
        input_ws = sh.worksheet("Input_URLs")
    except gspread.exceptions.WorksheetNotFound:
        # Create it if it doesn't exist
        input_ws = sh.add_worksheet(title="Input_URLs", rows=100, cols=2)
        input_ws.update("A1", [["Product_URL"]])
        print("[Sheets] Created 'Input_URLs' sheet. Please paste URLs in column A.")
        return

    raw_urls = input_ws.col_values(1)[1:]  # skip header
    urls = [u.strip() for u in raw_urls if u.strip() and u.strip().startswith("http")]

    if not urls:
        print("[Sheets] No URLs found in 'Input_URLs' sheet. Exiting.")
        return

    print(f"[Sheets] Found {len(urls)} URLs to scrape.")

    # 2. Scrape each URL
    extractor = ProductExtractor()
    extracted_products: List[ProductDetail] = []

    for idx, url in enumerate(urls, 1):
        print(f"[{idx}/{len(urls)}] Scraping: {url}...")
        try:
            prod = extractor.extract_from_url(url, mode=mode)
            extracted_products.append(prod)
            print(f"   -> Success: {prod.title[:40]} | Variants: {len(prod.variants)}")
        except Exception as e:
            print(f"   -> Error on {url}: {e}")
        time.sleep(1.5)  # respectful delay

    if not extracted_products:
        print("[Sheets] No products extracted. Done.")
        return

    # 3. Update 'Products' sheet
    try:
        prod_ws = sh.worksheet("Products")
    except gspread.exceptions.WorksheetNotFound:
        prod_ws = sh.add_worksheet(title="Products", rows=1000, cols=20)

    prod_rows = [p.to_summary_dict() for p in extracted_products]
    if prod_rows:
        headers = list(prod_rows[0].keys())
        data_matrix = [headers] + [[r.get(h, "") for h in headers] for r in prod_rows]
        prod_ws.clear()
        prod_ws.update("A1", data_matrix)
        print(f"[Sheets] Updated 'Products' tab with {len(prod_rows)} items.")

    # 4. Update 'Variants' sheet
    try:
        var_ws = sh.worksheet("Variants")
    except gspread.exceptions.WorksheetNotFound:
        var_ws = sh.add_worksheet(title="Variants", rows=5000, cols=15)

    variant_rows = []
    for p in extracted_products:
        if p.variants:
            for v in p.variants:
                variant_rows.append([
                    p.url,
                    p.title,
                    p.brand or "",
                    p.mpn or "",
                    v.sku or "",
                    v.upc or v.gtin or "",
                    v.size or "",
                    v.color or "",
                    v.price if v.price is not None else "",
                    v.regular_price if v.regular_price is not None else "",
                    p.currency,
                    "InStock" if v.in_stock else "OutOfStock",
                    "Yes" if v.in_stock else "No",
                    v.image_url or ""
                ])
        else:
            variant_rows.append([
                p.url, p.title, p.brand or "", p.mpn or "", p.sku or "",
                p.upc or p.gtin or "", ", ".join(p.sizes), ", ".join(p.colors),
                p.price if p.price is not None else "", "", p.currency,
                p.stock_status, "Yes" if p.in_stock else "No", p.images[0] if p.images else ""
            ])

    var_headers = [
        "Product URL", "Product Title", "Brand", "Style / MPN",
        "Variant SKU", "UPC / GTIN", "Size", "Color",
        "Price", "Regular Price", "Currency", "Stock Status",
        "In Stock", "Image URL"
    ]
    var_matrix = [var_headers] + variant_rows
    var_ws.clear()
    var_ws.update("A1", var_matrix)
    print(f"[Sheets] Updated 'Variants' tab with {len(variant_rows)} variant rows.")

    # Also save local backup Excel file
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    os.makedirs("output", exist_ok=True)
    excel_path = f"output/scraped_products_{timestamp}.xlsx"
    ProductExporter.to_excel(extracted_products, excel_path)
    print(f"[Backup] Saved Excel backup to {excel_path}")


if __name__ == "__main__":
    run_sheets_scraper()
