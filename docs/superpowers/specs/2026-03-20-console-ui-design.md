# 控制台界面设计规范

**日期：** 2026-03-20
**目标：** 为 AI 量化交易系统构建本地 Next.js 控制台界面，供个人本地使用
**后端：** 已有 FastAPI（`http://localhost:8000`），本文档描述前端层设计

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 框架 | Next.js 14 App Router + TypeScript |
| 样式 | Tailwind CSS |
| UI 组件 | shadcn/ui（基于 Radix，简洁浅色风格） |
| K线图 | TradingView lightweight-charts |
| 其他图表 | Recharts（回测收益曲线） |
| API 调用 | 浏览器直接 fetch `localhost:8000`，无中间层 |

---

## 整体布局

- **左侧固定导航栏**（220px）：logo、5个菜单项、底部 FastAPI 在线状态指示器
- **右侧内容区**：各页面内容
- 根路由 `/` 重定向到 `/live`

---

## 路由与页面功能

### 1. 实盘 `/live`

**功能：**
- 顶部账户概览卡片：总资金、当日盈亏、持仓数量
- 持仓列表表格：symbol、数量、成本价、当前价、盈亏%
- 信号面板：输入 symbol + 日期范围 → 调用 `GET /signal` → 显示 RSI信号/MA信号/情绪/综合评分/建议动作
- "执行交易"按钮：调用 `POST /trade`，展示提交结果

**使用端点：** `GET /signal`、`POST /trade`

---

### 2. 策略库 `/strategies`

**功能：**
- 回测表单：选策略（RSI / MA）、symbol、日期范围（默认 2020-01-01 ~ 2024-12-31）、仓位大小（0.01~1.0）
- 结果卡片：Sharpe Ratio、最大回撤、年化收益、交易次数、平均持仓天数
- Recharts 折线图：回测期间累计收益曲线（基于 total_return 计算）

**使用端点：** `GET /backtest`

---

### 3. 交易终端 `/terminal`

**功能：**
- 经纪商切换：Alpaca Paper / Alpaca Live（badge 显示当前模式，切换时更新本地状态）
- 下单表单：symbol、买/卖、股数、预估金额
- 提交后展示订单结果：submitted（含 order_id）/ blocked（含原因）/ cancelled（含原因）

**使用端点：** `POST /trade`

---

### 4. 数据探索 `/explore`

**功能：**
- 查询表单：symbol、start、end
- 上方：TradingView lightweight-charts K线图（OHLCV，CandlestickSeries）
- 下方：回测结果表格（Sharpe、最大回撤、年化收益、交易次数）

**使用端点：** `GET /data/price`、`GET /backtest`

---

### 5. 消息中心 `/messages`

**功能：**
- 两个 Tab：「交易通知」/「系统日志」
- 交易通知：调用 `GET /confirmations`（新增后端端点），显示最近 50 条，按 created_at 倒序，含状态标签（pending/confirmed/cancelled）
- 系统日志：前端内存记录每次 API 调用（时间戳、端点、状态码、耗时），仅本次会话保留

**使用端点：** `GET /confirmations`（新增）

---

## 新增后端端点

### `GET /confirmations`

**位置：** `api/routes/confirmations.py`（新建），在 `api/main.py` 注册

**响应：**
```json
[
  {
    "order_id": "uuid",
    "symbol": "AAPL",
    "action": "buy",
    "qty": 1.0,
    "created_at": "2026-03-20T09:00:00",
    "status": "confirmed"
  }
]
```

读取 `pending_confirmations` 表，按 `created_at` DESC，最多返回 50 条。

---

## 数据层

### `web/lib/api.ts`

统一封装所有 fetch 调用：
- `BASE_URL` 从 `NEXT_PUBLIC_API_URL` 环境变量读取（默认 `http://localhost:8000`）
- 每个函数对应一个后端端点，返回类型化结果
- fetch 失败时抛出 Error，由调用方处理（toast 通知）

### `web/lib/types.ts`

所有后端响应的 TypeScript interface，包括：
- `SignalResponse`、`BacktestResponse`、`TradeResponse`
- `PriceBar`（OHLCV）、`ConfirmationRecord`

---

## 错误处理

- 所有 API 调用失败：shadcn `<Toaster>` toast 通知，不让页面崩溃
- FastAPI 离线：导航栏底部 `ApiStatus` 组件显示红色"离线"，轮询 `GET /health` 检测（每 30 秒）
- 空数据：各组件显示空状态提示，不显示错误

---

## 文件结构

```
stock/
└── web/
    ├── app/
    │   ├── layout.tsx
    │   ├── page.tsx                   ← redirect to /live
    │   ├── live/page.tsx
    │   ├── strategies/page.tsx
    │   ├── terminal/page.tsx
    │   ├── explore/page.tsx
    │   └── messages/page.tsx
    ├── components/
    │   ├── layout/
    │   │   ├── Sidebar.tsx
    │   │   └── ApiStatus.tsx
    │   ├── live/
    │   │   ├── AccountSummary.tsx
    │   │   ├── PositionsTable.tsx
    │   │   └── SignalPanel.tsx
    │   ├── strategies/
    │   │   ├── BacktestForm.tsx
    │   │   ├── BacktestResults.tsx
    │   │   └── EquityCurve.tsx
    │   ├── terminal/
    │   │   ├── BrokerSelector.tsx
    │   │   └── OrderForm.tsx
    │   ├── explore/
    │   │   ├── ExploreForm.tsx
    │   │   └── PriceChart.tsx
    │   └── messages/
    │       ├── ConfirmationsTab.tsx
    │       └── SystemLogTab.tsx
    ├── lib/
    │   ├── api.ts
    │   └── types.ts
    ├── .env.local
    ├── next.config.ts
    ├── tailwind.config.ts
    └── package.json
```

**组件原则：** 每个 page 负责数据获取和状态，子组件只做渲染。单文件不超过 150 行。

---

## 约束

- 本地使用，无需认证
- 不部署到公网
- 不修改现有后端代码，仅新增 `GET /confirmations` 端点
- `web/` 目录独立，`package.json` 只在 `web/` 内，不影响 Python 项目
