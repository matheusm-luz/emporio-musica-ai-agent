"""Deterministic business rules from the policy manual — never delegated to the LLM.

Each rule cites the manual section it implements (see docs/SPEC.md).
"""

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

CENT = Decimal("0.01")

# §3: 5% off the list price when paying with PIX. §6.2: not applied over promotional prices.
PIX_DISCOUNT = Decimal("0.05")

# §3.1 (prevails over the summary table in §3, SPEC I7): (max installments, minimum installment).
INSTALLMENT_TIERS: tuple[tuple[int, Decimal], ...] = (
    (3, Decimal("50.00")),
    (6, Decimal("80.00")),
    (12, Decimal("100.00")),
)

# §2: Mon–Fri 09:00–18:00, Sat 09:00–13:00, Sundays and holidays closed (holidays: SPEC I11).
OPENING_HOURS: dict[int, tuple[time, time]] = {
    **{weekday: (time(9), time(18)) for weekday in range(5)},
    5: (time(9), time(13)),
}
WEEKDAY_NAMES_PT = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")


def money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def format_brl(value: Decimal) -> str:
    """Decimal(2199) -> 'R$ 2.199,00'."""
    integer, cents = f"{money(value):,.2f}".split(".")
    return f"R$ {integer.replace(',', '.')},{cents}"


class Availability(StrEnum):
    AVAILABLE = "disponível"
    OUT_OF_STOCK = "esgotado"
    DISCONTINUED = "descontinuado"
    COMING_SOON = "em breve"


def availability(status: str, stock: int) -> Availability:
    """`status` prevails over stock (SPEC I8)."""
    if status == "discontinued":
        return Availability.DISCONTINUED
    if status == "coming_soon":
        return Availability.COMING_SOON
    return Availability.AVAILABLE if stock > 0 else Availability.OUT_OF_STOCK


def minimum_installment(count: int) -> Decimal:
    return next(minimum for tier_max, minimum in INSTALLMENT_TIERS if count <= tier_max)


def max_installments(amount: Decimal) -> int:
    """Largest interest-free installment count allowed for `amount` (§3.1); 1 = single payment."""
    allowed = (count for count in range(2, 13) if amount / count >= minimum_installment(count))
    return max(allowed, default=1)


@dataclass(frozen=True)
class Promotion:
    name: str
    percent: int


@dataclass(frozen=True)
class PriceQuote:
    list_price: Decimal
    promotion: Promotion | None
    final_price: Decimal  # promotional price when a promotion is active, else the list price
    pix_price: Decimal | None  # None when a promotion is active (§6.2: not cumulative)
    installments: int
    installment_value: Decimal

    def to_dict(self) -> dict:
        quote = {"preco": format_brl(self.final_price)}
        if self.promotion:
            quote |= {
                "preco_original": format_brl(self.list_price),
                "promocao": self.promotion.name,
                "desconto": f"{self.promotion.percent}%",
                "pix": "desconto PIX de 5% não se aplica sobre preço promocional",
            }
        else:
            quote["preco_pix"] = f"{format_brl(self.pix_price)} (5% de desconto à vista no PIX)"
        if self.installments > 1:
            quote["parcelamento_cartao"] = (
                f"até {self.installments}x de {format_brl(self.installment_value)} sem juros"
            )
        else:
            quote["parcelamento_cartao"] = "somente à vista (valor abaixo da parcela mínima)"
        return quote


def quote_price(list_price: Decimal, active_promotions: list[Promotion]) -> PriceQuote:
    """Price shown to the customer. Promotions are not cumulative — the best one applies (§6.2)."""
    promotion = max(active_promotions, key=lambda p: p.percent, default=None)
    final = money(list_price * (100 - promotion.percent) / 100) if promotion else money(list_price)
    installments = max_installments(final)
    return PriceQuote(
        list_price=money(list_price),
        promotion=promotion,
        final_price=final,
        pix_price=None if promotion else money(final * (1 - PIX_DISCOUNT)),
        installments=installments,
        installment_value=money(final / installments),
    )


def store_status(now: datetime) -> str:
    """Open/closed sentence for the system prompt (§2, §7.1: inform when the team is back)."""
    hours = OPENING_HOURS.get(now.weekday())
    if hours and hours[0] <= now.time() < hours[1]:
        return f"A loja está ABERTA agora (hoje até {hours[1]:%H:%M})."
    for days_ahead in range(0, 8):
        day = now + timedelta(days=days_ahead)
        hours = OPENING_HOURS.get(day.weekday())
        if not hours or (days_ahead == 0 and now.time() >= hours[0]):
            continue
        when = "hoje" if days_ahead == 0 else "amanhã" if days_ahead == 1 else ""
        when = when or WEEKDAY_NAMES_PT[day.weekday()]
        return (
            "A loja está FECHADA agora (fora do horário de atendimento). "
            f"A equipe volta {when} ({day:%d/%m}) às {hours[0]:%H:%M}."
        )
    raise AssertionError("opening hours must contain at least one day")
