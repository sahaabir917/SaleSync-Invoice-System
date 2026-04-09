"""
Loads all CSV data files into memory at startup.
Builds in-memory indexes for fast lookup and search.
Applies data quality fixes at load time.
"""
import os
import re
import logging
import pandas as pd

logger = logging.getLogger(__name__)

# In-memory stores
_data = {
    "categories": [],
    "brands": [],
    "dates": [],
    "currencies": ["USD", "GBP", "INR", "AED", "AUD", "CAD", "SGD"],
    "customers_df": None,
    "products_df": None,
    "price_by_product": {},   # product_id -> {unit_price, unit_price_currency}
}

# Fast lookup indexes
_indexes = {
    "customers_by_id": {},
    "products_by_id": {},
    "products_by_category": {},
    "products_by_brand": {},
}

# Category code normalization map (handles inconsistencies in brands.csv)
_CATEGORY_CODE_MAP = {
    "ce": "ce", "electronics": "ce",
    "app": "app", "apparel": "app",
    "hnk": "hnk", "home & kitchen": "hnk", "home": "hnk",
    "bpc": "bpc", "beauty & personal care": "bpc", "beauty": "bpc",
    "bks": "bks", "books": "bks",
    "grcy": "grcy", "grocery": "grcy",
    "toy": "toy", "toys": "toy", "toys & games": "toy",
    "spt": "spt", "sports": "spt", "sports & outdoors": "spt",
}


def _normalize_category_code(code: str) -> str:
    if pd.isna(code):
        return ""
    code = str(code).strip().lower()
    return _CATEGORY_CODE_MAP.get(code, code)


def _clean_brand_code(code: str) -> str:
    if pd.isna(code):
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", str(code).strip()).upper()


def load_all(data_dir: str):
    """Load all CSVs from data_dir into memory. Call once at app startup."""
    _load_categories(os.path.join(data_dir, "category", "category.csv"))
    _load_brands(os.path.join(data_dir, "brands", "brands.csv"))
    _load_dates(os.path.join(data_dir, "date", "date.csv"))
    _load_customers(os.path.join(data_dir, "customers", "customers.csv"))
    _load_products(os.path.join(data_dir, "products", "products.csv"))
    # Load order_items to build price lookup (best-known price per product)
    for fname in sorted(os.listdir(data_dir)):
        if fname.startswith("order_items") and fname.endswith(".csv"):
            _load_order_items_prices(os.path.join(data_dir, fname))
            break
    logger.info(
        "Data loaded: %d categories, %d brands, %d dates, %d customers, %d products",
        len(_data["categories"]),
        len(_data["brands"]),
        len(_data["dates"]),
        len(_data["customers_df"]),
        len(_data["products_df"]),
    )


def _load_categories(path: str):
    df = pd.read_csv(path, dtype=str)
    df.columns = df.columns.str.strip()
    df["category_code"] = df["category_code"].str.strip().str.lower()
    df["category_name"] = df["category_name"].str.strip()
    _data["categories"] = df.to_dict(orient="records")


def _load_brands(path: str):
    df = pd.read_csv(path, dtype=str)
    df.columns = df.columns.str.strip()
    df["brand_code"] = df["brand_code"].apply(_clean_brand_code)
    df["brand_name"] = df["brand_name"].str.strip()
    df["category_code"] = df["category_code"].apply(_normalize_category_code)
    df = df[df["brand_code"] != ""].drop_duplicates(subset=["brand_code"])
    _data["brands"] = df.to_dict(orient="records")


def _load_dates(path: str):
    df = pd.read_csv(path, dtype=str)
    df.columns = df.columns.str.strip()
    df["date"] = df["date"].str.strip()
    df["day_name"] = df["day_name"].str.strip().str.capitalize()
    df = df.drop_duplicates(subset=["date"])
    df["_parsed"] = pd.to_datetime(df["date"], format="%d-%m-%Y", errors="coerce")
    df = df.dropna(subset=["_parsed"]).sort_values("_parsed")
    df["display"] = df["_parsed"].dt.strftime("%A, %d %b %Y")
    df = df.drop(columns=["_parsed"])
    _data["dates"] = df.to_dict(orient="records")


def _load_customers(path: str):
    df = pd.read_csv(path, dtype=str, low_memory=False)
    df.columns = df.columns.str.strip()
    df["customer_id"] = df["customer_id"].str.strip()
    df["country"] = df["country"].str.strip()
    df["state"] = df["state"].str.strip()
    df["country_code"] = df["country_code"].str.strip()
    df["phone"] = df["phone"].str.replace(r"\.0$", "", regex=True)
    df = df.drop_duplicates(subset=["customer_id"])
    _data["customers_df"] = df
    _indexes["customers_by_id"] = df.set_index("customer_id").to_dict(orient="index")


def _load_order_items_prices(path: str):
    """Build product_id → {unit_price, unit_price_currency} from order_items CSV."""
    df = pd.read_csv(path, dtype=str, low_memory=False)
    df.columns = df.columns.str.strip()
    df["product_id"] = df["product_id"].str.strip()
    # Clean unit_price: strip $ prefix, keep numeric only
    df["unit_price"] = (
        df["unit_price"].str.replace(r"[^\d.]", "", regex=True).str.strip()
    )
    df["unit_price_currency"] = df["unit_price_currency"].str.strip()
    # Drop rows with non-numeric price
    df = df[pd.to_numeric(df["unit_price"], errors="coerce").notna()]
    df["unit_price"] = pd.to_numeric(df["unit_price"])
    # Keep last known price per product (last row wins)
    for _, row in df[["product_id", "unit_price", "unit_price_currency"]].iterrows():
        _data["price_by_product"][row["product_id"]] = {
            "unit_price": float(row["unit_price"]),
            "unit_price_currency": row["unit_price_currency"],
        }
    logger.info("Price lookup built: %d products with known prices", len(_data["price_by_product"]))


def _load_products(path: str):
    df = pd.read_csv(path, dtype=str, low_memory=False)
    df.columns = df.columns.str.strip()
    df["product_id"] = df["product_id"].str.strip()
    df["sku"] = df["sku"].str.strip()
    df["brand_code"] = df["brand_code"].apply(_clean_brand_code)
    df["category_code"] = df["category_code"].str.strip().str.lower()
    df["color"] = df["color"].str.strip().fillna("")
    df["size"] = df["size"].str.strip().fillna("")
    df["material"] = df["material"].str.strip().fillna("")
    df["weight_grams"] = df["weight_grams"].str.replace(r"g$", "", regex=True).str.strip()
    for col in ["length_cm", "width_cm", "height_cm"]:
        df[col] = df[col].str.replace(",", ".", regex=False).str.strip()
    _data["products_df"] = df
    _indexes["products_by_id"] = df.set_index("product_id").to_dict(orient="index")
    for cat_code, group in df.groupby("category_code"):
        _indexes["products_by_category"][cat_code] = group.to_dict(orient="records")
    for brand_code, group in df.groupby("brand_code"):
        _indexes["products_by_brand"][brand_code] = group.to_dict(orient="records")


# ---------------------------------------------------------------------------
# Public query functions
# ---------------------------------------------------------------------------

def get_categories():
    return _data["categories"]


def get_brands(category_code: str = None):
    brands = _data["brands"]
    if category_code:
        brands = [b for b in brands if b["category_code"] == category_code.lower()]
    return brands


def get_dates():
    return _data["dates"]


def get_currencies():
    return _data["currencies"]


def search_customers(query: str, limit: int = 20):
    if not query or len(query) < 2:
        return []
    df = _data["customers_df"]
    q = query.strip().upper()
    mask = (
        df["customer_id"].str.upper().str.contains(q, na=False)
        | df["country"].str.upper().str.contains(q, na=False)
        | df["state"].str.upper().str.contains(q, na=False)
    )
    return df[mask].head(limit).to_dict(orient="records")


def get_customer(customer_id: str):
    return _indexes["customers_by_id"].get(customer_id.strip())


def get_products(category_code: str = None, brand_code: str = None, query: str = None, limit: int = 100):
    df = _data["products_df"]
    if category_code:
        df = df[df["category_code"] == category_code.lower()]
    if brand_code:
        df = df[df["brand_code"] == brand_code.upper()]
    if query and len(query) >= 2:
        q = query.strip().upper()
        df = df[
            df["product_id"].str.upper().str.contains(q, na=False)
            | df["sku"].str.upper().str.contains(q, na=False)
            | df["color"].str.upper().str.contains(q, na=False)
        ]
    return df.head(limit).to_dict(orient="records")


def get_product(product_id: str):
    row = _indexes["products_by_id"].get(product_id.strip())
    if row:
        # Attach last-known price if available
        price_info = _data["price_by_product"].get(product_id.strip(), {})
        return {**row, **price_info}
    return None


def get_health():
    return {
        "status": "ok",
        "customers": len(_data["customers_df"]) if _data["customers_df"] is not None else 0,
        "products": len(_data["products_df"]) if _data["products_df"] is not None else 0,
        "brands": len(_data["brands"]),
        "categories": len(_data["categories"]),
        "dates": len(_data["dates"]),
    }
