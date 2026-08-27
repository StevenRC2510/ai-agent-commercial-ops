"""Tables for the prompt-prefix measurement. Sources: docs/SPEC-2.md §5.2 for the floors."""

from collections.abc import Mapping

from app.application.constants import Model

# Keyed by Model, not str: a model with no published floor must fail at construction.
# Minimum cacheable prefix in tokens — NOT monotonic across generations, so never inferred.
MIN_CACHEABLE_TOKENS: Mapping[Model, int] = {
    Model.HAIKU_4_5: 4096,
    Model.SONNET_5: 1024,
    Model.OPUS_5: 512,
}

# Anthropic's tokenizer is not public, so tokens are estimated from characters. The band spans
# punctuation-dense JSON (2.5) to accented Spanish prose (4.0); a verdict must hold across it.
CHARS_PER_TOKEN_BAND: tuple[float, float] = (2.5, 4.0)
