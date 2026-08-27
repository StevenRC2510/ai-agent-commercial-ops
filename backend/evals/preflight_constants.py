"""What a developer reads when the suite refuses to run."""

DEMO_MODE_ACTIVE = (
    "DEMO_MODE is on, so the fake client would answer every case. Scoring it would "
    "measure our own keyword matcher, not a model. Set DEMO_MODE=false."
)

KEY_MISSING = "ANTHROPIC_API_KEY is empty. The suite only runs against the real API."

CONFIG_UNAVAILABLE = (
    "app.config refused to load ({errors}). The usual cause is DEMO_MODE=false with no "
    "ANTHROPIC_API_KEY set."
)

BLOCKED_HEADER = "make eval cannot run:"

BLOCKED_FOOTER = (
    "No cases were run and no results were produced. This suite measures the real model "
    "on purpose: it needs DEMO_MODE=false, a funded ANTHROPIC_API_KEY, and network access."
)
