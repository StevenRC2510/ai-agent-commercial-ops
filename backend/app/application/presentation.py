"""PRESENTATION — the only place the Spanish text a human reads gets built.

Imports only app.domain, never policy: rendering stays independent of decisions.
"""

_DENIAL_TEXTS: dict[str, str] = {
    "unknown_tool": "La operación solicitada no existe.",
    "role_lacks_permission": "Tu rol no tiene permiso para esta operación.",
    "invalid_arguments": "Los datos de la operación no son válidos.",
    "order_not_found": "No encontré esa orden.",
    "invalid_status_transition": "Ese cambio de estado no está permitido.",
}


def render_denial(reason: str) -> str:
    """Human-readable Spanish message for a PolicyDecision denial reason code."""
    return _DENIAL_TEXTS[reason]


def denial_texts() -> dict[str, str]:
    """The complete map of denial reason codes to their Spanish messages.

    Exists so a test can assert this matches policy.DenialReason without an import.
    """
    return dict(_DENIAL_TEXTS)
