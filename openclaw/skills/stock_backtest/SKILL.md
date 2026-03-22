---
name: stock_backtest
description: Query stock backtesting results (Sharpe, drawdown, returns) from the AI quant trading system
metadata: {"openclaw":{"requires":{"env":["LOCAL_API_KEY"]}}}
---

# Stock Backtest

When the user asks to backtest a stock (e.g. "回测 AAPL", "backtest TSLA rsi", "回测 MSFT ma交叉"):

1. **Extract parameters:**
   - `symbol` (required): Stock ticker, e.g. AAPL, TSLA, MSFT
   - `strategy` (optional): `rsi` (RSI均值回归) or `ma_crossover` (MA双线交叉). Default: `rsi`
   - `start` (optional): Start date YYYY-MM-DD. Default: `2020-01-01`
   - `end` (optional): End date YYYY-MM-DD. Default: `2024-12-31`

2. **Call the API:**
   ```
   exec curl -s -H "Authorization: Bearer $LOCAL_API_KEY" \
     "http://127.0.0.1:8000/backtest?symbol={SYMBOL}&strategy={STRATEGY}&start={START}&end={END}"
   ```

3. **Interpret the response:**
   The JSON response contains:
   - `sharpe_ratio`: Risk-adjusted return (> 1.0 is good, > 2.0 is excellent)
   - `max_drawdown`: Worst peak-to-trough loss (e.g. -0.15 = -15%)
   - `annual_return`: Annualized return (e.g. 0.12 = 12%)
   - `total_trades`: Number of trades executed
   - `win_rate`: Percentage of profitable trades

   Present results in a clear summary, e.g.:
   "AAPL RSI策略回测 (2020-2024): Sharpe 1.32, 年化收益 15.2%, 最大回撤 -12.3%, 共62笔交易, 胜率 58%"

4. **Error handling:**
   - 404: No price data available for this symbol
   - 400: Invalid strategy name (only `rsi` or `ma_crossover` supported)
