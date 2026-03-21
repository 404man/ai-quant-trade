from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

from api.gateways.base import BaseGateway, OrderResult


def _side(action: str) -> OrderSide:
    return OrderSide.BUY if action.lower() == "buy" else OrderSide.SELL


class AlpacaGateway(BaseGateway):
    name = "alpaca"
    label = "Alpaca"

    def __init__(self):
        self._client: TradingClient | None = None

    def connect(self, config: dict) -> None:
        paper = config.get("mode", "paper") == "paper"
        self._client = TradingClient(
            api_key=config["api_key"],
            secret_key=config["secret_key"],
            paper=paper,
        )
        self._client.get_account()  # validate credentials
        self.status = "connected"

    def disconnect(self) -> None:
        self._client = None
        self.status = "disconnected"

    def send_order(self, symbol: str, action: str, qty: float) -> OrderResult:
        if self._client is None:
            raise RuntimeError("Alpaca gateway not connected")
        req = MarketOrderRequest(
            symbol=symbol.upper(),
            qty=qty,
            side=_side(action),
            time_in_force=TimeInForce.DAY,
        )
        order = self._client.submit_order(req)
        return OrderResult(
            status="submitted",
            order_id=str(order.id),
            qty=qty,
            price_estimate=None,
            reason=None,
        )
