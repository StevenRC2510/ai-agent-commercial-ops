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
}
