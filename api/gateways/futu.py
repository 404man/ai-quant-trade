from api.gateways.base import BaseGateway, OrderResult


class FutuGateway(BaseGateway):
    name = "futu"
    label = "富途"

    def connect(self, config: dict) -> None:
        raise RuntimeError("需先在本地运行 FutuOpenD 程序（默认端口 11111）")

    def disconnect(self) -> None:
        raise RuntimeError("需先在本地运行 FutuOpenD 程序（默认端口 11111）")

    def send_order(self, symbol: str, action: str, qty: float) -> OrderResult:
        raise RuntimeError("需先在本地运行 FutuOpenD 程序（默认端口 11111）")
