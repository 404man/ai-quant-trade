import pytest
from api.services.risk_service import RiskGate, RiskCheckResult


def make_gate() -> RiskGate:
    return RiskGate()


def valid_params() -> dict:
    return {
        "capital": 1000.0,
        "daily_loss": 0.0,
        "current_positions": 0,
        "proposed_trade_value": 10.0,  # 1% of capital — within 2% limit
    }


def test_allows_valid_trade():
    result = make_gate().check(**valid_params())
    assert result.allowed is True


def test_blocks_below_min_capital():
    params = valid_params()
    params["capital"] = 150.0  # below $200 minimum
    result = make_gate().check(**params)
    assert result.allowed is False


def test_blocks_daily_loss_limit():
    params = valid_params()
    params["daily_loss"] = 21.0  # 21/1000 = 2.1% > 2% limit
    result = make_gate().check(**params)
    assert result.allowed is False


def test_blocks_max_positions():
    params = valid_params()
    params["current_positions"] = 5  # at max
    result = make_gate().check(**params)
    assert result.allowed is False


def test_blocks_oversized_trade():
    params = valid_params()
    params["proposed_trade_value"] = 25.0  # 25/1000 = 2.5% > 2% limit
    result = make_gate().check(**params)
    assert result.allowed is False


def test_reason_populated_on_block():
    params = valid_params()
    params["capital"] = 100.0
    result = make_gate().check(**params)
    assert result.allowed is False
    assert result.reason is not None
    assert len(result.reason) > 0


def test_reason_none_on_allow():
    result = make_gate().check(**valid_params())
    assert result.reason is None


def test_checks_order_capital_first():
    # Both capital AND daily_loss are violations — capital check fires first
    params = valid_params()
    params["capital"] = 100.0   # below min
    params["daily_loss"] = 50.0  # also over daily limit
    result = make_gate().check(**params)
    assert "Capital" in result.reason or "capital" in result.reason.lower()
