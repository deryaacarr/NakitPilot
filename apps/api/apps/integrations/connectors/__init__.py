"""Connector package public API."""

from apps.integrations.connectors.base import AccountingConnector, BaseConnector
from apps.integrations.connectors.registry import (
    build,
    get,
    known_providers,
    list_providers,
    register,
)
from apps.integrations.connectors.types import (
    FetchPage,
    NormalizedCompany,
    NormalizedCustomer,
    NormalizedInvoice,
    NormalizedPayment,
)

__all__ = [
    "AccountingConnector",
    "BaseConnector",
    "FetchPage",
    "NormalizedCompany",
    "NormalizedCustomer",
    "NormalizedInvoice",
    "NormalizedPayment",
    "build",
    "get",
    "known_providers",
    "list_providers",
    "register",
]
