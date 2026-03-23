# OpenClaw Agent 层架构设计

## 核心思路

AI 判断交给 OpenClaw Agent 层，FastAPI 只提供纯数据/技术面 API。

```
OpenClaw (Agent 层)
├── 每日定时扫描 watchlist
│   ├── 搜索新闻 → 自己判断舆情（免费，不调 Claude API）
│   ├── GET /signal → 技术信号 (RSI/MACD/MA/Volume)
│   ├── GET /backtest → 历史验证
│   └── 综合研判 → 趋势判断 + 策略匹配
├── 输出
│   ├── 推荐报告（Top N 股票 + 每只策略建议）
│   └── Telegram 推送
└── 交互
    ├── "分析 AAPL" → 单股深度分析
    ├── "推荐" → 触发全量扫描
    └── "加自选 TSLA" → 管理 watchlist

FastAPI (数据层，纯 API)
├── GET /signal — 技术信号（纯因子计算，不含舆情）
├── GET /backtest — 策略回测
├── GET /data — K线数据
├── GET /positions — 持仓
├── GET /watchlist — 自选列表 CRUD
└── POST /trade — 下单
```

## 职责划分

| 能力 | 谁做 | 原因 |
|------|------|------|
| 技术因子计算 | FastAPI | 确定性计算，代码做 |
| 新闻搜索 + 舆情判断 | OpenClaw | Agent 天然有联网+AI能力 |
| 趋势判断（上涨/下跌/横盘）| OpenClaw | 需要综合技术面+舆情，AI判断 |
| 策略匹配 | OpenClaw | 根据趋势推荐策略，AI决策 |
| 回测验证 | FastAPI | 确定性计算 |
| 报告生成 | OpenClaw | 自然语言输出 |

## Skills 设计

### stock_watchlist（新增）

管理自选股票列表。

触发词：`加自选 TSLA`、`删自选 AAPL`、`自选列表`

```
exec curl -s -H "Authorization: Bearer $LOCAL_API_KEY" \
  "http://127.0.0.1:8000/watchlist"                         # 查看
exec curl -s -X POST ... "http://127.0.0.1:8000/watchlist"  # 添加
exec curl -s -X DELETE ... "http://127.0.0.1:8000/watchlist/TSLA" # 删除
```

### stock_daily_scan（新增，核心）

每日扫描 watchlist，输出综合报告。

触发词：`每日扫描`、`推荐`、`今日分析`

执行流程：
1. `GET /watchlist` → 获取自选列表
2. 对每只股票：
   - `GET /signal?symbol={}&start={-30d}&end={today}` → 技术信号
   - `GET /backtest?symbol={}&strategy=rsi&start={-1y}&end={today}` → 历史表现
   - Agent 自己搜索 `{symbol} stock news today` → 新闻舆情
3. 综合判断趋势：
   - MA20 > MA60 且 MACD 金叉 → 上涨趋势
   - MA20 < MA60 且 MACD 死叉 → 下跌趋势
   - 其余 → 横盘震荡
4. 策略匹配：
   - 上涨 → "建议 MA Crossover / MACD 追动量，回调买入"
   - 下跌 → "建议观望或轻仓，严格止损"
   - 横盘 → "建议 RSI 均值回归，超卖买超买卖"
5. 输出排名报告

### stock_signal（已有，保留）

纯技术信号查询，不变。

### stock_backtest（已有，保留）

策略回测，不变。

### stock_positions（已有，保留）

持仓查询，不变。

### stock_sentiment（已有，废弃）

不再需要——舆情判断由 OpenClaw Agent 自己完成。

## API 变更

### 新增：watchlist CRUD

```
GET    /watchlist                → [{symbol, added_at, notes}]
POST   /watchlist                → 添加 {symbol, notes?}
DELETE /watchlist/{symbol}       → 删除
```

### 变更：SignalService

去掉 sentiment ×1.2 boost。`/signal` 返回纯技术面评分，AI 判断由 OpenClaw 在 Agent 层做。

## 实施顺序

1. watchlist API + DB 表（后端基础）
2. stock_watchlist Skill（OpenClaw 管理自选）
3. stock_daily_scan Skill（核心扫描逻辑）
4. SignalService 去掉 sentiment boost
5. 更新文档
