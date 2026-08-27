"""Stem tables and the Spanish lines the demo model "says".

This copy is model output, not application messaging, so it lives beside the demo
client instead of in app/application/messages.py. Every stem is stored already
lowercased and unaccented, and matches any word that starts with it.
"""

import re
from collections.abc import Mapping
from enum import Enum

from app.application.permissions import ToolName
from app.domain.constants import OrderStatus


class WriteSlot(str, Enum):
    """The two arguments a status change needs, so a clarification can name the missing one."""

    ORDER_ID = "order_id"
    NEW_STATUS = "new_status"


# Ordered on purpose: "cambia la orden 11" also mentions an order, so writes match first.
TOOL_STEMS: Mapping[ToolName, tuple[str, ...]] = {
    # "actualic"/"marqu" are the same verbs after the c/z spelling shift ("actualices").
    ToolName.UPDATE_ORDER_STATUS: (
        "actualic",
        "actualiz",
        "cambi",
        "cancel",
        "marc",
        "marqu",
        "mover",
        "muev",
        "pon",
    ),
    ToolName.GET_CLIENT_BALANCE: (
        "saldo",
        "deuda",
        "debe",
        "adeuda",
        "pago",
        "balance",
        "credito",
    ),
    ToolName.GET_SALES_ORDERS: (
        "orden",
        "pedido",
        "venta",
        "entreg",
        "pendiente",
        "cancelad",
        "proceso",
    ),
}

# Suffixes that veto a stem match: a past participle ("canceladas") names a state, not a command.
STEM_EXCLUSIONS: Mapping[ToolName, tuple[str, ...]] = {
    ToolName.UPDATE_ORDER_STATUS: ("ada", "adas", "ado", "ados"),
}

STATUS_STEMS: Mapping[OrderStatus, tuple[str, ...]] = {
    OrderStatus.PENDING: ("pendiente",),
    OrderStatus.IN_PROGRESS: ("proceso", "curso", "progreso"),
    OrderStatus.DELIVERED: ("entregad", "entregar"),
    OrderStatus.CANCELLED: ("cancel",),
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

# Never interpolated: each line is its own opener in CLARIFICATION_OPENERS below.
MISSING_SLOT_ASKS: Mapping[WriteSlot, str] = {
    WriteSlot.ORDER_ID: (
        "Ya tengo el estado destino, pero me falta el número de la orden. "
        "Dímelo y te preparo el cambio; por ejemplo: «la 12»."
    ),
    WriteSlot.NEW_STATUS: (
        "Ya tengo la orden, pero me falta el estado destino: pendiente, en proceso, "
        "entregada o cancelada. ¿A cuál la muevo?"
    ),
}

# Words that carry no intent of their own, so a message made only of these, a number, a status
# and the pending tool's own verb is an answer to the pending question rather than a new request.
SLOT_ANSWER_FILLERS: frozenset[str] = frozenset(
    {
        "a",
        "al",
        "de",
        "del",
        "el",
        "en",
        "es",
        "favor",
        "la",
        "las",
        "lo",
        "los",
        "numero",
        "orden",
        "ordenes",
        "pedido",
        "pedidos",
        "por",
    }
)

# A handful, not thirty; the answer says how many it is showing out of how many it found.
CANDIDATES_SAMPLE_SIZE = 5
CANDIDATES_QUESTION = "¿Cuál de estas órdenes quieres cambiar?"
CANDIDATES_ANSWER = (
    "{question} Te muestro {shown} de las {found} que admiten ese cambio: {sample}. "
    "Dime su número; por ejemplo: «la {example}»."
)
CANDIDATES_EMPTY_ANSWER = "No encontré ninguna orden a la que pueda aplicarle ese cambio."

# Every line that asks for a missing argument, by the tool it asks about: the client recognises
# its own question by these openers, so the next message completes the intent it left hanging.
CLARIFICATION_OPENERS: Mapping[ToolName, tuple[str, ...]] = {
    ToolName.GET_CLIENT_BALANCE: (CLARIFICATIONS[ToolName.GET_CLIENT_BALANCE],),
    ToolName.UPDATE_ORDER_STATUS: (
        CLARIFICATIONS[ToolName.UPDATE_ORDER_STATUS],
        CANDIDATES_QUESTION,
        *MISSING_SLOT_ASKS.values(),
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

# A prefix, not the id: one id shared by every proposal makes an orphan look answered.
TOOL_USE_ID_PREFIX = "demo-tool-use"

UNTRUSTED_PATTERN = re.compile(r"<untrusted_data>\s*(?P<payload>.*?)\s*</untrusted_data>", re.S)
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
WORD_PATTERN = re.compile(r"[a-z0-9]+")
