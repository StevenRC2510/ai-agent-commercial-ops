"""Shared LLM vocabulary and price table. Everything imports these; nothing duplicates them."""

from collections.abc import Mapping
from decimal import Decimal
from enum import Enum


class Model(str, Enum):
    """The priced model IDs. Bare, no date suffix (SPEC-2 §5.2)."""

    HAIKU_4_5 = "claude-haiku-4-5"
    SONNET_5 = "claude-sonnet-5"
    OPUS_5 = "claude-opus-5"


# Keyed by Model, not str: an unpriced id must fail at construction, never at lookup.
# USD per million tokens, as (input, output). Source table in docs/SPEC-2.md §5.2.
PRICES: Mapping[Model, tuple[Decimal, Decimal]] = {
    Model.HAIKU_4_5: (Decimal("1.00"), Decimal("5.00")),
    Model.SONNET_5: (Decimal("3.00"), Decimal("15.00")),
    Model.OPUS_5: (Decimal("5.00"), Decimal("25.00")),
}
