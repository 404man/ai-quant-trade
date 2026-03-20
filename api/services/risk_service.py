from dataclasses import dataclass
from typing import Optional

# Hard limits matching spec
MIN_CAPITAL = 200.0          # $200 minimum to trade
DAILY_LOSS_LIMIT_PCT = 0.02  # 2% of capital
MAX_POSITIONS = 5
MAX_TRADE_PCT = 0.02         # 2% per trade


@dataclass
class RiskCheckResult:
    allowed: bool
    reason: Optional[str] = None


class RiskGate:
    """
    Pre-execution risk guard (vnpy pattern).
    Signals must pass through check() before order submission.
    Checks are stateless — all portfolio state is passed in explicitly.
    Phase 4 will use this via a stateful wrapper that reads SQLite.
    """

    def check(
        self,
        *,
        capital: float,
        daily_loss: float,
        current_positions: int,
        proposed_trade_value: float,
    ) -> RiskCheckResult:
        """
        Validate a proposed trade against all risk limits.
        Returns RiskCheckResult(allowed=True) if all checks pass.
        Checks are evaluated in order; first failure short-circuits.

        Args:
            capital: total portfolio capital ($)
            daily_loss: realized loss so far today ($ positive = loss)
            current_positions: number of open positions
            proposed_trade_value: dollar value of the proposed trade
        """
        if capital < MIN_CAPITAL:
            return RiskCheckResult(
                allowed=False,
                reason=f"Capital ${capital:.2f} below minimum ${MIN_CAPITAL:.2f}"
            )

        if capital > 0 and daily_loss / capital >= DAILY_LOSS_LIMIT_PCT:
            return RiskCheckResult(
                allowed=False,
                reason=f"Daily loss limit reached: ${daily_loss:.2f} >= {DAILY_LOSS_LIMIT_PCT*100:.0f}% of capital"
            )

        if current_positions >= MAX_POSITIONS:
            return RiskCheckResult(
                allowed=False,
                reason=f"Max positions reached: {current_positions}/{MAX_POSITIONS}"
            )

        if capital > 0 and proposed_trade_value / capital > MAX_TRADE_PCT:
            return RiskCheckResult(
                allowed=False,
                reason=f"Trade size ${proposed_trade_value:.2f} exceeds {MAX_TRADE_PCT*100:.0f}% of capital (${capital * MAX_TRADE_PCT:.2f})"
            )

        return RiskCheckResult(allowed=True)
