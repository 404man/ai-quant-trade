import pytest
from unittest.mock import patch, MagicMock


def test_binance_connect_success():
    from api.gateways.binance import BinanceGateway
    gw = BinanceGateway()
    mock_exchange = MagicMock()
    with patch("api.gateways.binance.ccxt.binance", return_value=mock_exchange):
        gw.connect({"api_key": "key", "api_secret": "secret"})
    assert gw.status == "connected"
    mock_exchange.fetch_balance.assert_called_once()


def test_binance_connect_failure():
    from api.gateways.binance import BinanceGateway
    gw = BinanceGateway()
    mock_exchange = MagicMock()
    mock_exchange.fetch_balance.side_effect = Exception("Invalid API key")
    with patch("api.gateways.binance.ccxt.binance", return_value=mock_exchange):
        with pytest.raises(Exception, match="Invalid API key"):
            gw.connect({"api_key": "bad", "api_secret": "bad"})


def test_binance_send_order():
    from api.gateways.binance import BinanceGateway
    gw = BinanceGateway()
    mock_exchange = MagicMock()
    mock_exchange.create_market_order.return_value = {
        "id": "binance-ord-1",
        "price": 50000.0,
    }
    with patch("api.gateways.binance.ccxt.binance", return_value=mock_exchange):
        gw.connect({"api_key": "key", "api_secret": "secret"})
    result = gw.send_order("BTC/USDT", "buy", 0.01)
    assert result.status == "submitted"
    assert result.order_id == "binance-ord-1"
    assert result.qty == 0.01
    mock_exchange.create_market_order.assert_called_once_with("BTC/USDT", "buy", 0.01)


def test_binance_disconnect():
    from api.gateways.binance import BinanceGateway
    gw = BinanceGateway()
    mock_exchange = MagicMock()
    with patch("api.gateways.binance.ccxt.binance", return_value=mock_exchange):
        gw.connect({"api_key": "key", "api_secret": "secret"})
    gw.disconnect()
    assert gw.status == "disconnected"
    assert gw._exchange is None
