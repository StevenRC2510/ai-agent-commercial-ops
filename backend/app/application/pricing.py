"""Cost estimation over the price table. Pure arithmetic, no IO: application, not infrastructure."""

from decimal import Decimal

from app.application.constants import PRICES, Model

_TOKENS_PER_PRICE_UNIT = Decimal(1_000_000)


def estimate_cost(model: Model, input_tokens: int, output_tokens: int) -> Decimal:
    """Cost in USD as Decimal — never float, like every other money value here."""
    input_price, output_price = PRICES[model]
    billed = Decimal(input_tokens) * input_price + Decimal(output_tokens) * output_price
    return billed / _TOKENS_PER_PRICE_UNIT
