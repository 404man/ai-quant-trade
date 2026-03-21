# 交易接口设置 — 设计文档

**日期：** 2026-03-21
**状态：** 已批准
**范围：** 后端网关抽象层 + 配置 API + 前端设置页面

---

## 背景与目标

现有系统仅支持 Alpaca 一个交易接口，逻辑硬编码在 `POST /trade` 路由中。本功能新增统一的 Gateway 抽象层，支持多交易所接入（参考 vnpy 架构思路，但不依赖 vnpy），并提供前端设置页面管理各接口的连接配置。

**目标：**
- 实现 `BaseGateway` 抽象基类，定义统一接口
- 实现 4 个网关适配器：Alpaca（迁移现有逻辑）、Binance（真实实现）、Futu（stub）、IB（stub）
- 新增 `GatewayManager` 单例管理网关实例
- 新增 5 个 API 路由管理网关配置与连接
- 前端新增 `/settings` 页面，侧边栏布局
- 配置存储在 SQLite `gateway_configs` 表

---

## 架构概览

```
前端 /settings 页面
       │
       ▼
FastAPI 路由 (api/routes/gateways.py)
       │
       ▼
GatewayManager (api/services/gateway_manager.py)
       │
  ┌────┴─────────────────────────┐
  ▼          ▼          ▼        ▼
AlpacaGateway  BinanceGateway  FutuGateway  IBGateway
  (真实)         (真实)          (stub)       (stub)
       │
       ▼
  BaseGateway (api/gateways/base.py)
       │
       ▼
  SQLite gateway_configs 表
```

---

## 后端设计

### 1. 抽象基类 `BaseGateway`

**文件：** `api/gateways/base.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

GatewayStatus = Literal["connected", "disconnected", "error"]

@dataclass
class OrderResult:
    status: str           # "submitted" | "blocked" | "cancelled"
    order_id: str | None
    qty: float | None
    price_estimate: float | None
    reason: str | None

class BaseGateway(ABC):
    name: str             # 唯一标识，如 "alpaca"
    label: str            # 显示名称，如 "Alpaca"
    status: GatewayStatus = "disconnected"

    @abstractmethod
    def connect(self, config: dict) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def send_order(self, symbol: str, action: str, qty: float) -> OrderResult: ...

    def get_status(self) -> GatewayStatus:
        return self.status
```

### 2. 网关适配器

**目录：** `api/gateways/`

| 文件 | 接口 | 实现方式 | 依赖 |
|------|------|----------|------|
| `alpaca.py` | Alpaca | 真实（迁移现有逻辑） | 现有 alpaca-trade-api |
| `binance.py` | Binance | 真实（REST API） | ccxt |
| `futu.py` | 富途 | Stub（需本地 FutuOpenD） | 无（标注说明） |
| `ib.py` | Interactive Brokers | Stub（需本地 TWS/IB Gateway） | 无（标注说明） |

**Stub 实现说明：** Futu 和 IB 的 `connect()` 抛出明确错误消息：
- Futu: `"需先在本地运行 FutuOpenD 程序（默认端口 11111）"`
- IB: `"需先在本地运行 TWS 或 IB Gateway 程序（默认端口 7497）"`

**各网关配置字段：**

| 网关 | 配置字段 |
|------|----------|
| Alpaca | `api_key`, `secret_key`, `mode`（"paper" \| "live"） |
| Binance | `api_key`, `api_secret` |
| Futu | `host`（默认 127.0.0.1）, `port`（默认 11111） |
| IB | `host`（默认 127.0.0.1）, `port`（默认 7497） |

### 3. GatewayManager

**文件：** `api/services/gateway_manager.py`

- 单例，app 启动时从 DB 加载所有已启用网关的配置并初始化实例
- 方法：
  - `get_all() -> list[dict]` — 返回所有网关信息（脱敏）
  - `save_config(name, config: dict) -> None` — 写入 DB
  - `connect(name) -> None` — 调用对应网关的 `connect()`，更新 status
  - `disconnect(name) -> None`
  - `get_status(name) -> GatewayStatus`
  - `route_order(name, symbol, action, qty) -> OrderResult`
- 脱敏规则：返回配置时，`secret_key`、`api_secret` 等字段替换为 `"***"`

### 4. 数据库

**新增表** `gateway_configs`（在 `db/schema.py` 的 `init_db()` 中创建）：

```sql
CREATE TABLE IF NOT EXISTS gateway_configs (
    name       TEXT PRIMARY KEY,
    config_json TEXT NOT NULL DEFAULT '{}',
    enabled    INTEGER NOT NULL DEFAULT 0,
    status     TEXT NOT NULL DEFAULT 'disconnected'
)
```

- `config_json`：JSON 字符串，存储 API key 等配置（明文，仅限本地开发）
- 初始数据：预插入 4 条记录（alpaca/binance/futu/ib），enabled=0，config_json='{}'

> ⚠️ **安全说明：** 配置明文存储仅适合本地开发环境。生产环境需加密存储。

### 5. API 路由

**文件：** `api/routes/gateways.py`
**注册：** `api/main.py`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/gateways` | 返回所有网关列表（含状态，secret 脱敏） |
| PUT | `/gateways/{name}` | 保存网关配置（body: config dict） |
| POST | `/gateways/{name}/connect` | 触发连接，返回新状态 |
| POST | `/gateways/{name}/disconnect` | 断开连接，返回新状态 |
| GET | `/gateways/{name}/status` | 返回当前状态 |

**GET /gateways 响应示例：**
```json
[
  {
    "name": "alpaca",
    "label": "Alpaca",
    "enabled": true,
    "status": "connected",
    "config": { "api_key": "PK***", "mode": "paper", "secret_key": "***" }
  },
  {
    "name": "binance",
    "label": "Binance",
    "enabled": false,
    "status": "disconnected",
    "config": {}
  }
]
```

**修改 `POST /trade`：**
新增可选 body 参数 `gateway: str = "alpaca"`，通过 `GatewayManager.route_order()` 路由。默认值 `"alpaca"` 保持向后兼容，现有调用无需修改。

---

## 前端设计

### 页面路由

新增 `/settings` 页面，侧边导航加入「设置」入口（`Settings` 图标）。

### 文件结构

```
web/
├── app/settings/page.tsx
├── components/settings/
│   ├── GatewayList.tsx      ← 左侧接口列表（含状态圆点）
│   └── GatewayDetail.tsx    ← 右侧配置面板（含表单 + 连接/断开按钮）
├── lib/
│   ├── api.ts               ← 新增 5 个 gateway API 函数
│   └── types.ts             ← 新增 GatewayConfig interface
```

### 布局

侧边栏 + 详情面板（双栏布局）：
- 左栏（约 160px）：网关列表，每项显示状态圆点 + 名称
- 右栏：选中网关的配置表单 + 操作按钮

### 交互流程

1. 页面加载 → `GET /gateways` → 渲染左侧列表
2. 点击左侧某接口 → 右侧显示对应配置表单
3. 填写字段 → 点「保存」→ `PUT /gateways/{name}`
4. 点「连接」→ `POST /gateways/{name}/connect` → 刷新状态
5. 点「断开」→ `POST /gateways/{name}/disconnect`

### GatewayConfig TypeScript Interface

```typescript
export interface GatewayConfig {
  name: string;
  label: string;
  enabled: boolean;
  status: "connected" | "disconnected" | "error";
  config: Record<string, string>;
}
```

### 各网关表单字段

| 网关 | 字段 | 说明 |
|------|------|------|
| Alpaca | API Key、Secret Key、模式（paper/live 下拉） | |
| Binance | API Key、API Secret | |
| Futu | Host、Port | 显示提示：需运行 FutuOpenD |
| IB | Host、Port | 显示提示：需运行 TWS/IB Gateway |

Secret 字段：写入时发送明文，读取时后端返回 `"***"`，前端显示占位符提示用户「已保存，输入新值可更新」。

---

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| 连接失败（API key 错误、网络不通） | 右侧面板显示红色错误信息，状态圆点变红（error） |
| Futu/IB 未运行本地程序 | 连接时返回明确错误消息，界面显示安装提示 |
| 保存配置失败 | shadcn toast 通知 |
| `/trade` 传入无效 gateway 名称 | 返回 400，前端 toast 显示 |
| 网关名称不存在 | PUT/connect/disconnect 返回 404 |

---

## 测试计划

### 后端（pytest）

**`tests/test_gateways_route.py`：**
- `GET /gateways` 返回 200 及正确结构
- `PUT /gateways/{name}` 保存配置、secret 脱敏验证
- `POST /gateways/{name}/connect` 成功与失败场景
- `POST /gateways/{name}/disconnect`
- `GET /gateways/{name}/status`
- 无效 gateway 名称返回 404

**`tests/test_gateway_manager.py`：**
- GatewayManager 初始化、路由逻辑
- `route_order` 路由到正确适配器

**`tests/test_alpaca_gateway.py`：**
- `connect()` / `send_order()` 单测（mock HTTP）

### 前端
- `next build` 通过（TypeScript 无错误）

---

## 文件变更清单

**新建：**
- `api/gateways/__init__.py`
- `api/gateways/base.py`
- `api/gateways/alpaca.py`
- `api/gateways/binance.py`
- `api/gateways/futu.py`
- `api/gateways/ib.py`
- `api/services/gateway_manager.py`
- `api/routes/gateways.py`
- `web/app/settings/page.tsx`
- `web/components/settings/GatewayList.tsx`
- `web/components/settings/GatewayDetail.tsx`
- `tests/test_gateways_route.py`
- `tests/test_gateway_manager.py`
- `tests/test_alpaca_gateway.py`

**修改：**
- `db/schema.py` — 新增 `gateway_configs` 表
- `api/main.py` — 注册 gateways router
- `api/routes/trade.py` — 新增可选 `gateway` 参数
- `web/lib/api.ts` — 新增 gateway API 函数
- `web/lib/types.ts` — 新增 `GatewayConfig` interface
- `web/components/layout/Sidebar.tsx` — 新增「设置」导航项
