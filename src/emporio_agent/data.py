"""Loading, cleaning and validation of the store CSVs (see docs/DATA_NOTES.md).

The original files are read as delivered; every fix happens in memory and every data-quality
finding is recorded in `StoreData.warnings` instead of being silently corrected.
"""

import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

import pandas as pd

from emporio_agent.config import DATA_DIR

logger = logging.getLogger(__name__)

# Brands that appear in the catalog (names and descriptions). Used to detect descriptions that
# contradict the product name — e.g. "Music Man Bass 1X" described as a "Fender Jazz Bass".
KNOWN_BRANDS = (
    "Crafter", "Fender", "Giannini", "Gibson", "Ibanez", "Kala", "Kalani", "Korg", "Martin",
    "Music Man", "Nord", "Ohana", "Pearl", "PRS", "Roland", "Rozini", "Shelby", "Tagima",
    "Takamine", "Tama", "Taylor", "Yamaha",
)  # fmt: skip


def normalize(text: str) -> str:
    """Lowercase, accent-free text for matching ("Violões" -> "violoes")."""
    decomposed = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower().strip()


def phone_digits(phone: str) -> str:
    """Digits only, without the country code: '+55 (67) 99812-3456' -> '67998123456'."""
    digits = re.sub(r"\D", "", str(phone))
    return digits[2:] if len(digits) > 11 and digits.startswith("55") else digits


def brands_in(text: str) -> set[str]:
    norm = f" {normalize(text)} "
    return {b for b in KNOWN_BRANDS if re.search(rf"\b{re.escape(normalize(b))}\b", norm)}


@dataclass(frozen=True)
class StoreData:
    products: pd.DataFrame
    categories: pd.DataFrame
    promotions: pd.DataFrame
    orders: pd.DataFrame
    order_items: pd.DataFrame
    customers: pd.DataFrame
    warnings: list[str] = field(default_factory=list)

    def product(self, product_id: int) -> pd.Series:
        return self.products.loc[product_id]

    def active_promotions(self, product_id: int) -> pd.DataFrame:
        promos = self.promotions
        return promos[(promos["product_id"] == product_id) & promos["is_active"]]


def _indexed(df: pd.DataFrame, key: str) -> pd.DataFrame:
    """Index by `key` while keeping it as a column (unnamed index avoids merge ambiguity)."""
    indexed = df.set_index(key, drop=False)
    indexed.index.name = None
    return indexed


def _read(data_dir: Path, table: str) -> pd.DataFrame:
    matches = sorted(data_dir.glob(f"*{table}.csv"))
    if len(matches) != 1:
        raise FileNotFoundError(f"Expected exactly one '*{table}.csv' in {data_dir}, got {matches}")
    return pd.read_csv(matches[0], encoding="utf-8")


def _load_products(data_dir: Path, categories: pd.DataFrame, warnings: list[str]) -> pd.DataFrame:
    df = _read(data_dir, "products")
    df["name"] = df["name"].str.strip()
    df["description"] = df["description"].fillna("").str.strip()
    df["status"] = df["status"].str.strip().str.lower()
    df["price"] = df["price_brl"].map(lambda v: Decimal(str(v)))
    df["specs"] = df["specs"].map(lambda s: json.loads(s) if isinstance(s, str) and s else {})
    df["created_at"] = pd.to_datetime(df["created_at"]).dt.date
    df = df.merge(
        categories[["category_id", "name"]].rename(columns={"name": "category"}),
        on="category_id",
        how="left",
    )

    df["name_norm"] = df["name"].map(normalize)
    df["description_reliable"] = True
    for idx, row in df.iterrows():
        foreign = brands_in(row["description"]) - brands_in(row["name"])
        if foreign:
            df.at[idx, "description_reliable"] = False
            warnings.append(
                f"product {row['product_id']} '{row['name']}': description mentions "
                f"{sorted(foreign)} — description hidden, name/specs are authoritative"
            )
        if row["status"] == "discontinued" and row["stock_quantity"] > 0:
            warnings.append(
                f"product {row['product_id']} is discontinued but has stock "
                f"{row['stock_quantity']} — treated as not for sale"
            )

    empty = set(categories["name"]) - set(df["category"].dropna())
    for category in sorted(empty):
        warnings.append(f"category '{category}' has no products in the catalog")
    return _indexed(df, "product_id").sort_index()


def _load_promotions(data_dir: Path, products: pd.DataFrame, warnings: list[str]) -> pd.DataFrame:
    df = _read(data_dir, "promotions")
    df["description"] = df["description"].str.strip()
    df["is_active"] = df["is_active"].astype(int) == 1
    unknown = df[~df["product_id"].isin(products.index)]
    for _, row in unknown.iterrows():
        warnings.append(f"promotion {row['promotion_id']} references unknown product")
    active_per_product = df[df["is_active"]].groupby("product_id").size()
    for product_id in active_per_product[active_per_product > 1].index:
        warnings.append(f"product {product_id} has several active promotions — best one applies")
    return df


def _load_orders(
    data_dir: Path, products: pd.DataFrame, warnings: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    orders = _read(data_dir, "orders")
    items = _read(data_dir, "order_items")

    for column in ("order_date", "estimated_delivery"):
        orders[column] = pd.to_datetime(orders[column]).dt.date
    orders["status"] = orders["status"].str.strip().str.lower()
    orders["total"] = orders["total_brl"].map(lambda v: Decimal(str(v)))
    for column in ("tracking_code", "notes", "payment_method"):
        orders[column] = orders[column].astype(object).where(orders[column].notna(), None)

    items = items.merge(
        products[["product_id", "name", "price"]], on="product_id", how="left", validate="m:1"
    )
    items["line_total"] = items["price"] * items["quantity"]
    items_total = items.groupby("order_id")["line_total"].sum()
    for _, order in orders.iterrows():
        expected = items_total.get(order["order_id"])
        if expected is not None and expected != order["total"]:
            warnings.append(
                f"order {order['order_id']}: recorded total {order['total']} differs from "
                f"items x current prices {expected} — the recorded total is reported"
            )
    return _indexed(orders, "order_id"), items


def _load_customers(data_dir: Path, warnings: list[str]) -> pd.DataFrame:
    df = _read(data_dir, "customers")
    df["name"] = df["name"].str.strip()
    df["email"] = df["email"].str.strip().str.lower()
    df["phone_digits"] = df["phone"].map(phone_digits)
    for column in ("email", "phone_digits"):
        duplicated = df[df[column].duplicated(keep=False)]
        for value, group in duplicated.groupby(column):
            ids = group["customer_id"].tolist()
            warnings.append(f"customers {ids} share the same {column} '{value}'")
    return _indexed(df, "customer_id")


def load_store_data(data_dir: Path = DATA_DIR) -> StoreData:
    warnings: list[str] = []
    categories = _read(data_dir, "categories")
    products = _load_products(data_dir, categories, warnings)
    promotions = _load_promotions(data_dir, products, warnings)
    orders, order_items = _load_orders(data_dir, products, warnings)
    customers = _load_customers(data_dir, warnings)
    for warning in warnings:
        logger.info("data quality: %s", warning)
    return StoreData(
        products=products,
        categories=categories,
        promotions=promotions,
        orders=orders,
        order_items=order_items,
        customers=customers,
        warnings=warnings,
    )
