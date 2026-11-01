"""Tools the agent can call. Each one is a plain function returning JSON-serializable data.

All business data (prices, stock, promotions, orders, dates) is computed here, so the
model only has to choose a tool and phrase the answer.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from emporio_agent import clock
from emporio_agent.data_store import (
    Customer,
    Order,
    Product,
    digits_only,
    format_brl,
    get_store,
    normalize,
)

STOPWORDS = {"de", "da", "do", "das", "dos", "para", "com", "e", "o", "a", "os", "as", "um", "uma"}

AVAILABILITY_LABELS = {
    "available": "disponível",
    "out_of_stock": "esgotado no momento",
    "discontinued": "fora de linha (não faz mais parte do catálogo)",
    "coming_soon": "em breve (ainda não disponível para venda)",
}

MAX_RESULTS = 20
ALTERNATIVES_PRICE_RANGE = Decimal("0.30")  # +/- 30% of the original product's price


# --- Product helpers -----------------------------------------------------------------


def _category_name(product: Product) -> str:
    return get_store().categories[product.category_id].name


def _product_summary(product: Product) -> dict:
    summary = {
        "product_id": product.id,
        "name": product.name,
        "category": _category_name(product),
        "availability": product.availability,
        "availability_label": AVAILABILITY_LABELS[product.availability],
        "price": format_brl(product.final_price),
    }
    if product.availability == "available":
        summary["units_in_stock"] = product.stock
    if product.promotion:
        summary["promotion"] = {
            "name": product.promotion.description,
            "original_price": format_brl(product.price),
            "discount_percent": product.promotion.discount_percent,
            "promotional_price": format_brl(product.final_price),
        }
    return summary


def _token_variants(token: str) -> set[str]:
    """Light Portuguese plural handling: violões <-> violão, guitarras -> guitarra."""
    variants = {token}
    if token.endswith("oes"):
        variants.add(token[:-3] + "ao")
    if token.endswith("ao"):
        variants.add(token[:-2] + "oes")
    if token.endswith("s") and len(token) > 3:
        variants.add(token[:-1])
    return variants


def _haystack(product: Product) -> str:
    specs = " ".join(str(v) for v in product.specs.values())
    description = product.description if product.description_is_reliable else ""
    return normalize(f"{product.name} {_category_name(product)} {description} {specs}")


def _match_score(tokens: list[str], haystack: str) -> int:
    return sum(1 for t in tokens if any(v in haystack for v in _token_variants(t)))


def _find_category_id(category: str) -> int | None:
    wanted = normalize(category)
    for cat in get_store().categories.values():
        if normalize(cat.name) == wanted:
            return cat.id
    return None


def _alternatives(product: Product, limit: int = 3) -> list[dict]:
    """Available products in the same category, closest in price first."""
    candidates = [
        p
        for p in get_store().products.values()
        if p.category_id == product.category_id
        and p.id != product.id
        and p.availability == "available"
    ]
    reference = product.final_price
    in_range = [
        p
        for p in candidates
        if abs(p.final_price - reference) <= reference * ALTERNATIVES_PRICE_RANGE
    ]
    pool = in_range or candidates
    pool.sort(key=lambda p: abs(p.final_price - reference))
    return [_product_summary(p) for p in pool[:limit]]


# --- Product tools -------------------------------------------------------------------


def list_categories() -> dict:
    return {
        "categories": [
            {"name": c.name, "description": c.description} for c in get_store().categories.values()
        ]
    }


def search_products(
    query: str | None = None,
    category: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    available_only: bool = False,
    limit: int = 10,
) -> dict:
    products = list(get_store().products.values())

    if category:
        category_id = _find_category_id(category)
        if category_id is None:
            return {
                "error": f"Unknown category '{category}'.",
                **list_categories(),
            }
        products = [p for p in products if p.category_id == category_id]

    # Price filters use the price the customer pays (with an active promotion, if any).
    if min_price is not None:
        products = [p for p in products if p.final_price >= Decimal(str(min_price))]
    if max_price is not None:
        products = [p for p in products if p.final_price <= Decimal(str(max_price))]
    if available_only:
        products = [p for p in products if p.availability == "available"]

    partial = False
    scores: dict[int, int] = {}
    if query:
        tokens = [t for t in normalize(query).split() if t not in STOPWORDS]
        scores = {p.id: _match_score(tokens, _haystack(p)) for p in products}
        exact = [p for p in products if scores[p.id] == len(tokens)]
        partial = not exact
        products = exact or [p for p in products if scores[p.id] > 0]

    # Available first, then most relevant (only differs for partial matches), then cheapest.
    products.sort(
        key=lambda p: (p.availability != "available", -scores.get(p.id, 0), p.final_price)
    )
    limit = max(1, min(limit, MAX_RESULTS))
    result = {
        "total_matches": len(products),
        "products": [_product_summary(p) for p in products[:limit]],
    }
    if partial:
        result["note"] = "No product matched every search term; showing partial matches."
    return result


def get_product_details(product_id: int) -> dict:
    product = get_store().products.get(product_id)
    if product is None:
        return {"error": f"Product {product_id} not found."}
    details = _product_summary(product)
    if product.description_is_reliable:
        details["description"] = product.description
    else:
        details["description_note"] = (
            "Description withheld: it contradicts the product name in the source data. "
            "Rely on name and specs only."
        )
    details["specs"] = product.specs
    if product.availability != "available":
        details["alternatives"] = _alternatives(product)
    return details


# --- Orders --------------------------------------------------------------------------

ORDER_STATUS_LABELS = {
    "pending": "pendente (aguardando confirmação)",
    "confirmed": "confirmado, em preparação para envio",
    "shipped": "enviado, a caminho",
    "delivered": "entregue",
    "cancelled": "cancelado",
}

REGRET_DAYS = 7  # policy 4.1, counted from receipt
PREFERENCE_EXCHANGE_DAYS = 7  # policy 4.3
DEFECT_EXCHANGE_DAYS = 30  # policy 4.2, counted from purchase
LEGAL_WARRANTY_DAYS = 90  # policy 8.1, counted from receipt

VERIFICATION_FAILED = {
    "verified": False,
    "error": "Could not find an order with this number for the e-mail or phone given. "
    "Ask the customer to check both. Do not reveal whether the order exists.",
}


def _fmt_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _payment_label(method: str) -> str:
    if method.startswith("credit_"):
        return f"cartão de crédito em {method.removeprefix('credit_')}"
    return {"pix": "PIX", "debit": "cartão de débito", "boleto": "boleto bancário"}.get(
        method, method
    )


def _identity_matches(customer: Customer, email_or_phone: str) -> bool:
    given = email_or_phone.strip().lower()
    if "@" in given:
        return given == customer.email.strip().lower()
    digits = digits_only(given)
    if len(digits) in (12, 13) and digits.startswith("55"):
        digits = digits[2:]  # +55 country code
    # Accept the number with or without area code (at least the 8-9 local digits).
    return len(digits) >= 8 and digits_only(customer.phone).endswith(digits)


def _window(start: date, days: int, today: date) -> dict:
    deadline = start + timedelta(days=days)
    return {"deadline": _fmt_date(deadline), "open": today <= deadline}


def _after_sales(order: Order, today: date) -> dict:
    """Return/exchange/warranty windows for a delivered order, computed from today's date.

    The data has no actual receipt date, so the estimated delivery date is the proxy.
    """
    received = order.estimated_delivery or order.order_date
    return {
        "assumed_receipt_date": _fmt_date(received),
        "assumption": "No receipt date in the system; the estimated delivery date is "
        "used as the receipt date.",
        "today": _fmt_date(today),
        "days_since_receipt": (today - received).days,
        "regret_return_7_days": _window(received, REGRET_DAYS, today),
        "preference_exchange_7_days": _window(received, PREFERENCE_EXCHANGE_DAYS, today),
        "defect_exchange_30_days_from_purchase": _window(
            order.order_date, DEFECT_EXCHANGE_DAYS, today
        ),
        "legal_warranty_90_days": _window(received, LEGAL_WARRANTY_DAYS, today),
        "manufacturer_warranty": "Varies from 6 months to 2 years by manufacturer; "
        "see the warranty certificate. The store can mediate the claim.",
    }


def get_order_status(order_id: int, email_or_phone: str) -> dict:
    """Order data is only returned when the e-mail or phone matches the order's customer."""
    store = get_store()
    order = store.orders.get(order_id)
    if order is None:
        return VERIFICATION_FAILED
    customer = store.customers[order.customer_id]
    if not _identity_matches(customer, email_or_phone):
        return VERIFICATION_FAILED

    today = clock.now().date()
    result = {
        "verified": True,
        "order_id": order.id,
        "customer_first_name": customer.name.split()[0],
        "status": order.status,
        "status_label": ORDER_STATUS_LABELS.get(order.status, order.status),
        "order_date": _fmt_date(order.order_date),
        "days_since_order": (today - order.order_date).days,
        "items": [{"name": store.products[pid].name, "quantity": qty} for pid, qty in order.items],
        "total": format_brl(order.total),
        "payment_method": _payment_label(order.payment_method),
    }
    if order.tracking_code:
        result["tracking_code"] = order.tracking_code
    elif order.status in ("pending", "confirmed"):
        result["tracking_note"] = (
            "No tracking code yet: it is sent by e-mail and WhatsApp when the order ships."
        )
    if order.estimated_delivery:
        result["estimated_delivery"] = _fmt_date(order.estimated_delivery)
    if order.status == "shipped" and order.estimated_delivery and order.estimated_delivery < today:
        result["delivery_overdue_days"] = (today - order.estimated_delivery).days
    if order.notes:
        result["notes"] = order.notes
    if order.status == "delivered":
        result["after_sales"] = _after_sales(order, today)
    return result


# --- Registry ------------------------------------------------------------------------


@dataclass(frozen=True)
class Tool:
    function: Callable[..., dict]
    description: str
    parameters: dict

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.function.__name__,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _category_enum() -> list[str]:
    return [c.name for c in get_store().categories.values()]


def build_tools() -> dict[str, Tool]:
    tools = [
        Tool(
            list_categories,
            "List the product categories the store sells.",
            {"type": "object", "properties": {}},
        ),
        Tool(
            search_products,
            "Search the instrument catalog. Returns current price (with active promotion, "
            "if any), availability and stock. Use for any question about products, prices "
            "or availability. Returns unavailable products too, flagged in `availability`.",
            {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Free text: brand, model, type or feature "
                        "(e.g. 'takamine gd20', 'nylon', 'elétrico').",
                    },
                    "category": {"type": "string", "enum": _category_enum()},
                    "min_price": {"type": "number", "description": "Minimum price in BRL."},
                    "max_price": {"type": "number", "description": "Maximum price in BRL."},
                    "available_only": {
                        "type": "boolean",
                        "description": "True to return only products available for sale. "
                        "Use when the customer is browsing options.",
                    },
                    "limit": {"type": "integer", "description": "Max results (default 10)."},
                },
            },
        ),
        Tool(
            get_product_details,
            "Full details of one product: description, specs, price, promotion and "
            "availability. For unavailable products it also returns similar available "
            "alternatives in the same category and price range.",
            {
                "type": "object",
                "properties": {"product_id": {"type": "integer"}},
                "required": ["product_id"],
            },
        ),
        Tool(
            get_order_status,
            "Status of a customer's order: items, total, tracking and delivery estimate; for "
            "delivered orders, also the return, exchange and warranty windows computed from "
            "today's date. Requires the order number AND the e-mail or phone of the buyer; "
            "ask the customer for both before calling. Never guess them.",
            {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer"},
                    "email_or_phone": {
                        "type": "string",
                        "description": "E-mail or phone number given by the customer.",
                    },
                },
                "required": ["order_id", "email_or_phone"],
            },
        ),
    ]
    return {t.function.__name__: t for t in tools}


TOOLS = build_tools()


def tool_schemas() -> list[dict]:
    return [t.schema() for t in TOOLS.values()]


def execute_tool(name: str, arguments: str) -> str:
    """Runs a tool from a model tool call. Errors are returned to the model as JSON."""
    tool = TOOLS.get(name)
    if tool is None:
        return json.dumps({"error": f"Unknown tool '{name}'."})
    try:
        args = json.loads(arguments or "{}")
        result = tool.function(**args)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        result = {"error": f"Invalid arguments for {name}: {exc}"}
    return json.dumps(result, ensure_ascii=False)
