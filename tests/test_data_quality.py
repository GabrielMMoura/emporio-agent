"""Known anomalies in the provided data, pinned as tests.

Each one is listed in the README "Data notes". If the data changes, these tests point at
the notes that need updating.
"""

from datetime import datetime

import pytest

from emporio_agent import clock
from emporio_agent.data_store import get_store
from emporio_agent.prompts import build_system_prompt
from emporio_agent.tools import _min_installment, get_order_status


@pytest.fixture(scope="module")
def store():
    return get_store()


def items_total(store, order):
    return sum(store.products[pid].price * qty for pid, qty in order.items)


def test_order_totals_differ_from_items_in_two_orders(store):
    mismatched = {o.id for o in store.orders.values() if items_total(store, o) != o.total}
    assert mismatched == {3, 20}


def test_pix_orders_were_charged_full_price(store):
    pix_orders = [o for o in store.orders.values() if o.payment_method == "pix"]
    assert pix_orders
    assert all(items_total(store, o) == o.total for o in pix_orders)


def test_some_historical_orders_break_the_installment_minimums(store):
    breaking = set()
    for order in store.orders.values():
        if order.payment_method.startswith("credit_"):
            n = int(order.payment_method.removeprefix("credit_").rstrip("x"))
            if n > 1 and order.total / n < _min_installment(n):
                breaking.add(order.id)
    assert breaking == {9, 16, 18}


def test_coming_soon_product_appears_in_orders(store):
    orders = {o.id for o in store.orders.values() if any(pid == 130 for pid, _ in o.items)}
    assert orders == {3, 14}


def test_two_customers_share_an_email(store):
    owners = [c.id for c in store.customers.values() if c.email == "bruno.martins@jmail.com"]
    assert owners == [11, 43]


def test_shared_email_only_unlocks_orders_of_the_order_owner(monkeypatch):
    # Order 10 belongs to customer 11. The shared e-mail matches, which is the best the
    # data allows; a phone number disambiguates.
    frozen = datetime(2026, 11, 1, tzinfo=clock.STORE_TZ)
    monkeypatch.setattr(clock, "now", lambda: frozen)
    assert get_order_status(10, "bruno.martins@jmail.com")["verified"] is True
    assert get_order_status(10, "(67) 99456-3456")["verified"] is False  # customer 43's phone


def test_system_prompt_has_current_time_and_official_contacts():
    prompt = build_system_prompt(datetime(2026, 11, 1, 9, 5, tzinfo=clock.STORE_TZ))
    assert "domingo, 01/11/2026 09:05" in prompt
    assert "(67) 3341-4444" in prompt
    assert "contato@emporiodamusica.com.br" in prompt
    assert "3321-4500" not in prompt
