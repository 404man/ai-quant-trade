# OpenClaw 集成设计规范

**日期：** 2026-03-22
**目标：** 将 AI 量化交易系统与 OpenClaw 双向集成——Skills 查询 + Webhook 推送
**前置条件：** Phase 1-4 已完成，Gateway 抽象层已实现

---

## 概述

OpenClaw 是一个自托管 AI 助手框架，通过 Skills（SKILL.md 文件）教 agent 使用工具，通过 Webhooks 接收外部事件推送。本设计实现两个方向的集成：

1. **查询方向（Skills）**：用户通过 OpenClaw 对话查询系统状态（回测、情绪、信号、持仓）
2. **推送方向（Webhooks）**：系统主动向 OpenClaw 推送事件（交易信号、风控警报、订单状态、每日摘要）

**集成方式**：Skills 通过 `exec` 工具执行 `curl` 调用 FastAPI；Webhook 通过 `httpx` POST 到 OpenClaw 的 `/hooks/agent` 端点。

---

## 认证层

### Bearer Token 认证 (api/auth.py)

FastAPI 依赖（`Depends()`），所有路由统一加认证：

- 读取 `LOCAL_API_KEY` 环境变量
- 验证请求 header `Authorization: Bearer <token>`
- `GET /health` 不需要认证
- Token 不匹配返回 `401 Unauthorized`
- 未设置 `LOCAL_API_KEY` 环境变量时跳过认证（开发模式）

```python
from fastapi import Depends, HTTPException, Request

def verify_api_key(request: Request):
    api_key = os.environ.get("LOCAL_API_KEY")
    if not api_key:
        return  # dev mode: no auth
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {api_key}":
        raise HTTPException(status_code=401, detail="Invalid API key")
```

认证依赖通过 `app = FastAPI(dependencies=[Depends(verify_api_key)])` 全局注入，`/health` 端点单独排除。

---

## Skills（查询方向：OpenClaw → FastAPI）

### 文件结构

```
openclaw/skills/
├── stock_backtest/SKILL.md
├── stock_sentiment/SKILL.md
├── stock_signal/SKILL.md
└── stock_positions/SKILL.md
```

每个 SKILL.md 包含 YAML frontmatter + markdown 指令，教 agent 如何解析用户意图、构造 curl 命令、解读 JSON 响应。

### Skill 定义

#### stock_backtest

- **触发词**：回测、backtest
- **API**：`GET /backtest?symbol=AAPL&strategy=rsi&start=2020-01-01&end=2024-12-31`
- **参数**：symbol（必填）、strategy（rsi 或 ma_crossover，默认 rsi）、start/end（默认 2020-01-01 到 2024-12-31）
- **响应解读**：用自然语言呈现 Sharpe Ratio、最大回撤、年化收益、交易次数

#### stock_sentiment

- **触发词**：情绪、sentiment
- **API**：`GET /sentiment?symbol=TSLA`
- **参数**：symbol（必填）
- **响应解读**：翻译 sentiment（bullish/bearish/neutral）为中文，附带 confidence 百分比

#### stock_signal

- **触发词**：信号、signal
- **API**：`GET /signal?symbol=AAPL&start=<30天前>&end=<今天>&capital=500`
- **参数**：symbol（必填）、capital（默认 500）
- **响应解读**：翻译 action（buy/sell/hold），如被风控拦截说明原因

#### stock_positions

- **触发词**：持仓、positions、账户状态
- **API**：`GET /positions`（新端点）
- **参数**：无
- **响应解读**：列出持仓表格（symbol、数量、方向、入场价），附带账户余额

### Skill SKILL.md 格式

```markdown
---
name: stock_backtest
description: Query stock backtesting results from the AI quant trading system
metadata: {"openclaw":{"requires":{"env":["LOCAL_API_KEY"]}}}
---

# Stock Backtest

When the user asks to backtest a stock (e.g. "回测 AAPL", "backtest TSLA rsi"):

1. Extract: symbol (required), strategy (rsi or ma_crossover, default rsi)
2. Run:
   ```
   exec curl -s -H "Authorization: Bearer $LOCAL_API_KEY" \
     "http://127.0.0.1:8000/backtest?symbol=AAPL&strategy=rsi&start=2020-01-01&end=2024-12-31"
   ```
3. Parse JSON response and present results in natural language
```

### 新增端点：GET /positions

**文件**：`api/routes/positions.py`

```python
@router.get("/positions")
def get_positions():
    trade_svc = TradeService()
    positions = trade_svc.get_positions()  # 现有方法
    return {
        "positions": positions,
        "count": len(positions),
    }
```

返回示例：
```json
{
  "positions": [
    {"symbol": "AAPL", "qty": 5, "side": "buy", "entry_price": 178.50}
  ],
  "count": 1
}
```

---

## Webhook 推送（FastAPI → OpenClaw）

### 配置

`.env` 新增：
```
OPENCLAW_HOOK_URL=http://127.0.0.1:18789/hooks/agent
OPENCLAW_HOOK_TOKEN=your_hook_token_here
```

### WebhookService (api/services/webhook_service.py)

统一推送入口，职责：
- 构造消息文本
- POST 到 OpenClaw `/hooks/agent`
- 失败静默（仅日志记录，不影响主流程）

```python
import httpx
import logging
import os

logger = logging.getLogger(__name__)

class WebhookService:
    def __init__(self):
        self.url = os.environ.get("OPENCLAW_HOOK_URL", "")
        self.token = os.environ.get("OPENCLAW_HOOK_TOKEN", "")

    def push(self, event_type: str, data: dict) -> None:
        if not self.url or not self.token:
            return  # webhook not configured
        message = self._format_message(event_type, data)
        try:
            httpx.post(
                self.url,
                json={"message": message, "name": f"stock-{event_type}"},
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=5.0,
            )
        except Exception as e:
            logger.warning(f"Webhook push failed: {e}")

    def _format_message(self, event_type: str, data: dict) -> str:
        formatters = {
            "signal": self._fmt_signal,
            "risk_alert": self._fmt_risk_alert,
            "order_status": self._fmt_order_status,
            "daily_summary": self._fmt_daily_summary,
        }
        fmt = formatters.get(event_type)
        return fmt(data) if fmt else str(data)
```

### 4 种推送事件

#### 1. 交易信号推送

- **触发时机**：`GET /signal` 返回 action 为 buy 或 sell 时
- **触发点**：`api/routes/signal.py`，在返回响应前调用
- **推送内容**：`{symbol, action, size, score}`
- **消息格式**：`"交易信号：AAPL 买入，仓位 5%，评分 0.78"`

#### 2. 风控警报

- **触发时机**：`POST /trade` 被风控拦截时
- **触发点**：`api/routes/trade.py`，风控检查返回 blocked
- **推送内容**：`{symbol, reason, capital, daily_loss}`
- **消息格式**：`"风控警报：AAPL 交易被拦截 — 单日亏损已达限额"`

#### 3. 订单状态变更

- **触发时机**：`POST /trade` 订单最终结果确定（submitted/cancelled/timeout）
- **触发点**：`api/routes/trade.py`，在返回响应前调用
- **推送内容**：`{order_id, symbol, action, status, qty, price_estimate}`
- **消息格式**：`"订单成交：AAPL 买入 5 股 @ $178.50" 或 "订单取消：AAPL — 用户拒绝"`

#### 4. 每日摘要

- **触发时机**：通过 `POST /daily-summary` 端点手动触发（由外部 cron 或 OpenClaw 定时调用）
- **推送内容**：`{positions, daily_pnl, account_balance, date}`
- **消息格式**：多行文本，含持仓列表 + 当日盈亏 + 账户余额

### 新增端点：POST /daily-summary

**文件**：`api/routes/daily_summary.py`

```python
@router.post("/daily-summary")
def post_daily_summary():
    trade_svc = TradeService()
    positions = trade_svc.get_positions()
    daily_loss = trade_svc.get_daily_loss(date.today().isoformat())
    webhook = WebhookService()
    webhook.push("daily_summary", {
        "positions": positions,
        "daily_pnl": -daily_loss,
        "date": date.today().isoformat(),
    })
    return {"status": "sent"}
```

---

## Telegram 分工

| 职责 | 处理方 | 说明 |
|------|--------|------|
| 交易确认 (YES/NO) | 现有 python-telegram-bot (`tg/handlers.py`) | 关键路径，不依赖 OpenClaw |
| 自然语言查询 | OpenClaw Telegram channel | 用户对话触发 Skills |
| 事件推送 | OpenClaw webhook → Telegram | FastAPI 推 OpenClaw，OpenClaw 转发 Telegram |

交易确认保持现有实现不变。OpenClaw 和现有 Telegram bot 使用不同的 bot token，互不干扰。

未来可选：OpenClaw 运行稳定 3 个月后，可考虑将交易确认也迁移到 OpenClaw（不在本次范围）。

---

## 文件变更清单

### 新增文件

| 文件 | 职责 |
|------|------|
| `api/auth.py` | Bearer Token 认证依赖 |
| `api/routes/positions.py` | GET /positions 持仓查询端点 |
| `api/routes/daily_summary.py` | POST /daily-summary 每日摘要触发端点 |
| `api/services/webhook_service.py` | OpenClaw webhook 推送服务 |
| `openclaw/skills/stock_backtest/SKILL.md` | 回测查询 Skill |
| `openclaw/skills/stock_sentiment/SKILL.md` | 情绪查询 Skill |
| `openclaw/skills/stock_signal/SKILL.md` | 信号查询 Skill |
| `openclaw/skills/stock_positions/SKILL.md` | 持仓查询 Skill |
| `tests/test_auth.py` | 认证测试 |
| `tests/test_positions_route.py` | 持仓端点测试 |
| `tests/test_webhook_service.py` | Webhook 推送测试 |
| `tests/test_daily_summary_route.py` | 每日摘要端点测试 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `api/main.py` | 全局认证依赖 + 注册 positions/daily_summary 路由 |
| `api/routes/signal.py` | buy/sell 时触发信号推送 |
| `api/routes/trade.py` | 风控警报 + 订单状态推送 |
| `.env.example` | 新增 OPENCLAW_HOOK_URL、OPENCLAW_HOOK_TOKEN |
| `requirements.txt` | 新增 httpx |

---

## 测试计划

### test_auth.py
- 正确 token → 200
- 错误 token → 401
- 缺少 header → 401
- LOCAL_API_KEY 未设置 → 跳过认证（200）
- /health 无需认证 → 200

### test_positions_route.py
- 有持仓 → 返回列表 + count
- 无持仓 → 返回空列表 + count=0

### test_webhook_service.py
- push 成功 → httpx.post 被调用，参数正确
- push 失败 → 不抛异常，仅日志
- URL/token 未配置 → 静默返回
- 4 种事件类型消息格式正确

### test_daily_summary_route.py
- 触发推送 → webhook.push 被调用
- 返回 {"status": "sent"}

### 现有测试兼容
- 现有测试不设置 LOCAL_API_KEY，认证跳过，全部兼容
- signal/trade 路由测试 mock webhook_service，不受推送影响

---

## 依赖

- **httpx**：用于 webhook HTTP POST（比 requests 更现代，支持 async）
- 无其他新依赖

---

## 不在范围内

- 交易确认迁移到 OpenClaw
- OpenClaw Plugin 开发（当前用 Skills + curl）
- API Key 轮换/过期机制
- Webhook 重试/队列（当前失败静默）
- 前端 /settings 页面的 OpenClaw 配置 UI
