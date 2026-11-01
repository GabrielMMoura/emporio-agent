from datetime import datetime

import pytest

from emporio_agent import clock
from emporio_agent.tools import calculate_payment_options, get_policy, get_store_status


@pytest.fixture
def at(monkeypatch):
    def set_now(*args):
        frozen = datetime(*args, tzinfo=clock.STORE_TZ)
        monkeypatch.setattr(clock, "now", lambda: frozen)

    return set_now


# --- get_store_status ------------------------------------------------------------------


def test_open_on_a_weekday(at):
    at(2026, 11, 4, 10, 0)  # Wednesday
    status = get_store_status()
    assert status["is_open"] is True
    assert status["today_hours"] == "09:00 às 18:00"
    assert status["closes_at"] == "18:00"
    assert "next_opening" not in status


def test_sunday_before_a_holiday_skips_to_tuesday(at):
    at(2026, 11, 1, 10, 0)  # Sunday; Monday 02/11 is Finados
    status = get_store_status()
    assert status["is_open"] is False
    assert status["today_hours"] == "fechado"
    assert status["next_opening"] == "terça-feira, 03/11/2026 às 09:00"


def test_closed_on_a_holiday(at):
    at(2026, 11, 2, 11, 0)
    status = get_store_status()
    assert status["is_open"] is False
    assert status["holiday"] == "Finados"


def test_saturday_closes_at_13(at):
    at(2026, 11, 7, 13, 30)
    status = get_store_status()
    assert status["is_open"] is False
    assert status["today_hours"] == "09:00 às 13:00"
    assert status["next_opening"] == "segunda-feira, 09/11/2026 às 09:00"


def test_before_opening_reopens_same_day(at):
    at(2026, 11, 6, 8, 0)  # Friday
    assert get_store_status()["next_opening"] == "sexta-feira, 06/11/2026 às 09:00"


def test_closing_time_is_exclusive(at):
    at(2026, 11, 6, 18, 0)
    status = get_store_status()
    assert status["is_open"] is False
    assert status["next_opening"] == "sábado, 07/11/2026 às 09:00"


# --- calculate_payment_options ---------------------------------------------------------


def installments(result):
    return {o["installments"]: o["value"] for o in result["credit_card"]["options"]}


def test_regular_product_gets_pix_discount_and_12x():
    result = calculate_payment_options(95)  # Takamine GD20, 2199
    assert result["price"] == "R$ 2.199,00"
    assert result["pix"]["total"] == "R$ 2.089,05"
    assert result["credit_card"]["max_installments"] == 12
    assert installments(result)[10] == "R$ 219,90"
    assert result["combined_payment_allowed"] is True
    assert "promotion" not in result


def test_pix_discount_does_not_stack_with_promotion():
    result = calculate_payment_options(121)  # Ohana CK-20, 549 with 20% off
    assert result["promotion"]["original_price"] == "R$ 549,00"
    assert result["promotion"]["discount_percent"] == 20
    assert result["price"] == "R$ 439,20"
    assert result["pix"]["total"] == "R$ 439,20"
    assert "does not stack" in result["pix"]["note"]


def test_installments_respect_minimum_per_bracket():
    result = calculate_payment_options(120)  # Kala KA-C, 349,90
    plans = installments(result)
    assert plans[3] == "R$ 116,63"
    assert plans[4] == "R$ 87,48"  # >= 80 in the 4-6x bracket
    assert 5 not in plans  # 69,98 < 80
    assert 7 not in plans
    assert result["credit_card"]["max_installments"] == 4
    assert result["combined_payment_allowed"] is False


def test_cheap_product_limited_to_3x():
    result = calculate_payment_options(119)  # 159,90
    assert installments(result)[3] == "R$ 53,30"
    assert result["credit_card"]["max_installments"] == 3


def test_quantity_multiplies_total():
    result = calculate_payment_options(119, quantity=2)
    assert result["price"] == "R$ 319,80"


@pytest.mark.parametrize("product_id", [96, 113, 130])
def test_unavailable_products_have_no_payment_options(product_id):
    result = calculate_payment_options(product_id)
    assert "error" in result
    assert "pix" not in result


def test_invalid_inputs():
    assert "error" in calculate_payment_options(9999)
    assert "error" in calculate_payment_options(95, quantity=0)


# --- get_policy ------------------------------------------------------------------------


def test_policy_tool_returns_section():
    result = get_policy("payment")
    assert result["topic"] == "payment"
    assert "PIX" in result["text"]
