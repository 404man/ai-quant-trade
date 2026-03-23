# OpenClaw 接入指南

## 架构

```
OpenClaw (Agent 层)
├── 每日定时扫描 watchlist
│   ├── 搜索新闻 → 自己判断舆情（不调 Claude API）
│   ├── GET /signal → 技术信号 (RSI/MACD/MA/Volume)
│   ├── GET /backtest → 历史验证
│   └── 综合研判 → 趋势判断 + 策略匹配
├── 推送 Telegram / 输出报告
└── 管理 watchlist

FastAPI (数据层)
├── GET /signal — 纯技术信号
├── GET /backtest — 策略回测
├── GET /data — K线数据
├── GET /positions — 持仓
├── GET /watchlist — 自选列表
└── POST /trade — 下单
```

舆情判断由 OpenClaw Agent 自己完成（联网搜新闻 + AI 分析），不需要 `ANTHROPIC_API_KEY`。

---

## 前置条件

### 1. 启动后端

```bash
python -m uvicorn api.main:app --reload
```

确认：`curl http://127.0.0.1:8000/health` → `{"status":"ok"}`

### 2. 配置 API Key（可选）

`.env` 中设置 `LOCAL_API_KEY=your-token-here`。不设则跳过认证（开发模式）。

---

## Skills 列表

| Skill | 功能 | 触发词 |
|-------|------|--------|
| `stock_daily_scan` | 每日扫描 + 综合报告 | "每日扫描"、"推荐"、"分析 AAPL" |
| `stock_watchlist` | 管理自选列表 | "加自选 TSLA"、"自选列表"、"删自选" |
| `stock_signal` | 技术信号查询 | "信号 AAPL"、"signal TSLA" |
| `stock_backtest` | 策略回测 | "回测 AAPL"、"backtest TSLA macd" |
| `stock_positions` | 持仓查询 | "持仓"、"positions" |

### 加载

```
openclaw/skills/
├── stock_daily_scan/SKILL.md   ← 核心：每日扫描
├── stock_watchlist/SKILL.md    ← 自选管理
├── stock_signal/SKILL.md
├── stock_backtest/SKILL.md
└── stock_positions/SKILL.md
```

`stock_sentiment` 已废弃，舆情由 Agent 层直接完成。

---

## 接口速查

### GET /watchlist

```
/watchlist
```

返回：`[{symbol, notes, added_at}]`

### POST /watchlist

```json
{"symbol": "AAPL", "notes": "tech leader"}
```

### DELETE /watchlist/{symbol}

### GET /signal

```
/signal?symbol=AAPL&start=2025-02-21&end=2025-03-23&capital=500
```

返回：`action` (buy/sell/hold)、`score`、`size`、`rsi_signal`、`ma_signal`、`macd_signal`、`volume_ratio`、`risk_blocked`

### GET /backtest

```
/backtest?symbol=AAPL&strategy=rsi&start=2020-01-01&end=2024-12-31&position_size_pct=0.1
```

策略：`rsi` / `ma_crossover` / `macd`

### GET /positions

```
/positions
```

---

## 每日扫描流程

```
1. GET /watchlist → 获取所有自选
2. 对每只股票：
   ├── GET /signal → 技术信号
   ├── GET /backtest (×3 策略) → 历史 Sharpe
   └── Agent 搜索新闻 → 舆情判断
3. 综合趋势判断：
   ├── 上涨 → MA Crossover / MACD 追动量
   ├── 下跌 → 观望，严格止损
   └── 横盘 → RSI 均值回归
4. 输出报告 + 推送 Telegram
```

---

## 注意事项

- **数据源**：`.env` 设 `DATA_SOURCE=polygon` + `POLYGON_API_KEY=...` 绕过 Yahoo 限流
- **日期**：`start` 必须早于 `end`，否则 400
- **缓存**：拉取的数据自动写入 SQLite，相同范围命中缓存
