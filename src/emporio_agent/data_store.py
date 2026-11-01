"""Loads the store CSVs into typed, in-memory objects.

The dataset is small (65 products, 20 orders), so plain Python objects are enough.
Tools read from here with typed parameters; the LLM never queries the data directly.
"""

import csv
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path

from emporio_agent.config import DATA_DIR

CSV_PREFIX = "desafio_tecnico_ai_eng - "

CENT = Decimal("0.01")


def to_money(value: str | Decimal) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def format_brl(value: Decimal) -> str:
    """Formats 11499 as 'R$ 11.499,00'."""
    us_style = f"{to_money(value):,.2f}"
    return "R$ " + us_style.replace(",", "_").replace(".", ",").replace("_", ".")


def normalize(text: str) -> str:
    """Lowercase, strip accents and turn punctuation into spaces, for tolerant search."""
    decomposed = unicodedata.normalize("NFKD", text)
    no_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", no_accents.lower()).split())


def digits_only(text: str) -> str:
    return re.sub(r"\D", "", text)


@dataclass(frozen=True)
class Category:
    id: int
    name: str
    description: str


@dataclass(frozen=True)
class Promotion:
    id: int
    product_id: int
    discount_percent: int
    description: str


@dataclass(frozen=True)
class Product:
    id: int
    name: str
    category_id: int
    description: str
    price: Decimal
    stock: int
    status: str
    specs: dict
    promotion: Promotion | None = None

    @property
    def availability(self) -> str:
        """Single source of truth for whether a product can be sold.

        Status wins over stock: a `coming_soon` item with units in stock is still not for sale.
        """
        if self.status == "discontinued":
            return "discontinued"
        if self.status == "coming_soon":
            return "coming_soon"
        if self.stock <= 0:
            return "out_of_stock"
        return "available"

    @property
    def final_price(self) -> Decimal:
        if self.promotion is None:
            return self.price
        return to_money(self.price * (100 - self.promotion.discount_percent) / 100)


@dataclass(frozen=True)
class Customer:
    id: int
    name: str
    phone: str
    email: str


@dataclass(frozen=True)
class Order:
    id: int
    customer_id: int
    order_date: date
    status: str
    total: Decimal
    payment_method: str
    tracking_code: str | None
    estimated_delivery: date | None
    notes: str | None
    items: list[tuple[int, int]] = field(default_factory=list)  # (product_id, quantity)


@dataclass(frozen=True)
class Store:
    categories: dict[int, Category]
    products: dict[int, Product]
    customers: dict[int, Customer]
    orders: dict[int, Order]


def _read(data_dir: Path, table: str) -> list[dict[str, str]]:
    with open(data_dir / f"{CSV_PREFIX}{table}.csv", encoding="utf-8", newline="") as f:
        return [{k: v.strip() for k, v in row.items()} for row in csv.DictReader(f)]


def _active_promotions(rows: list[dict[str, str]]) -> dict[int, Promotion]:
    """Only `is_active = 1` promotions exist for the agent; expired ones are never offered.

    If a product ever had two active promotions, the larger discount would apply
    (promotions are not cumulative, policy 6.2). The provided data has at most one.
    """
    active: dict[int, Promotion] = {}
    for row in rows:
        if row["is_active"] != "1":
            continue
        promo = Promotion(
            id=int(row["promotion_id"]),
            product_id=int(row["product_id"]),
            discount_percent=int(row["discount_percent"]),
            description=row["description"],
        )
        current = active.get(promo.product_id)
        if current is None or promo.discount_percent > current.discount_percent:
            active[promo.product_id] = promo
    return active


def load_store(data_dir: Path = DATA_DIR) -> Store:
    categories = {
        int(r["category_id"]): Category(int(r["category_id"]), r["name"], r["description"])
        for r in _read(data_dir, "categories")
    }
    promotions = _active_promotions(_read(data_dir, "promotions"))

    products = {}
    for r in _read(data_dir, "products"):
        pid = int(r["product_id"])
        products[pid] = Product(
            id=pid,
            name=r["name"],
            category_id=int(r["category_id"]),
            description=r["description"],
            price=to_money(r["price_brl"]),
            stock=int(r["stock_quantity"]),
            status=r["status"],
            specs=json.loads(r["specs"]) if r["specs"] else {},
            promotion=promotions.get(pid),
        )

    customers = {
        int(r["customer_id"]): Customer(int(r["customer_id"]), r["name"], r["phone"], r["email"])
        for r in _read(data_dir, "customers")
    }

    items: dict[int, list[tuple[int, int]]] = {}
    for r in _read(data_dir, "order_items"):
        items.setdefault(int(r["order_id"]), []).append((int(r["product_id"]), int(r["quantity"])))

    orders = {}
    for r in _read(data_dir, "orders"):
        oid = int(r["order_id"])
        orders[oid] = Order(
            id=oid,
            customer_id=int(r["customer_id"]),
            order_date=date.fromisoformat(r["order_date"]),
            status=r["status"],
            total=to_money(r["total_brl"]),
            payment_method=r["payment_method"],
            tracking_code=r["tracking_code"] or None,
            estimated_delivery=(
                date.fromisoformat(r["estimated_delivery"]) if r["estimated_delivery"] else None
            ),
            notes=r["notes"] or None,
            items=items.get(oid, []),
        )

    return Store(categories, products, customers, orders)


@lru_cache(maxsize=1)
def get_store() -> Store:
    return load_store()
