from api.gateways.base import BaseGateway, OrderResult


class IBGateway(BaseGateway):
    name = "ib"
    label = "Interactive Brokers"

    def connect(self, config: dict) -> None:
        raise RuntimeError("需先在本地运行 TWS 或 IB Gateway 程序（默认端口 7497）")

    def disconnect(self) -> None:
        raise RuntimeError("需先在本地运行 TWS 或 IB Gateway 程序（默认端口 7497）")

    def send_order(self, symbol: str, action: str, qty: float) -> OrderResult:
        raise RuntimeError("需先在本地运行 TWS 或 IB Gateway 程序（默认端口 7497）")
