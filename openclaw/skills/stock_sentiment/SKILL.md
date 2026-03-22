---
name: stock_sentiment
description: Query AI sentiment analysis for a stock from the AI quant trading system
metadata: {"openclaw":{"requires":{"env":["LOCAL_API_KEY"]}}}
---

# Stock Sentiment

When the user asks about stock sentiment (e.g. "情绪 TSLA", "sentiment AAPL", "MSFT市场情绪"):

1. **Extract parameters:**
   - `symbol` (required): Stock ticker

2. **Call the API:**
   ```
   exec curl -s -H "Authorization: Bearer $LOCAL_API_KEY" \
     "http://127.0.0.1:8000/sentiment?symbol={SYMBOL}"
   ```

3. **Interpret the response:**
   The JSON response contains:
   - `sentiment`: One of `bullish` (看涨), `bearish` (看跌), `neutral` (中性)
   - `confidence`: 0.0 to 1.0 confidence score

   Present in natural language, e.g.:
   "TSLA 当前市场情绪: 看涨 (置信度 72%)"

4. **Error handling:**
   - If confidence is below 0.5, note that the signal is weak
   - If sentiment is neutral, mention it may be due to limited recent news
