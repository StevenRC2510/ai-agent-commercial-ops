from decimal import Decimal

import pytest

from app.application.pricing import estimate_cost


def test_haiku_cost_is_exact_decimal() -> None:
    """Money is Decimal here for the same reason it is in the database."""
    cost = estimate_cost("claude-haiku-4-5", input_tokens=1_000_000, output_tokens=0)
    assert cost == Decimal("1.00")
    assert isinstance(cost, Decimal)


def test_output_tokens_cost_more_than_input() -> None:
    cheap = estimate_cost("claude-haiku-4-5", input_tokens=1000, output_tokens=0)
    dear = estimate_cost("claude-haiku-4-5", input_tokens=0, output_tokens=1000)
    assert dear > cheap


@pytest.mark.parametrize("model", ["claude-haiku-4-5", "claude-sonnet-5", "claude-opus-5"])
def test_every_documented_model_is_priced(model: str) -> None:
    assert estimate_cost(model, input_tokens=1000, output_tokens=1000) > 0


def test_unknown_model_raises_rather_than_guessing() -> None:
    """A silent zero would make the budget guardrail useless."""
    with pytest.raises(KeyError):
        estimate_cost("claude-imaginary-9", input_tokens=1, output_tokens=1)


def test_a_date_suffixed_id_is_not_accepted() -> None:
    """Model IDs are bare; a suffixed one is a bug we want loud."""
    with pytest.raises(KeyError):
        estimate_cost("claude-haiku-4-5-20251001", input_tokens=1, output_tokens=1)
