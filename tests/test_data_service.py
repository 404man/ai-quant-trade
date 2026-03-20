import pytest
from unittest.mock import patch
import pandas as pd
from db.schema import init_db
from api.services.data_service import DataService


@pytest.fixture
def tmp_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return db_path


def make_mock_yf_data():
    """返回模拟的 yfinance DataFrame"""
    dates = pd.date_range("2024-01-02", periods=3, freq="B")
    df = pd.DataFrame({
        "Open": [185.0, 186.0, 187.0],
        "High": [187.0, 188.0, 189.0],
        "Low":  [184.0, 185.0, 186.0],
        "Close": [186.0, 187.0, 188.0],
        "Volume": [50000000, 51000000, 52000000],
    }, index=dates)
    df.index.name = "Date"
    return df


def test_fetch_returns_list_of_dicts(tmp_db):
    svc = DataService(db_path=tmp_db)
    with patch("api.services.data_service.yf.download", return_value=make_mock_yf_data()):
        result = svc.fetch("AAPL", "2024-01-01", "2024-01-05")
    assert isinstance(result, list)
    assert len(result) == 3
    assert set(result[0].keys()) == {"date", "open", "high", "low", "close", "volume"}


def test_fetch_caches_result(tmp_db):
    svc = DataService(db_path=tmp_db)
    with patch("api.services.data_service.yf.download", return_value=make_mock_yf_data()) as mock_dl:
        svc.fetch("AAPL", "2024-01-01", "2024-01-05")
        svc.fetch("AAPL", "2024-01-01", "2024-01-05")
    # Second call should read from cache, not call yfinance again
    assert mock_dl.call_count == 1


def test_fetch_returns_sorted_by_date(tmp_db):
    svc = DataService(db_path=tmp_db)
    with patch("api.services.data_service.yf.download", return_value=make_mock_yf_data()):
        result = svc.fetch("AAPL", "2024-01-01", "2024-01-05")
    dates = [r["date"] for r in result]
    assert dates == sorted(dates)


def test_fetch_empty_date_range_returns_empty_list(tmp_db):
    svc = DataService(db_path=tmp_db)
    with patch("api.services.data_service.yf.download", return_value=pd.DataFrame()):
        result = svc.fetch("AAPL", "2024-01-01", "2024-01-01")
    assert result == []


def test_fetch_invalid_date_raises_value_error(tmp_db):
    svc = DataService(db_path=tmp_db)
    with pytest.raises(ValueError, match="Invalid date format"):
        svc.fetch("AAPL", "01/01/2024", "2024-01-31")


def test_fetch_different_range_fetches_yfinance(tmp_db):
    """A broader range request should re-fetch even if a narrower range is cached."""
    svc = DataService(db_path=tmp_db)
    with patch("api.services.data_service.yf.download", return_value=make_mock_yf_data()) as mock_dl:
        svc.fetch("AAPL", "2024-01-02", "2024-01-04")  # narrow range
        svc.fetch("AAPL", "2024-01-01", "2024-01-10")  # broader range
    assert mock_dl.call_count == 2
