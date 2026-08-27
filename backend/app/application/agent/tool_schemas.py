"""Anthropic tool declarations, generated from the same models `policy.py` validates against.

Descriptions are Spanish, copied verbatim from docs/SPEC-2.md §4 where the spec gives full text.
"""

from collections.abc import Mapping
from typing import Any

from app.application.permissions import ToolName
from app.application.policy import visible_tools_for
from app.application.tool_args import TOOL_SCHEMAS

_DESCRIPTIONS: Mapping[ToolName, str] = {
    ToolName.GET_SALES_ORDERS: (
        "Consulta órdenes de venta con filtros opcionales por estado, rango de "
        "fechas y cliente. Úsala para cualquier pregunta sobre órdenes: cuáles "
        "están pendientes, qué se entregó en un periodo, órdenes de un cliente "
        "concreto. NO la uses para consultar saldos o pagos: para eso está "
        "get_client_balance."
    ),
    ToolName.GET_CLIENT_BALANCE: (
        "Consulta el saldo pendiente de pago de un cliente identificado por su "
        "client_id. Úsala para preguntas sobre deudas, saldos o pagos pendientes "
        "de un cliente concreto. NO la uses para listar órdenes o consultar su "
        "estado: para eso está get_sales_orders."
    ),
    ToolName.UPDATE_ORDER_STATUS: (
        "Cambia el estado de una orden de venta existente (por ejemplo, de "
        "pendiente a en proceso, o a cancelada), indicando siempre un motivo "
        "para auditoría. Úsala solo cuando el usuario pida explícitamente "
        "actualizar, cancelar o marcar como entregada una orden concreta. NO la "
        "uses para consultar el estado actual de una orden: para eso está "
        "get_sales_orders."
    ),
}


def tool_schemas_for(role: str) -> list[dict[str, Any]]:
    """Anthropic tool declarations for the tools this role may use.

    Sorted by name: an unstable order would change the prompt bytes on every request.
    """
    return [
        {
            "name": tool.value,
            "description": _DESCRIPTIONS[tool],
            "input_schema": TOOL_SCHEMAS[tool].model_json_schema(),
        }
        for tool in sorted(visible_tools_for(role), key=lambda t: t.value)
    ]
