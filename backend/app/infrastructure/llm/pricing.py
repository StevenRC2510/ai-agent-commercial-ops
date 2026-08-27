"""Per-model USD pricing and cost estimation. See docs/SPEC-2.md §5.2 for the source table."""

from collections.abc import Mapping
from decimal import Decimal

# model -> (input price, output price) per million tokens. Bare model IDs, no date suffix.
_PRICES: Mapping[str, tuple[Decimal, Decimal]] = {
    "claude-haiku-4-5": (Decimal("1.00"), Decimal("5.00")),
    "claude-sonnet-5": (Decimal("3.00"), Decimal("15.00")),
    "claude-opus-5": (Decimal("5.00"), Decimal("25.00")),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """Cost in USD as Decimal — never float, like every other money value here."""
    input_price, output_price = _PRICES[model]
    million = Decimal(1_000_000)
    return (Decimal(input_tokens) * input_price + Decimal(output_tokens) * output_price) / million
