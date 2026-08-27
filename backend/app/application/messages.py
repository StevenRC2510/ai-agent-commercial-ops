"""SPANISH TEXT TABLES — the single place every user-facing Spanish string is declared.

Data only, no functions: keeps translating the product later a one-file job.
"""

from collections.abc import Mapping

from app.application.permissions import DenialReason

DENIAL_TEXTS: Mapping[DenialReason, str] = {
    DenialReason.UNKNOWN_TOOL: "La operación solicitada no existe.",
    DenialReason.ROLE_LACKS_PERMISSION: "Tu rol no tiene permiso para esta operación.",
    DenialReason.INVALID_ARGUMENTS: "Los datos de la operación no son válidos.",
    DenialReason.ORDER_NOT_FOUND: "No encontré esa orden.",
    DenialReason.INVALID_STATUS_TRANSITION: "Ese cambio de estado no está permitido.",
    DenialReason.STATE_CHANGED_SINCE_CONSENT: (
        "La orden cambió de estado desde que aprobaste esta acción. Vuelve a intentarlo."
    ),
    # One text for every unusable consent: the caller must not learn which cause applied.
    DenialReason.CONSENT_UNUSABLE: "Esta confirmación ya no es válida. Vuelve a pedir el cambio.",
    # Names neither the caller nor the budget: a throttled request is not an oracle either.
    DenialReason.RATE_LIMITED: (
        "Alcanzaste el límite de solicitudes. Espera un momento y vuelve a intentarlo."
    ),
}

# Fixed, safe text for orchestrator failure paths: never derived from model output.
FALLBACK_LLM_ERROR = (
    "No pude procesar tu solicitud en este momento. Vuelve a intentarlo en unos segundos."
)
FALLBACK_MAX_ITERATIONS = (
    "La consulta resultó más compleja de lo que puedo resolver en un turno. "
    "¿Puedes reformularla en partes?"
)
FALLBACK_INPUT_TOO_LONG = (
    "Tu mensaje excede el límite de 2.000 caracteres. Resume la consulta, por favor."
)
FALLBACK_BUDGET_EXCEEDED = (
    "Esta conversación alcanzó su límite de costo. Empieza una nueva para continuar."
)
FALLBACK_INTERNAL_ERROR = (
    "Ocurrió un error inesperado y no pude completar la operación. Vuelve a intentarlo."
)

# HTTP surface. UNAUTHENTICATED names no role: an unauthenticated caller learns nothing.
UNAUTHENTICATED = "No pude identificar tu sesión. Vuelve a iniciarla."
CONFIRMATION_EXECUTED = "Cambio aplicado. {summary}"
CONFIRMATION_CANCELLED = "Cancelado. No se aplicó ningún cambio."
