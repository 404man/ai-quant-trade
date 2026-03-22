---
name: stock_signal
description: Get current trading signal (buy/sell/hold) for a stock from the AI quant trading system
metadata: {"openclaw":{"requires":{"env":["LOCAL_API_KEY"]}}}
---

# Stock Signal

When the user asks for a trading signal (e.g. "信号 AAPL", "signal TSLA", "MSFT能买吗"):

1. **Extract parameters:**
   - `symbol` (required): Stock ticker
   - `capital` (optional): Portfolio capital in USD. Default: 500

2. **Compute date range:**
   - `start`: 30 calendar days before today (YYYY-MM-DD)
   - `end`: today (YYYY-MM-DD)

3. **Call the API:**
   ```
   exec curl -s -H "Authorization: Bearer $LOCAL_API_KEY" \
     "http://127.0.0.1:8000/signal?symbol={SYMBOL}&start={START}&end={END}&capital={CAPITAL}"
   ```

4. **Interpret the response:**
   The JSON response contains:
   - `action`: `buy` (买入), `sell` (卖出), or `hold` (持有)
   - `size`: Position size as fraction (e.g. 0.05 = 5% of capital)
   - `score`: Composite signal score (-1.0 to 1.0)
   - `risk_blocked`: Whether risk controls blocked the trade
   - `risk_reason`: Why risk controls blocked (if applicable)

   Present in natural language, e.g.:
   "AAPL 信号: 买入，建议仓位 5%，综合评分 0.78"
   or if blocked:
   "AAPL 原始信号为买入，但被风控拦截: 单日亏损已达限额"

5. **Error handling:**
   - 404: No price data for this symbol/date range
