---
name: stock_backtest
description: Query stock backtesting results (Sharpe, drawdown, returns) from the AI quant trading system
metadata: {"openclaw":{"requires":{"env":["LOCAL_API_KEY"]}}}
---

# Stock Backtest

When the user asks to backtest a stock (e.g. "回测 AAPL", "backtest TSLA rsi", "回测 MSFT ma交叉"):

1. **Extract parameters:**
   - `symbol` (required): Stock ticker, e.g. AAPL, TSLA, MSFT
   - `strategy` (optional): `rsi`, `ma_crossover`, or `macd`. Default: `rsi`
   - `start` (optional): Start date YYYY-MM-DD. Default: `2020-01-01`
   - `end` (optional): End date YYYY-MM-DD. Default: today
   - `position_size_pct` (optional): Position size 0.01–1.0. Default: `0.1`

2. **Call the API:**
   ```
   exec curl -s -H "Authorization: Bearer $LOCAL_API_KEY" \
     "http://127.0.0.1:8000/backtest?symbol={SYMBOL}&strategy={STRATEGY}&start={START}&end={END}&position_size_pct={POSITION_SIZE_PCT}"
   ```

3. **Interpret the response:**
   - `sharpe_ratio`: Risk-adjusted return (> 1.0 is good, > 2.0 is excellent)
   - `max_drawdown`: Worst peak-to-trough loss (e.g. -0.15 = -15%)
   - `annual_return`: Annualized return (e.g. 0.12 = 12%)
   - `trade_count`: Number of trades executed
   - `avg_holding_days`: Average holding period in days

   Present results in a clear summary, e.g.:
   "AAPL RSI策略回测 (2020-2024): Sharpe 1.32, 年化收益 15.2%, 最大回撤 -12.3%, 共62笔交易, 平均持仓10天"

4. **Error handling:**
   - 404: No price data available for this symbol
   - 400: Invalid strategy name or start >= end
