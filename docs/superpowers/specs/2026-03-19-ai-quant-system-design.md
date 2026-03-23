# AI 量化交易系统设计规范

**日期：** 2026-03-19
**目标：** 3 个月内跑通纸面交易验证，小资金实盘为后续目标
**经验级别：** 无量化交易经验，依赖 AI 构建系统

---

## 背景与约束

- 市场：美股（Polygon.io 数据源），后续扩展 A 股
- 时间目标：3 个月内完成纸面交易（Alpaca Paper Trading）；实盘为后续阶段
- Agent 框架：OpenClaw（个人 AI 助手框架，Node.js，通过 Skills 机制调用 FastAPI）
- OpenClaw 定位：**交互层胶水**，不是量化引擎；量化核心逻辑全部在 Python/FastAPI
- 回测框架：**vectorbt**（比 Backtrader 更轻量，向量化计算更快，适合快速迭代）

---

## 整体架构

```
┌─────────────────────────────────────┐
│         OpenClaw 交互层              │
│  (Telegram Bot → Skills)            │
│  查询状态 / 触发分析 / 接收警报      │
└──────────────────┬──────────────────┘
                   │ HTTP + API Key
┌──────────────────▼──────────────────┐
│         FastAPI 核心服务             │
│  /backtest  /signal  /portfolio     │
│  /sentiment /risk   /trade          │
└──────┬──────────────┬───────────────┘
       │              │
┌──────▼──────┐  ┌────▼────────────────┐
│  数据层      │  │  策略 / 风控层       │
│ Polygon API │  │ vectorbt + pandas   │
│ + SQLite 缓存│  │ + Claude 情绪分析   │
└─────────────┘  └─────────────────────┘
                         │
              ┌──────────▼──────────┐
              │    Alpaca API        │
              │ Paper → 实盘        │
              └─────────────────────┘
```

**关键设计决策：**
- FastAPI 是系统中枢，所有模块通过它通信，便于测试和调试
- OpenClaw 通过 HTTP 调用 FastAPI，携带本地 API Key 认证，不直接接触数据库或策略代码
- Claude API 只做情绪分析，结果缓存 1 小时避免重复调用，失败返回 neutral
- 数据缓存使用 SQLite（结构化查询 + 无需额外服务）

---

## 初始策略定义

Phase 1 实现两个具体策略（entry/exit 规则明确）：

**策略 1：RSI 均值回归**
- 入场：RSI(14) < 30（超卖）
- 出场：RSI(14) > 70（超买）或持仓超 10 个交易日

**策略 2：MA 双线交叉**
- 入场：MA(10) 上穿 MA(30)（金叉）
- 出场：MA(10) 下穿 MA(30)（死叉）

两个策略均在 Phase 4 聚合时按等权重投票决策。

---

## 实施计划（调整后）

### Phase 1（第 1-2 周）：数据 + 回测基础

**前置验证（第 1 天必做）：**
- 验证 Polygon 免费套餐是否包含 2020-2024 日线历史数据
- 如不满足，切换 yfinance 作为数据源（免费，历史数据充足）

**交付物：**
- SQLite 数据缓存：`data/cache.db`（symbol + date + OHLCV）
- `GET /backtest?symbol=AAPL&strategy=rsi` 返回回测结果 JSON
- 回测指标：Sharpe Ratio、最大回撤、年化收益、交易次数
- 回测数据集：2020-2023 训练，2024 验证（out-of-sample）
- 防止过拟合：回测含手续费（$1/笔）和滑点（0.1%）

### Phase 2（第 3-4 周）：AI 情绪分析

**交付物：**
- `GET /sentiment?symbol=AAPL` 返回 `{"sentiment": "bullish", "confidence": 0.72}`
- 情绪信号可选接入回测（作为过滤条件，不作为主信号）
- SQLite 情绪缓存，1 小时过期
- 每日 Claude API 调用上限：50 次，超限返回 `{"sentiment": "neutral", "confidence": 0.5}`

### Phase 3（第 5-6 周）：信号聚合 + 风控

**交付物：**
- Master 逻辑：RSI 信号 × MA 信号 × 情绪过滤 → 综合评分
- `GET /signal?symbol=AAPL` 返回 `{"action": "buy", "size": 0.05, "score": 0.78}`
- 风控规则完整实现（见风控章节）
- **Go/No-Go 门：** out-of-sample Sharpe ≥ 1.0 才进入 Phase 4

### Phase 4（第 7-9 周）：Alpaca 纸面交易

**交付物：**
- 接入 Alpaca Paper Trading API
- 完整订单执行流程（见订单生命周期章节）
- Telegram Bot 可接收警报、发送确认
- 每日定时推送：持仓状态 + 当日盈亏
- 纸面交易至少运行 **4 周**，无重大 bug 才进 Phase 5

### Phase 5（第 10-12 周）：OpenClaw 接入 + 实盘准备

**交付物：**
- OpenClaw Skills 封装所有 FastAPI 端点
- Telegram Bot 查询：`回测 AAPL`、`情绪 TSLA`、`持仓状态`
- 实盘启动条件：纸面交易 4 周 Sharpe ≥ 1.0 + 人工审查
- 实盘初始资金：≤ $500

---

## 订单执行生命周期

```
信号生成
    ↓
风控检查（硬限制验证）
    ↓ 通过
Telegram 推送订单详情（symbol, action, size, price_estimate, risk_amount）
    ↓ 等待回复
用户回复 YES（5 分钟内）
    ↓ 超时 → 自动取消
Alpaca 下单（市价单，简单可靠）
    ↓
轮询订单状态（最多 30 秒）
    ↓
成交确认 → 更新本地持仓状态 → Telegram 推送成交通知
    ↓ 未成交 / 超时
撤单 → Telegram 推送"订单已取消"通知（含原因）
```

**系统重启恢复：**
- FastAPI 启动时从 Alpaca API 拉取当前持仓，覆盖本地状态
- 每日亏损计数从 SQLite 持久化读取（不依赖内存）

---

## 风控与安全边界

### 硬限制（代码层面强制，不可绕过）

```
单笔交易     ≤ 总资金 2%（$500 时约 $10，低于此金额不交易）
单标的仓位   ≤ 总资金 10%
单日亏损     ≥ 总资金 2% → 自动停止当日所有交易
同时持仓     ≤ 5 个标的
最低可交易资金 = $200（低于此值暂停系统）
```

每日亏损限制重置：每个交易日 09:30 ET 自动重置，持久化到 SQLite。

### 人工确认门（Phase 4 起必须，长期保留）

- 每笔买入/卖出通过 Telegram 推送详情
- 回复 `YES` 才真正下单，超时 5 分钟自动取消
- 此机制在系统跑稳（≥ 3 个月实盘）之前永远不关闭

### 权限隔离

- OpenClaw Skills 只能调用 FastAPI（携带本地 API Key）
- Alpaca API Key 只存在 FastAPI 服务的 `.env` 文件，OpenClaw 层不持有
- `.env` 加入 `.gitignore`，提供 `.env.example` 模板
- 本地运行，不部署到公网（减少攻击面）

### 回测过拟合保护

- 训练集：2020-2023，验证集：2024（out-of-sample）
- 回测含手续费和滑点
- 上线门槛：out-of-sample Sharpe ≥ 1.0
- 股票池固定为 S&P 500 成分股，避免幸存者偏差（使用固定列表）

---

## 项目目录结构

```
stock/
├── api/
│   ├── main.py                  # FastAPI 入口，路由注册
│   ├── auth.py                  # 本地 API Key 验证
│   ├── routes/
│   │   ├── backtest.py
│   │   ├── data.py
│   │   ├── sentiment.py
│   │   ├── signal.py
│   │   ├── risk.py
│   │   └── trade.py
│   └── services/
│       ├── data_service.py      # Polygon/yfinance + SQLite 缓存
│       ├── backtest_service.py  # vectorbt 封装
│       ├── sentiment_service.py # Claude API + SQLite 缓存
│       ├── risk_service.py      # 风控规则（含每日亏损跟踪）
│       └── trade_service.py     # Alpaca API + 订单状态管理
├── strategies/
│   ├── rsi_strategy.py          # RSI 均值回归
│   └── ma_crossover_strategy.py # MA 双线交叉
├── telegram/
│   ├── bot.py                   # Telegram Bot（python-telegram-bot）
│   └── handlers.py              # YES/NO 确认处理
├── openclaw/
│   ├── backtest_skill.js
│   ├── sentiment_skill.js
│   └── signal_skill.js
├── data/
│   └── cache.db                 # SQLite 缓存（不入 git）
├── logs/
│   └── trades.db                # 交易日志 SQLite（不入 git）
├── tests/
│   ├── test_backtest.py
│   ├── test_sentiment.py
│   ├── test_risk.py
│   └── test_trade_lifecycle.py
├── .env                         # 不入 git
├── .env.example
├── .gitignore
└── requirements.txt
```

---

## 技术栈

| 层级 | 技术 |
|------|------|
| API 服务 | Python 3.11 + FastAPI |
| 回测 | vectorbt |
| 指标计算 | pandas-ta |
| 数据缓存 | SQLite（via sqlite3 标准库）|
| AI 情绪分析 | Claude API（anthropic SDK）|
| 实盘交易 | alpaca-py（Alpaca 官方 Python SDK，paper + live）|
| 市场数据 | Polygon.io REST API（备用：yfinance）|
| Telegram | python-telegram-bot |
| 交互层 | OpenClaw（Node.js，独立进程，Phase 5）|

---

## 待解决问题

- [ ] Day 1：验证 Polygon 免费套餐历史数据范围，必要时切换 yfinance
- [ ] Phase 3 开始前：确认本地 API Key 认证方案（简单 Bearer Token 即可），在 `api/auth.py` 中实现
- [ ] Phase 4 开始前：明确 Telegram 确认超时处理细节（沉默丢弃 vs 推送取消通知）

##  控制台界面 Next.js 实现
包括以下菜单： 实盘、策略库、交易终端（交易API选择）、数据探索、消息中心
