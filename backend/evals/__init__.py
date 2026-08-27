"""Agent evaluation suite (docs/SPEC-2.md §11.1).

Lives outside `app/` on purpose: it composes every layer, so it is a caller of the
application, never part of it. Nothing under `app/` may import it.
"""
