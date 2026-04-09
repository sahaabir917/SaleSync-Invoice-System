# Invoice Web Platform — Project Plan

## Overview

A web platform that reads e-commerce CSV data and lets a user compose a single-item invoice, generate a styled PDF, and automatically upload it to Google Drive.

---

## Tech Stack

| Layer          | Technology                      | Reason                                                                      |
| -------------- | ------------------------------- | --------------------------------------------------------------------------- |
| Backend        | Python + Flask                  | pandas handles 300k CSV rows at startup; WeasyPrint renders real CSS to PDF |
| Frontend       | HTML + Alpine.js (CDN)          | Single-page reactive form, no build step needed                             |
| PDF Generation | WeasyPrint (server-side)        | Full CSS layout support — gradients, tables, Google Fonts                   |
| Google Drive   | Service Account (JSON key)      | Zero OAuth redirect flow; set once, works permanently                       |
| Data           | pandas in-memory + dict indexes | Sub-50ms customer search on 300k rows                                       |

---

## Project Structure

```
invoice-platform/
├── app.py                     ← Flask routes + startup data loading
├── config.py                  ← env var loader
├── requirements.txt
├── .env                       ← environment variables (gitignored)
├── .env.example
├── .gitignore
├── README.md
├── services/
│   ├── data_loader.py         ← CSV ingestion, data quality fixes, in-memory indexes
│   ├── pdf_generator.py       ← WeasyPrint rendering + total price calculation
│   └── drive_uploader.py      ← Google Drive service account upload
├── templates/
│   ├── invoice.html           ← Jinja2 PDF template (A4, indigo theme)
│   └── index.html             ← Main web UI
├── static/
│   ├── css/style.css
│   └── js/app.js              ← Alpine.js logic
├── credentials/
│   └── service_account.json   ← Google service account key (gitignored)
└── generated_pdfs/            ← Local copy of every generated PDF
```

---

## Data Sources

All data loaded from `c:/Users/sahaa/OneDrive/Desktop/Extenal datasource project/`

| File                      | Records | Used For                                        |
| ------------------------- | ------- | ----------------------------------------------- |
| `category/category.csv`   | 10      | Category dropdown                               |
| `brands/brands.csv`       | 52      | Brand dropdown (filtered by category)           |
| `date/date.csv`           | 95      | Date dropdown                                   |
| `customers/customers.csv` | 300,000 | Customer autocomplete search                    |
| `products/products.csv`   | 50,000  | Product dropdown (filtered by category + brand) |

### Data Quality Fixes Applied at Load Time

| File            | Issue                                                               | Fix                     |
| --------------- | ------------------------------------------------------------------- | ----------------------- |
| `brands.csv`    | Leading/trailing spaces in names                                    | `str.strip()`           |
| `brands.csv`    | Uppercase category codes (`CE`, `APP`) vs lowercase everywhere else | Normalize to lowercase  |
| `brands.csv`    | Inconsistent codes (`BOOKS`/`BKS`, `GROCERY`/`GRCY`, `TOY`/`TOYS`)  | Map to canonical code   |
| `brands.csv`    | Special chars in brand codes (`VOLT@`, `GLOW*`)                     | Strip non-alphanumeric  |
| `date.csv`      | Last 3 rows are duplicates with wrong quarter                       | Deduplicate, keep first |
| `products.csv`  | `weight_grams` has `g` suffix (`305g`)                              | Strip suffix            |
| `products.csv`  | Comma decimal separator in `length_cm` (`"22,2"`)                   | Normalize to `.`        |
| `customers.csv` | Phone in scientific notation (`917280033536.0`)                     | Strip `.0` suffix       |

---

## Data Model (Star Schema)

```
  CUSTOMERS ──────────┐
                       │
  CATEGORIES ──┐       ▼
               ├──► PRODUCTS ──► ORDER_ITEMS (invoice fact)
  BRANDS ──────┘                    │
                                    ▼
                                  DATE
```

**Invoice fields captured:**
`dt`, `order_ts`, `customer_id`, `order_id`, `item_seq`, `product_id`,
`quantity`, `unit_price_currency`, `unit_price`, `discount_pct`, `tax_amount`,
`channel`, `coupon_code`, **`total_price`** (computed)

---

## API Endpoints

### Static (loaded once on page load)

| Method | Endpoint                      | Returns                                       |
| ------ | ----------------------------- | --------------------------------------------- |
| GET    | `/api/categories`             | 10 category records                           |
| GET    | `/api/brands?category={code}` | Brands, optionally filtered by category       |
| GET    | `/api/dates`                  | 95 deduplicated, sorted dates                 |
| GET    | `/api/currencies`             | `["USD","GBP","INR","AED","AUD","CAD","SGD"]` |

### Dynamic Search

| Method | Endpoint                                               | Notes                                      |
| ------ | ------------------------------------------------------ | ------------------------------------------ |
| GET    | `/api/customers/search?q={term}&limit=20`              | Debounced autocomplete, min 2 chars        |
| GET    | `/api/customers/{customer_id}`                         | Single customer record                     |
| GET    | `/api/products?category={code}&brand={code}&limit=100` | Cascading filter                           |
| GET    | `/api/products/{product_id}`                           | Single product (auto-fills SKU/color/size) |

### Invoice

| Method | Endpoint                | Returns                                                  |
| ------ | ----------------------- | -------------------------------------------------------- |
| POST   | `/api/invoice/preview`  | Rendered HTML (open in new tab)                          |
| POST   | `/api/invoice/generate` | PDF binary download                                      |
| POST   | `/api/invoice/upload`   | Generate PDF → upload to Drive → `{drive_url, filename}` |

### Utility

| Method | Endpoint                   | Returns                        |
| ------ | -------------------------- | ------------------------------ |
| GET    | `/api/health`              | Row counts for all loaded data |
| GET    | `/api/config/drive-status` | `{connected: bool}`            |

---

## Total Price Formula

```
subtotal       = quantity × unit_price
discount       = subtotal × (discount_pct / 100)
total_price    = subtotal − discount + tax_amount
```

---

## Frontend UX Flow

```
1. Select Date ──────────────────────────────── (dropdown, 95 dates)
2. Fill Order ID, Item Seq, Channel, Coupon
3. Search Customer ──────────────────────────── (autocomplete, 300k records)
     └─ type ≥ 2 chars → debounced 300ms → API search → select → info card shown
4. Select Category ──────────────────────────── (10 options)
     └─ triggers brand list reload
5. Select Brand ─────────────────────────────── (filtered by category)
     └─ triggers product list reload
6. Select Product ───────────────────────────── (filtered by category + brand)
     └─ auto-fills SKU / color / size / material info card
7. Enter Quantity, Currency, Unit Price, Discount %, Tax
     └─ total price updates live
8. Action buttons:
     ├─ Preview      → HTML in new tab
     ├─ Download PDF → PDF file download
     └─ Upload       → PDF generated + uploaded to Drive → Drive link shown
```

---

## Invoice PDF Design

**Page:** A4 portrait, 20mm margins, white background

**Sections (top to bottom):**

1. **Header** — Company name (left) + "INVOICE" wordmark in indigo (right), order number, date, channel badge
2. **Gradient divider** — indigo → transparent
3. **Two-column info block** — "Bill To" (customer details) | "Order Details" (order ID, timestamp, coupon badge)
4. **Line items table** — indigo header row, alternating gray rows; columns: Product ID, SKU, Category/Brand, Color/Size, Qty, Unit Price, Discount, Tax, Line Total
5. **Pricing summary** (right-aligned box) — Subtotal → Discount → Tax → **TOTAL** (indigo gradient band)
6. **Thank you note** — left-bordered indigo accent card
7. **Footer** — company address (left) | generation timestamp + filename (right)

**Color scheme:** Deep indigo `#4F46E5` primary · White background · Slate gray `#F8FAFC` table stripes · Green `#059669` for discounts/coupons

**Typography:** Inter (body) · Poppins (headings) — loaded via Google Fonts

---

## Google Drive Setup (one-time)

1. Google Cloud Console → enable **Google Drive API**
2. IAM → Service Accounts → Create → download JSON key → save as `credentials/service_account.json`
3. In Google Drive: create folder **"Invoices"** → share with service account email (Editor)
4. Copy folder ID from Drive URL → set `GOOGLE_DRIVE_FOLDER_ID` in `.env`

**PDF filename format:** `Invoice-{order_id}-{item_seq}.pdf`

---

## Environment Variables

```bash
FLASK_PORT=5000
FLASK_SECRET_KEY=change-me

DATA_DIR=c:/Users/sahaa/OneDrive/Desktop/Extenal datasource project

GOOGLE_SERVICE_ACCOUNT_FILE=credentials/service_account.json
GOOGLE_DRIVE_FOLDER_ID=your-folder-id

COMPANY_NAME=Your Company Name
COMPANY_ADDRESS=123 Main Street, City, Country
```

---

## Dependencies

```
flask>=3.0.0
pandas>=2.2.0
weasyprint>=62.0
google-api-python-client>=2.100.0
google-auth>=2.23.0
python-dotenv>=1.0.0
```

> **Windows note:** WeasyPrint requires the GTK3 runtime.
> Download: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases

---

## Implementation Phases

| Phase              | What was built                                                              |
| ------------------ | --------------------------------------------------------------------------- |
| **1 — Foundation** | Project scaffold, `config.py`, `requirements.txt`, `.env`                   |
| **2 — Data Layer** | `data_loader.py` — CSV ingestion, all data quality fixes, in-memory indexes |
| **3 — API**        | `app.py` — all Flask routes (static, search, invoice endpoints)             |
| **4 — PDF**        | `invoice.html` (Jinja2 template) + `pdf_generator.py` (WeasyPrint)          |
| **5 — Drive**      | `drive_uploader.py` — service account auth + file upload                    |
| **6 — Frontend**   | `index.html` + `style.css` + `app.js` — full Alpine.js reactive UI          |

---

## Running the App

```bash
pip install -r requirements.txt
python app.py
# → http://localhost:5000
```
