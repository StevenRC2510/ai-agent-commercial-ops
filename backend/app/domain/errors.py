"""Domain exceptions. Generic exceptions never cross a layer boundary."""


class DomainError(Exception):
    """Base class for every expected business failure."""


class ClientNotFoundError(DomainError):
    """Raised when a referenced client does not exist."""


class OrderNotFoundError(DomainError):
    """Raised when a referenced order does not exist."""


class InvalidTransitionError(DomainError):
    """Raised when an order status change violates the allowed transition table."""
