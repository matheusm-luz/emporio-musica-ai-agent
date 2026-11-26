from datetime import datetime
from decimal import Decimal

import pytest

from emporio_agent.config import STORE_TZ
from emporio_agent.rules import (
    Availability,
    Promotion,
    availability,
    format_brl,
    max_installments,
    quote_price,
    store_status,
)


def test_format_brl() -> None:
    assert format_brl(Decimal("2199")) == "R$ 2.199,00"
    assert format_brl(Decimal("2089.05")) == "R$ 2.089,05"
    assert format_brl(Decimal("159.9")) == "R$ 159,90"
    assert format_brl(Decimal("19567")) == "R$ 19.567,00"


@pytest.mark.parametrize(
    ("status", "stock", "expected"),
    [
        ("active", 5, Availability.AVAILABLE),
        ("active", 0, Availability.OUT_OF_STOCK),  # product 96
        ("discontinued", 13, Availability.DISCONTINUED),  # product 136: status prevails
        ("discontinued", 0, Availability.DISCONTINUED),  # product 113
        ("coming_soon", 2, Availability.COMING_SOON),  # product 130
    ],
)
def test_availability(status: str, stock: int, expected: Availability) -> None:
    assert availability(status, stock) is expected


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        ("2199", 12),  # 12 x 183,25 >= 100
        ("1000", 10),  # 10 x 100,00 — exactly the minimum
        ("999", 9),  # 10 x 99,90 < 100
        ("359", 4),  # 4 x 89,75 >= 80 ; 5 x 71,80 < 80
        ("159.9", 3),  # 3 x 53,30 >= 50
        ("100", 2),  # 2 x 50,00
        ("99", 1),  # 2 x 49,50 < 50 -> single payment
    ],
)
def test_max_installments_follow_section_3_1(amount: str, expected: int) -> None:
    assert max_installments(Decimal(amount)) == expected


def test_quote_without_promotion_offers_pix_discount() -> None:
    quote = quote_price(Decimal("2199"), [])  # Takamine GD20
    assert quote.final_price == Decimal("2199.00")
    assert quote.pix_price == Decimal("2089.05")
    assert (quote.installments, quote.installment_value) == (12, Decimal("183.25"))
    assert quote.to_dict()["preco_pix"].startswith("R$ 2.089,05")


def test_quote_with_promotion_has_no_pix_discount_and_shows_original_price() -> None:
    quote = quote_price(Decimal("549"), [Promotion("Desconto Exclusivo", 20)])  # Ohana CK-20
    assert quote.final_price == Decimal("439.20")
    assert quote.pix_price is None
    assert (quote.installments, quote.installment_value) == (5, Decimal("87.84"))
    shown = quote.to_dict()
    assert shown["preco_original"] == "R$ 549,00"
    assert shown["desconto"] == "20%"


def test_promotions_are_not_cumulative() -> None:
    quote = quote_price(Decimal("1000"), [Promotion("A", 10), Promotion("B", 18)])
    assert quote.promotion == Promotion("B", 18)
    assert quote.final_price == Decimal("820.00")


def _at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=STORE_TZ)


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (_at(25, 10), "ABERTA agora (hoje até 18:00)"),  # Wednesday
        (_at(28, 12, 59), "ABERTA agora (hoje até 13:00)"),  # Saturday
        (_at(25, 7, 30), "volta hoje (25/11) às 09:00"),
        (_at(27, 19), "volta amanhã (28/11) às 09:00"),  # Friday night
        (_at(28, 14), "volta segunda (30/11) às 09:00"),  # Saturday afternoon
        (_at(29, 10), "volta amanhã (30/11) às 09:00"),  # Sunday
    ],
)
def test_store_status(now: datetime, expected: str) -> None:
    assert expected in store_status(now)
