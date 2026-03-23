---
name: stock_daily_scan
description: Daily scan of watchlist stocks — combines technical signals, news sentiment, and trend analysis to produce trading recommendations and execute trades
metadata: {"openclaw":{"requires":{"env":["LOCAL_API_KEY"]}}}
---

# Stock Daily Scan

When the user asks for a market scan, daily report, or recommendations (e.g. "每日扫描", "推荐", "今日分析", "看看市场"):

## Execution Flow

### Step 1: Get watchlist

```
exec curl -s -H "Authorization: Bearer $LOCAL_API_KEY" \
  "http://127.0.0.1:8000/watchlist"
```

If empty, tell user to add stocks first: "自选列表为空，先加几只: 加自选 AAPL"

### Step 2: For each symbol, gather data

**Technical signal** (past 60 days for sufficient data):
```
exec curl -s -H "Authorization: Bearer $LOCAL_API_KEY" \
  "http://127.0.0.1:8000/signal?symbol={SYMBOL}&start={60_DAYS_AGO}&end={TODAY}&capital=10000"
```

**Backtest** (past 1 year, all 3 strategies):
```
exec curl -s -H "Authorization: Bearer $LOCAL_API_KEY" \
  "http://127.0.0.1:8000/backtest?symbol={SYMBOL}&strategy=rsi&start={1_YEAR_AGO}&end={TODAY}"
exec curl -s -H "Authorization: Bearer $LOCAL_API_KEY" \
  "http://127.0.0.1:8000/backtest?symbol={SYMBOL}&strategy=ma_crossover&start={1_YEAR_AGO}&end={TODAY}"
exec curl -s -H "Authorization: Bearer $LOCAL_API_KEY" \
  "http://127.0.0.1:8000/backtest?symbol={SYMBOL}&strategy=macd&start={1_YEAR_AGO}&end={TODAY}"
```

### Step 3: News sentiment (Agent does this directly)

Search the web for recent news about each symbol. Assess sentiment based on:
- Earnings reports and guidance
- Analyst upgrades/downgrades
- Sector-wide events
- Regulatory or geopolitical risks

Classify as: bullish / bearish / neutral with confidence (0-1).

### Step 4: Trend classification

Combine technical signal + news to determine trend:

| Condition | Trend |
|-----------|-------|
| signal.action = buy AND score > 0.3 AND news bullish | 上涨趋势 |
| signal.action = sell AND score < -0.3 AND news bearish | 下跌趋势 |
| Otherwise | 横盘震荡 |

### Step 5: Strategy matching + trade decision

| Trend | Strategy | Trade Action |
|-------|----------|-------------|
| 上涨趋势 | MA Crossover / MACD (pick higher Sharpe) | **buy**, size = signal.size |
| 下跌趋势 | 观望或减仓 | **sell** if holding, otherwise skip |
| 横盘震荡 | RSI 均值回归 | **buy** only if RSI signal = buy, small size (×0.5) |

### Step 6: Output report

Format as:

```
📊 每日扫描报告 (2025-03-23)

1. AAPL — 上涨趋势 ⬆️
   技术信号: buy (score 0.65)
   最佳策略: MACD (Sharpe 1.32, 年化 15%)
   舆情: 看涨 — Q1 iPhone 销量超预期
   建议: MACD 追动量，回调买入
   ✅ 交易: 建议买入 5% 仓位

2. TSLA — 横盘震荡 ↔️
   技术信号: hold (score 0.12)
   最佳策略: RSI (Sharpe 0.85, 年化 8%)
   舆情: 中性 — FSD 进展正常，无重大催化剂
   建议: RSI 均值回归策略，等待超卖区间
   ⏸️ 交易: 暂不操作

3. NVDA — 下跌趋势 ⬇️
   技术信号: sell (score -0.45)
   最佳策略: 观望
   舆情: 看跌 — 出口管制扩大
   建议: 暂时观望
   ⚠️ 交易: 如有持仓建议减仓
```

### Step 7: Execute trades (with confirmation)

After presenting the report, ask user: "是否执行以上交易建议？(全部执行 / 选择执行 / 跳过)"

**If user confirms**, for each actionable trade:

```
exec curl -s -X POST -H "Authorization: Bearer $LOCAL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "{SYMBOL}", "action": "{buy|sell}", "size": {SIZE}, "capital": {CAPITAL}, "start": "{60_DAYS_AGO}", "end": "{TODAY}", "gateway": "alpaca"}' \
  "http://127.0.0.1:8000/trade"
```

The `/trade` endpoint will:
1. Run risk check (position size, daily loss limit)
2. Send Telegram confirmation → wait for YES/NO reply
3. If confirmed → submit order to gateway
4. Return order status

**Trade result interpretation:**
- `status: "submitted"` → Order sent to broker, report order_id and qty
- `status: "blocked"` → Risk gate blocked the trade, report reason
- `status: "cancelled"` → User rejected via Telegram or timeout

Present each trade result:
```
交易执行结果:
  AAPL: ✅ 已提交 (订单 abc123, 5股 @ $178.50)
  MSFT: ❌ 风控拦截 — 单日亏损已达限额
  GOOG: ⏹️ 用户拒绝 (Telegram)
```

---

## Single stock analysis + trade

When the user asks about a specific stock (e.g. "分析 AAPL", "TSLA 怎么样"):

Run the same flow for just that one symbol, with more detail:
- Show all 3 strategy backtest results in a comparison table
- Include key price levels (recent high/low)
- Give a more detailed news summary
- Ask if user wants to execute the recommended trade

When the user explicitly wants to trade (e.g. "买入 AAPL", "卖出 TSLA", "执行交易"):

Directly call `/trade` with the appropriate parameters. Always confirm the details before executing:
"确认: 买入 AAPL, 仓位 5%, 资金 $10000, 通过 Alpaca 执行？"
