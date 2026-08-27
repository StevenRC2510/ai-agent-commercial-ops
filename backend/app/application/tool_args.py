"""Argument schemas for tools, one per tool. Change when a tool's signature changes."""

import re
from collections.abc import Mapping
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.application.permissions import ToolName
from app.domain.constants import DEFAULT_ORDER_LIMIT, MAX_ORDER_LIMIT, OrderStatus


class GetSalesOrdersArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: OrderStatus | None = None
    date_from: date | None = None
    date_to: date | None = None
    client_id: int | None = Field(default=None, gt=0, strict=True)
    limit: int = Field(default=DEFAULT_ORDER_LIMIT, gt=0, strict=True)

    @model_validator(mode="after")
    def normalise(self) -> "GetSalesOrdersArgs":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not be after date_to")
        if self.limit > MAX_ORDER_LIMIT:
            self.limit = MAX_ORDER_LIMIT  # clamp so safe_args describes what actually runs
        return self


class GetClientBalanceArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: int = Field(gt=0, strict=True)


class UpdateOrderStatusArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: int = Field(gt=0, strict=True)
    new_status: OrderStatus
    reason: str = Field(min_length=3, max_length=280)

    @field_validator("reason", mode="before")
    @classmethod
    def collapse_whitespace(cls, value: object) -> object:
        """Collapse to one line so a reason cannot forge a second sentence on the card."""
        if not isinstance(value, str):
            return value
        return re.sub(r"\s+", " ", value).strip()


TOOL_SCHEMAS: Mapping[ToolName, type[BaseModel]] = {
    ToolName.GET_SALES_ORDERS: GetSalesOrdersArgs,
    ToolName.GET_CLIENT_BALANCE: GetClientBalanceArgs,
    ToolName.UPDATE_ORDER_STATUS: UpdateOrderStatusArgs,
}
