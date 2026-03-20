import pytest
from unittest.mock import patch, MagicMock
from db.schema import init_db
from api.services.trade_service import TradeService


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


@pytest.fixture
def svc(db):
    return TradeService(db_path=db)


def test_get_daily_loss_returns_zero_when_no_record(svc):
    result = svc.get_daily_loss("2026-01-01")
    assert result == 0.0


def test_record_loss_and_retrieve(svc):
    svc.record_loss("2026-01-01", 15.50)
    assert svc.get_daily_loss("2026-01-01") == 15.50


def test_record_loss_upserts(svc):
    svc.record_loss("2026-01-01", 10.0)
    svc.record_loss("2026-01-01", 20.0)
    assert svc.get_daily_loss("2026-01-01") == 20.0


def test_get_position_count_zero_initially(svc):
    assert svc.get_position_count() == 0


def test_sync_positions_writes_to_db(svc):
    mock_position = MagicMock()
    mock_position.symbol = "AAPL"
    mock_position.qty = "10"
    mock_position.avg_entry_price = "185.50"
    mock_position.side = "long"

    with patch.object(svc, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_all_positions.return_value = [mock_position]
        mock_get_client.return_value = mock_client
        svc.sync_positions()

    assert svc.get_position_count() == 1


def test_submit_order_returns_order_id(svc):
    mock_order = MagicMock()
    mock_order.id = "test-order-123"

    with patch.object(svc, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.submit_order.return_value = mock_order
        mock_get_client.return_value = mock_client
        order_id = svc.submit_order("AAPL", "buy", 1.0)

    assert order_id == "test-order-123"


def test_cancel_order_calls_alpaca(svc):
    with patch.object(svc, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        svc.cancel_order("test-order-456")

    mock_client.cancel_order_by_id.assert_called_once_with("test-order-456")
