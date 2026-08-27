"""Keyword tables and the Spanish lines the demo model "says".

This copy is model output, not application messaging, so it lives beside the demo
client instead of in app/application/messages.py. Every keyword is stored already
lowercased and unaccented, because matching runs on normalised text.
"""

import re
from collections.abc import Mapping

from app.application.permissions import ToolName
from app.domain.constants import OrderStatus

# Ordered on purpose: "cambia la orden 11" also mentions an order, so writes match first.
KEYWORDS: Mapping[ToolName, tuple[str, ...]] = {
    ToolName.UPDATE_ORDER_STATUS: (
        "cambia",
        "cambiar",
        "cambiale",
        "actualiza",
        "actualizar",
        "cancela",
        "cancelar",
        "marca",
        "marcar",
        "pon",
        "poner",
        "mueve",
        "mover",
    ),
    ToolName.GET_CLIENT_BALANCE: (
        "saldo",
        "saldos",
        "deuda",
        "deudas",
        "debe",
        "adeuda",
        "pago",
        "pagos",
        "balance",
        "credito",
    ),
    ToolName.GET_SALES_ORDERS: (
        "orden",
        "ordenes",
        "pedido",
        "pedidos",
        "venta",
        "ventas",
        "entrega",
        "entregas",
        "pendiente",
        "pendientes",
        "entregada",
        "entregadas",
        "entregado",
        "entregados",
        "cancelada",
        "canceladas",
        "proceso",
    ),
}

STATUS_KEYWORDS: Mapping[OrderStatus, tuple[str, ...]] = {
    OrderStatus.PENDING: ("pendiente", "pendientes"),
    OrderStatus.IN_PROGRESS: ("proceso", "curso", "progreso"),
    OrderStatus.DELIVERED: ("entregada", "entregadas", "entregado", "entregados", "entregar"),
    OrderStatus.CANCELLED: (
        "cancelada",
        "canceladas",
        "cancelado",
        "cancelados",
        "cancela",
        "cancelar",
    ),
}

CLARIFICATIONS: Mapping[ToolName, str] = {
    ToolName.GET_CLIENT_BALANCE: (
        "¿De qué cliente quieres el saldo? Dime su número; por ejemplo: «saldo del cliente 1»."
    ),
    ToolName.UPDATE_ORDER_STATUS: (
        "Para cambiar una orden necesito su número y el estado destino "
        "(pendiente, en proceso, entregada o cancelada). Por ejemplo: "
        "«marca la orden #11 como entregada»."
    ),
}

CAPABILITIES_REPLY = (
    "Estoy en modo demostración: no hay un modelo real detrás, pero el sistema completo sí "
    "funciona. Puedo consultar órdenes (por estado o por rango de fechas), consultar el saldo "
    "de un cliente y proponer un cambio de estado de una orden, que siempre pasa por tu "
    "confirmación."
)

ORDERS_ANSWER = "Encontré {count} órdenes. Las más recientes: {sample}."
ORDERS_EMPTY_ANSWER = "No encontré ninguna orden con esos filtros."
ORDER_LINE = "#{order_id} ({status}, ${total})"
ORDERS_SAMPLE_SIZE = 3

BALANCE_ANSWER = (
    "El cliente #{client_id} ({name}) tiene un saldo de ${balance}: ${total_ordered} en "
    "órdenes y ${total_paid} en pagos, sobre un límite de crédito de ${credit_limit}."
)

TOOL_ERROR_ANSWER = "La consulta no devolvió datos: {error}"
LOOP_GUARD_REPLY = "Ya consulté lo que podía para esta petición."

WRITE_REASON = "Solicitado por el usuario en modo demostración."

TOOL_USE_ID = "demo-tool-use"

UNTRUSTED_PATTERN = re.compile(r"<untrusted_data>\s*(?P<payload>.*?)\s*</untrusted_data>", re.S)
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
WORD_PATTERN = re.compile(r"[a-z0-9]+")
