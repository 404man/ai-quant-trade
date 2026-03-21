from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

GatewayStatus = Literal["connected", "disconnected", "error"]

SENSITIVE_FIELDS = {"secret_key", "api_secret"}


@dataclass
class OrderResult:
    status: str
    order_id: str | None
    qty: float | None
    price_estimate: float | None
    reason: str | None


class BaseGateway(ABC):
    name: str
    label: str
    status: GatewayStatus = "disconnected"

    @abstractmethod
    def connect(self, config: dict) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def send_order(self, symbol: str, action: str, qty: float) -> OrderResult: ...

    def get_status(self) -> GatewayStatus:
        return self.status
