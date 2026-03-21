import pytest
from unittest.mock import patch, MagicMock


def test_alpaca_connect_success():
    from api.gateways.alpaca import AlpacaGateway
    gw = AlpacaGateway()
    mock_client = MagicMock()
    with patch("api.gateways.alpaca.TradingClient", return_value=mock_client):
        gw.connect({"api_key": "PK", "secret_key": "SK", "mode": "paper"})
    assert gw.status == "connected"
    mock_client.get_account.assert_called_once()


def test_alpaca_connect_failure():
    from api.gateways.alpaca import AlpacaGateway
    gw = AlpacaGateway()
    with patch("api.gateways.alpaca.TradingClient", side_effect=Exception("bad creds")):
        with pytest.raises(Exception, match="bad creds"):
            gw.connect({"api_key": "bad", "secret_key": "bad", "mode": "paper"})


def test_alpaca_send_order():
    from api.gateways.alpaca import AlpacaGateway
    gw = AlpacaGateway()
    mock_client = MagicMock()
    mock_order = MagicMock()
    mock_order.id = "ord-abc-123"
    mock_client.submit_order.return_value = mock_order
    with patch("api.gateways.alpaca.TradingClient", return_value=mock_client):
        gw.connect({"api_key": "PK", "secret_key": "SK", "mode": "paper"})
    result = gw.send_order("AAPL", "buy", 10.0)
    assert result.status == "submitted"
    assert result.order_id == "ord-abc-123"
    assert result.qty == 10.0


def test_alpaca_disconnect():
    from api.gateways.alpaca import AlpacaGateway
    gw = AlpacaGateway()
    mock_client = MagicMock()
    with patch("api.gateways.alpaca.TradingClient", return_value=mock_client):
        gw.connect({"api_key": "PK", "secret_key": "SK", "mode": "paper"})
    gw.disconnect()
    assert gw.status == "disconnected"
    assert gw._client is None
