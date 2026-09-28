# 🕷️ Scheels E-Commerce Product Scraper (GitHub Actions Automation)

Automated Scheels scraper that runs on a schedule via GitHub Actions, reads input URLs from Google Sheets, extracts complete product details with all variations (SKU, UPC, Size, Color, Price, Stock), and updates Google Sheets directly.

---

## 📁 Repository Structure

```
├── .github/
│   └── workflows/
│       └── daily_scraper.yml    # GitHub Actions automation workflow
├── parsers/
│   ├── json_ld_parser.py        # Schema.org & ProductGroup parser
│   └── dom_parser.py            # DOM swatch & fallback parser
├── extractor.py                 # Extraction orchestrator
├── fetcher.py                   # Playwright & TLS fingerprint fetcher
├── models.py                    # Product data models
├── exporter.py                  # Excel / CSV / JSON exporter
├── sheets_runner.py             # Google Sheets reader & updater
└── requirements.txt             # Python dependencies
```

---

## 🚀 Setup Guide (3 Steps)

### Step 1: Create Google Cloud Service Account (Free)
1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project (e.g. `scheels-scraper`).
3. Enable **Google Sheets API** and **Google Drive API**.
4. Go to **APIs & Services** -> **Credentials** -> **Create Credentials** -> **Service Account**.
5. Click on the created Service Account -> **Keys** tab -> **Add Key** -> **Create new key (JSON)**.
6. A JSON file will be downloaded.

### Step 2: Share Google Sheet with the Service Account
1. Create a Google Sheet named: `Scheels_Products`.
2. In the first tab named `Input_URLs`, put your product URLs in **Column A** (Row 1 is header `Product_URL`).
3. Click **Share** on the Google Sheet and give **Editor** access to the `client_email` from your downloaded JSON file.

### Step 3: Add GitHub Secret & Push Code
1. Create a **Private** Repository on GitHub.
2. Go to **Settings** -> **Secrets and variables** -> **Actions** -> **New repository secret**.
   - **Name**: `GCP_SA_KEY`
   - **Secret**: Copy & paste the entire content of the downloaded Service Account JSON file.
3. Push this project code to your repository.

---

## ⏰ Schedule & Manual Trigger
- **Automatic**: Runs daily at 9:30 PM IST (4:00 PM UTC) via GitHub Actions.
- **Manual**: Go to **Actions** tab in your GitHub repository -> Select **🕷️ Scheels Daily Product Scraper** -> Click **Run workflow**.
