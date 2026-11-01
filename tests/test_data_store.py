from datetime import date
from decimal import Decimal

import pytest

from emporio_agent.data_store import format_brl, get_store, normalize


@pytest.fixture(scope="module")
def store():
    return get_store()


def test_loads_all_tables(store):
    assert len(store.categories) == 9
    assert len(store.products) == 65
    assert len(store.customers) == 50
    assert len(store.orders) == 20
    assert sum(len(o.items) for o in store.orders.values()) == 22


def test_prices_in_mixed_formats_become_decimals(store):
    assert store.products[93].price == Decimal("11499.00")
    assert store.products[81].price == Decimal("599.90")


def test_specs_are_parsed_to_dict(store):
    assert store.products[81].specs["strings"] == "nylon"


def test_active_product_with_zero_stock_is_out_of_stock(store):
    giannini = store.products[96]
    assert giannini.status == "active"
    assert giannini.availability == "out_of_stock"


@pytest.mark.parametrize("product_id", [113, 136])
def test_discontinued_products(store, product_id):
    assert store.products[product_id].availability == "discontinued"


def test_coming_soon_with_stock_is_not_available(store):
    kala = store.products[130]
    assert kala.stock > 0
    assert kala.availability == "coming_soon"


def test_regular_product_is_available(store):
    assert store.products[95].availability == "available"


def test_only_active_promotions_are_loaded(store):
    promoted = {pid for pid, p in store.products.items() if p.promotion}
    assert promoted == {127, 121, 90, 94}


def test_inactive_promotion_does_not_change_price(store):
    # Takamine GD20 had a 12% "Oferta Especial" that is no longer active.
    takamine = store.products[95]
    assert takamine.promotion is None
    assert takamine.final_price == takamine.price


def test_final_price_applies_active_discount(store):
    crafter = store.products[90]  # 2399 with 18% off
    assert crafter.final_price == Decimal("1967.18")


def test_orders_without_tracking_have_none(store):
    assert store.orders[9].tracking_code is None
    assert store.orders[9].estimated_delivery is None
    assert store.orders[1].estimated_delivery == date(2025, 10, 25)


def test_multi_item_order(store):
    assert store.orders[15].items == [(82, 1), (106, 1)]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("11499"), "R$ 11.499,00"),
        (Decimal("799.9"), "R$ 799,90"),
        (Decimal("1967.175"), "R$ 1.967,18"),
        (Decimal("0"), "R$ 0,00"),
    ],
)
def test_format_brl(value, expected):
    assert format_brl(value) == expected


def test_normalize_strips_accents_case_and_punctuation():
    assert normalize("Violão Elétrico KA-ABP-CTG") == "violao eletrico ka abp ctg"


@pytest.mark.parametrize("product_id", [135, 137, 139, 140, 142, 144])
def test_description_naming_another_brand_is_unreliable(store, product_id):
    assert not store.products[product_id].description_is_reliable


@pytest.mark.parametrize("product_id", [81, 95, 131, 141, 143])
def test_consistent_descriptions_are_reliable(store, product_id):
    assert store.products[product_id].description_is_reliable
