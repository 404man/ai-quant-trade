import ccxt
from api.gateways.base import BaseGateway, OrderResult


class BinanceGateway(BaseGateway):
    name = "binance"
    label = "Binance"

    def __init__(self):
        self._exchange: ccxt.binance | None = None

    def connect(self, config: dict) -> None:
        self._exchange = ccxt.binance({
            "apiKey": config["api_key"],
            "secret": config["api_secret"],
        })
        self._exchange.fetch_balance()  # validate credentials
        self.status = "connected"

    def disconnect(self) -> None:
        self._exchange = None
        self.status = "disconnected"

    def send_order(self, symbol: str, action: str, qty: float) -> OrderResult:
        if self._exchange is None:
            raise RuntimeError("Binance gateway not connected")
        result = self._exchange.create_market_order(symbol, action.lower(), qty)
        return OrderResult(
            status="submitted",
            order_id=str(result.get("id")),
            qty=qty,
            price_estimate=result.get("price"),
            reason=None,
        )
