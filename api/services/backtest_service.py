import math

import pandas as pd
import vectorbt as vbt
from strategies.rsi_strategy import generate_signals as rsi_signals
from strategies.ma_crossover_strategy import generate_signals as ma_signals
from strategies.bar_runner import run_bar_by_bar

COMMISSION_PER_TRADE = 1.0  # $1 per trade
SLIPPAGE_PCT = 0.001         # 0.1%
RSI_MAX_HOLDING_DAYS = 10

STRATEGY_MAP = {
    "rsi": rsi_signals,
    "ma": ma_signals,
}


def _apply_max_duration(entries: pd.Series, exits: pd.Series, max_duration: int) -> pd.Series:
    """Add forced exit signals after max_duration days of holding."""
    # Assumes entries and exits are mutually exclusive on the same bar
    # (holds for RSI strategy where buy and sell conditions cannot both be true)
    new_exits = exits.copy()
    in_position = False
    entry_day = None

    for i, (idx, is_entry) in enumerate(entries.items()):
        if not in_position and is_entry:
            in_position = True
            entry_day = i
        elif in_position:
            if exits.iloc[i]:
                in_position = False
                entry_day = None
            elif (i - entry_day) >= max_duration:
                new_exits.iloc[i] = True
                in_position = False
                entry_day = None

    return new_exits


class BacktestService:
    def run(
        self,
        price_data: list[dict],
        strategy: str,
        position_size_pct: float = 0.10,
        mode: str = "vectorized",
    ) -> dict:
        if strategy not in STRATEGY_MAP:
            raise ValueError(f"Unknown strategy: {strategy}. Valid: {list(STRATEGY_MAP.keys())}")

        if not 0 < position_size_pct <= 1.0:
            raise ValueError(f"position_size_pct must be in (0, 1.0], got {position_size_pct}")

        if len(price_data) < 30:
            return {
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "annual_return": 0.0,
                "trade_count": 0,
                "avg_holding_days": 0.0,
            }

        df = pd.DataFrame(price_data)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        close = df["close"]

        signal_fn = STRATEGY_MAP[strategy]
        if mode == "bar_by_bar":
            signals = run_bar_by_bar(close, signal_fn, lookback=50)
        elif mode == "vectorized":
            signals = signal_fn(close)
        else:
            raise ValueError(f"Unknown mode: {mode}. Valid: ['vectorized', 'bar_by_bar']")

        entries = signals == "buy"
        exits = signals == "sell"

        if strategy == "rsi":
            exits = _apply_max_duration(entries, exits, RSI_MAX_HOLDING_DAYS)

        pf = vbt.Portfolio.from_signals(
            close,
            entries=entries,
            exits=exits,
            size=position_size_pct,
            size_type="percent",  # allocate fraction of current capital per trade
            fees=COMMISSION_PER_TRADE / close.mean(),
            slippage=SLIPPAGE_PCT,
            freq="D",
        )
        # trades.duration is in bars; freq="D" means bars = calendar days

        stats = pf.stats()

        sharpe_raw = stats.get("Sharpe Ratio", 0.0)
        sharpe = float(sharpe_raw) if (sharpe_raw is not None and not (isinstance(sharpe_raw, float) and math.isnan(sharpe_raw)) and not (isinstance(sharpe_raw, float) and math.isinf(sharpe_raw))) else 0.0

        max_dd_raw = stats.get("Max Drawdown [%]", 0.0)
        if max_dd_raw is None or (isinstance(max_dd_raw, float) and math.isnan(max_dd_raw)):
            max_dd = 0.0
        else:
            # vectorbt returns Max Drawdown [%] as a positive number (e.g. 15.3 for a 15.3% drawdown)
            # divide by -100.0 to convert to a negative fraction (e.g. -0.153)
            max_dd = float(max_dd_raw) / -100.0

        total_return = float(stats.get("Total Return [%]", 0.0) or 0.0) / 100.0
        trade_count = int(stats.get("Total Trades", 0) or 0)

        n_days = len(close)
        annual_return = (1 + total_return) ** (252 / max(n_days, 1)) - 1

        trades = pf.trades
        if len(trades.records_arr) > 0:
            avg_holding = float(trades.duration.mean())
        else:
            avg_holding = 0.0

        return {
            "sharpe_ratio": round(sharpe, 4),
            "max_drawdown": round(max_dd, 4),
            "annual_return": round(annual_return, 4),
            "trade_count": trade_count,
            "avg_holding_days": round(avg_holding, 1),
        }
