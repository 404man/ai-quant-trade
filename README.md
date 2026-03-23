# AI 量化交易系统

FastAPI 后端 + Next.js 前端的 AI 量化交易平台。

## 快速启动

```bash
# 后端
python -m uvicorn api.main:app --reload

# 前端
cd web && npm run dev
```

访问 `http://localhost:3000`

## 文档

- [日常运维手册](docs/ops.md)
- [系统设计](docs/superpowers/specs/)
- [实现计划](docs/superpowers/plans/)

## 技术栈

- **后端**: Python 3.10 / FastAPI / SQLite / yfinance / vectorbt / TA-Lib
- **前端**: Next.js 14 / TypeScript / shadcn/ui / Recharts
- **策略**: RSI、MA Crossover、MACD（含 volume gate + conviction bonus）
- **网关**: Alpaca（纸交易）、Binance、Futu（stub）、IB（stub）

 Telegram 消息架构

/trade 接口
  → send_confirmation() → Telegram Bot API 发消息给你
  → poll_confirmation() → 等你回复 YES/NO
  → tg/bot.py 独立进程 → 收到回复写 DB
  → poll 读 DB → confirmed/cancelled
  → 确认后 → gateway 下单
这是一条独立的直连链路，跟 OpenClaw 无关。

两条路走法：

|                        | 保持现状（直连）       | 改走 OpenClaw                |
|------------------------|---------------------|------------------------------|
| Telegram 发消息    | tg/handlers.py 调 Bot API     | OpenClaw Agent 自己发     |
| 接收回复           | tg/bot.py 独立进程轮询          | OpenClaw 内置对话能力      |
| 优点              | 已实现，稳定                   | 统一入口，Agent 可以多轮对话    |
| 缺点              | 需要单独跑 python -m tg.bot    | 依赖 OpenClaw 的 Telegram 集成   |
建议：保持直连。 原因：

交易确认是关键路径，越简单越可靠
OpenClaw 的 Telegram 集成是额外复杂度
当前实现已经能用，改动没有收益
OpenClaw 负责"分析决策"，本系统负责"执行下单+确认"，职责分明。
