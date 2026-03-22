---
name: stock_positions
description: Query current portfolio positions and account status from the AI quant trading system
metadata: {"openclaw":{"requires":{"env":["LOCAL_API_KEY"]}}}
---

# Stock Positions

When the user asks about positions or account status (e.g. "持仓", "positions", "账户状态", "我现在有什么股票"):

1. **Call the API:**
   ```
   exec curl -s -H "Authorization: Bearer $LOCAL_API_KEY" \
     "http://127.0.0.1:8000/positions"
   ```

2. **Interpret the response:**
   The JSON response contains:
   - `positions`: Array of position objects, each with:
     - `symbol`: Stock ticker
     - `qty`: Number of shares
     - `avg_entry_price`: Average entry price
     - `side`: Position direction (long/short)
   - `count`: Total number of open positions

   Present as a formatted summary, e.g.:
   "当前持仓 (2个):
    - AAPL: 5股 多头 @ $178.50
    - TSLA: 3股 多头 @ $245.00"

   If no positions:
   "当前空仓，没有持仓。"
