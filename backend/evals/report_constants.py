"""Layout and fixed copy for the eval report."""

TITLE = "Agent evaluation suite — docs/SPEC-2.md 11.1"

NO_RESULTS = (
    "No cases were run, so this report contains no measurements. Nothing below is an\n"
    "estimate or a placeholder: where a number is absent, it was never measured."
)

PROVENANCE = (
    "Produced by `make eval` against the real Anthropic API. Numbers are one run, not a\n"
    "distribution; rerun after any change to the prompt or the tool descriptions."
)

# Model output is unbounded; a report has to stay readable and diffable.
ANSWER_EXCERPT_CHARS = 240

SEPARATOR = "-" * 88
