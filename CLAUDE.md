# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **CSV-based external data source** for an e-commerce analytics system. It contains dimensional and transactional data designed for OLAP/BI workloads (data warehousing, ETL pipelines, BI tool integration).

There are no build tools, scripts, or executable code — this is a data-only repository.

## Data Model (Star Schema)

The data follows a star schema with one fact table and several dimension tables:

**Fact Table**
- `order_items_2025-08-01.csv` — Order line items with pricing, discounts, taxes, and channel info

**Dimension Tables**
- `customers/customers.csv` — 300,000 customer records with geographic data
- `products/products.csv` — 50,000 products with physical specs and ratings
- `brands/brands.csv` — 52 brands with category association
- `category/category.csv` — 10 product categories
- `date/date.csv` — Date dimension covering Q3–Q4 2025 (Aug 1 – Oct 31)

**Key Relationships**
- `order_items.customer_id` → `customers.customer_id`
- `order_items.product_id` → `products.product_id`
- `products.brand_code` → `brands.brand_code`
- `products.category_code` → `categories.category_code`
- `brands.category_code` → `categories.category_code`
- `order_items.dt` → `date.date`

## Schema Reference

| Table | Key Columns |
|---|---|
| order_items | `dt`, `order_ts`, `customer_id`, `order_id`, `item_seq`, `product_id`, `quantity`, `unit_price_currency`, `unit_price`, `discount_pct`, `tax_amount`, `channel`, `coupon_code` |
| customers | `customer_id` (format: CUST000000000001), `phone`, `country_code`, `country`, `state` |
| products | `product_id`, `sku` (format: BRAND-CAT-NNNNN), `category_code`, `brand_code`, `color`, `size`, `material`, `weight_grams`, `length_cm`, `width_cm`, `height_cm`, `rating_count` |
| brands | `brand_code`, `brand_name`, `category_code` |
| category | `category_code`, `category_name` |
| date | `date`, `year`, `day_name`, `quarter`, `week_of_year` |

## Known Data Quality Issues

- `order_items.quantity` has some non-numeric values (e.g., `"Two"` instead of `2`)
- `customers.phone` is stored in scientific notation (e.g., `917280033536.0`)
- `products.rating_count` contains negative values
- `date` dimension has some duplicate dates with inconsistent quarter/formatting values
- Multi-currency orders: USD, GBP, INR, AED, AUD, CAD, SGD (no normalized amount column)

## Business Context

- **Channels**: `web`, `app`
- **Coupon codes present**: e.g., `FEST20`, `SAVE50`
- **Geographic scope**: International (India, Australia, and others)
- **Categories**: Electronics, Apparel, Home & Kitchen, Beauty & Personal Care, Books, Grocery, Toys & Games, Sports & Outdoors
- **Data vintage**: Transactions from 2025-08-01; date dimension spans Aug–Oct 2025
