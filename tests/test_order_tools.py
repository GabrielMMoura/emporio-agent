from datetime import datetime

import pytest

from emporio_agent import clock
from emporio_agent.tools import get_order_status


@pytest.fixture
def today(monkeypatch):
    """Freezes the clock; returns a setter for the current date."""

    def set_today(year, month, day):
        frozen = datetime(year, month, day, 10, 0, tzinfo=clock.STORE_TZ)
        monkeypatch.setattr(clock, "now", lambda: frozen)

    set_today(2026, 11, 1)
    return set_today


# Order 8: customer 2, Ana Carolina, anacarol.ferreira@coldmail.com, (67) 99654-7821


@pytest.mark.parametrize(
    "identity",
    [
        "anacarol.ferreira@coldmail.com",
        "  AnaCarol.Ferreira@ColdMail.com ",
        "(67) 99654-7821",
        "67996547821",
        "+55 67 99654-7821",
        "99654-7821",
    ],
)
def test_order_is_returned_when_identity_matches(today, identity):
    result = get_order_status(8, identity)
    assert result["verified"] is True
    assert result["customer_first_name"] == "Ana"


@pytest.mark.parametrize(
    "identity",
    ["lucas.mendes@jmail.com", "(67) 99812-3456", "7821", "anacarol.ferreira@coldmail"],
)
def test_order_is_withheld_when_identity_does_not_match(today, identity):
    result = get_order_status(8, identity)
    assert result["verified"] is False
    assert "status" not in result
    assert "items" not in result


@pytest.mark.parametrize("identity", ["", "   "])
def test_missing_identity_asks_for_it_without_revealing_anything(today, identity):
    # Regression: the model sometimes called the tool with an empty e-mail before asking.
    result = get_order_status(8, identity)
    assert result["verified"] is False
    assert "Ask the customer" in result["error"]
    assert result == get_order_status(999, identity)


def test_unknown_order_gives_same_answer_as_wrong_identity(today):
    assert get_order_status(999, "anacarol.ferreira@coldmail.com") == get_order_status(
        8, "someone@else.com"
    )


def test_shipped_order_has_tracking_and_overdue_flag(today):
    result = get_order_status(8, "anacarol.ferreira@coldmail.com")
    assert result["status"] == "shipped"
    assert result["tracking_code"] == "BRJL5544332BR"
    assert result["estimated_delivery"] == "28/02/2026"
    assert result["delivery_overdue_days"] == 246
    assert result["items"] == [{"name": "Kala KA-C Concert Mogno", "quantity": 1}]
    assert result["total"] == "R$ 349,90"
    assert result["payment_method"] == "cartão de débito"


def test_shipped_order_not_overdue_before_estimate(today):
    today(2026, 2, 20)
    result = get_order_status(8, "anacarol.ferreira@coldmail.com")
    assert "delivery_overdue_days" not in result


def test_confirmed_order_explains_missing_tracking(today):
    result = get_order_status(9, "juliana.almeida@hayoo.com.br")
    assert result["status"] == "confirmed"
    assert "tracking_code" not in result
    assert "tracking_note" in result
    assert result["payment_method"] == "cartão de crédito em 6x"


def test_cancelled_order_includes_reason(today):
    result = get_order_status(18, "gustavo.nunes@inlook.com")
    assert result["status"] == "cancelled"
    assert result["notes"] == "Item fora de estoque no momento do pedido"


def test_multi_item_order(today):
    result = get_order_status(15, "aline.monteiro@jmail.com")
    assert [i["name"] for i in result["items"]] == [
        "Yamaha C70 Nylon Natural",
        "Taylor 214ce Elétrico Aço Natural",
    ]


def test_non_delivered_orders_have_no_after_sales(today):
    assert "after_sales" not in get_order_status(8, "anacarol.ferreira@coldmail.com")


def test_delivered_order_long_ago_has_all_store_windows_closed(today):
    # Order 5: Rafael, bought 05/01/2026, estimated delivery 18/01/2026. Today 01/11/2026.
    after_sales = get_order_status(5, "rafael.pereira@jmail.com")["after_sales"]
    assert after_sales["assumed_receipt_date"] == "18/01/2026"
    assert after_sales["days_since_receipt"] == 287
    assert after_sales["regret_return_7_days"] == {"deadline": "25/01/2026", "open": False}
    assert after_sales["defect_exchange_30_days_from_purchase"]["open"] is False
    assert after_sales["legal_warranty_90_days"] == {"deadline": "18/04/2026", "open": False}


def test_regret_window_is_open_within_7_days_of_receipt(today):
    today(2026, 1, 25)  # exactly 7 days after the assumed receipt
    after_sales = get_order_status(5, "rafael.pereira@jmail.com")["after_sales"]
    assert after_sales["regret_return_7_days"]["open"] is True
    assert after_sales["defect_exchange_30_days_from_purchase"] == {
        "deadline": "04/02/2026",
        "open": True,
    }


def test_regret_window_closes_on_day_8(today):
    today(2026, 1, 26)
    after_sales = get_order_status(5, "rafael.pereira@jmail.com")["after_sales"]
    assert after_sales["regret_return_7_days"]["open"] is False
    assert after_sales["legal_warranty_90_days"]["open"] is True
