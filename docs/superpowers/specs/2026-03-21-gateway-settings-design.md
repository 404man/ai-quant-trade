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
  │  读写配置
  ├──────────────────────────► SQLite gateway_configs 表
  │
  ├── AlpacaGateway(BaseGateway)   ← 真实实现
  ├── BinanceGateway(BaseGateway)  ← 真实实现
  ├── FutuGateway(BaseGateway)     ← stub
  └── IBGateway(BaseGateway)       ← stub
```

每个适配器继承 `BaseGateway`。`GatewayManager` 负责持有适配器实例并读写 SQLite 配置。

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
| `futu.py` | 富途 | Stub | 无 |
| `ib.py` | Interactive Brokers | Stub | 无 |

**Stub 实现：** Futu 和 IB 的所有方法（`connect`、`disconnect`、`send_order`）均抛出 `RuntimeError`：
- Futu: `"需先在本地运行 FutuOpenD 程序（默认端口 11111）"`
- IB: `"需先在本地运行 TWS 或 IB Gateway 程序（默认端口 7497）"`

**各网关配置字段：**

| 网关 | 配置字段 |
|------|----------|
| Alpaca | `api_key`, `secret_key`, `mode`（"paper" \| "live"） |
| Binance | `api_key`, `api_secret` |
| Futu | `host`（默认 127.0.0.1）, `port`（默认 11111） |
| IB | `host`（默认 127.0.0.1）, `port`（默认 7497） |

**敏感字段：** `secret_key`（Alpaca）和 `api_secret`（Binance）在 `GET /gateways` 响应中替换为 `"***"`。`api_key` 明文返回。

### 3. GatewayManager

**文件：** `api/services/gateway_manager.py`

**单例实例化：**
- 模块级别创建：`_manager = GatewayManager()`（无参数构造）
- `api/main.py` 的 FastAPI `lifespan` 启动阶段，按以下顺序执行：
  1. `init_db(DEFAULT_DB_PATH)` — 确保所有表（包括 `gateway_configs`）已创建
  2. `_manager.load_from_db(DEFAULT_DB_PATH)` — 加载网关配置
  3. 现有的 `TradeService().sync_positions()`（顺序不变，放在最后）
- 路由文件通过 `from api.services.gateway_manager import _manager` 直接引用
- 路由文件通过 `from db.schema import DEFAULT_DB_PATH` 获取 db_path，直接传入 manager 方法

**方法签名：**

| 方法 | 签名 | 说明 |
|------|------|------|
| `load_from_db` | `(db_path: str) -> None` | 从 DB 读取所有网关配置，初始化适配器实例，不自动连接 |
| `get_all` | `(db_path: str) -> list[dict]` | 返回所有网关信息列表，secret 字段脱敏 |
| `save_config` | `(name: str, config: dict, enabled: bool, db_path: str) -> None` | 将配置写入 DB |
| `connect` | `(name: str, db_path: str) -> GatewayStatus` | 从 DB 读取该网关配置，调用适配器 `connect(config)`，持久化 status |
| `disconnect` | `(name: str, db_path: str) -> GatewayStatus` | 调用适配器 `disconnect()`，持久化 status |
| `get_status` | `(name: str) -> GatewayStatus` | 返回内存中的当前状态 |
| `route_order` | `(name: str, symbol: str, action: str, qty: float) -> OrderResult` | 路由订单到对应适配器 |

**`connect()` 流程：**
1. 从 DB 读取该网关的 `config_json`（内部读取，不需要调用方传入）
2. 调用 `gateway.connect(config)`
3. 成功：更新内存 `status='connected'`，写回 DB
4. 失败：更新内存 `status='error'`，写回 DB，re-raise 异常（由路由层 catch）

**路由层 connect 错误处理（`api/routes/gateways.py`）：**
```python
@router.post("/gateways/{name}/connect")
def connect_gateway(name: str):
    try:
        status = _manager.connect(name, DEFAULT_DB_PATH)
        return {"status": status}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown gateway: {name}")
    except Exception as e:
        return {"status": "error", "detail": str(e)}
```
`GET /gateways/{name}/status` 和 `POST /gateways/{name}/disconnect` 同样对 `KeyError` 返回 404。

**`route_order()` 异常：** 若 `name` 不在已注册网关中，抛出 `KeyError`。`trade.py` 路由在调用 `_manager.route_order()` 时用 `try/except KeyError` 捕获，返回 HTTP 400：`{"detail": "Unknown gateway: {name}"}`。

**状态持久化：** `connect()` / `disconnect()` 成功或失败后均将 status 写回 DB，重启后保留上次状态（仅供展示，实际连接需重新建立）。

**`enabled` 字段：** 通过 `save_config(enabled=True/False)` 写入 DB。前端保存配置时传入。

### 4. 数据库

**新增表** `gateway_configs`（在 `db/schema.py` 的 `init_db()` 中创建）：

```sql
CREATE TABLE IF NOT EXISTS gateway_configs (
    name        TEXT PRIMARY KEY,
    config_json TEXT NOT NULL DEFAULT '{}',
    enabled     INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'disconnected'
)
```

**初始数据：** `init_db()` 在建表后用 `INSERT OR IGNORE` 插入 4 条记录（alpaca/binance/futu/ib），`enabled=0`，`config_json='{}'`，`status='disconnected'`。

> ⚠️ **安全说明：** 配置明文存储仅适合本地开发环境。生产环境需加密存储。

### 5. API 路由

**文件：** `api/routes/gateways.py`
**注册：** `api/main.py`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/gateways` | 返回所有网关列表（含状态，secret 脱敏） |
| PUT | `/gateways/{name}` | 保存网关配置，返回更新后的 `GatewayConfig`（调用 `save_config()` 后从 `get_all()` 取回对应条目返回） |
| POST | `/gateways/{name}/connect` | 触发连接，返回 `{"status": "connected"}` 或错误 |
| POST | `/gateways/{name}/disconnect` | 断开连接，返回 `{"status": "disconnected"}` |
| GET | `/gateways/{name}/status` | 返回 `{"name": "alpaca", "status": "connected"}` |

**无效 `name`：** 所有端点对不存在的 gateway name 返回 HTTP 404。

**PUT /gateways/{name} 请求体（Pydantic 模型）：**

```python
class GatewayUpdateRequest(BaseModel):
    config: dict[str, str]  # 各网关的配置字段 key-value
    enabled: bool
```

**GET /gateways 响应示例：**
```json
[
  {
    "name": "alpaca",
    "label": "Alpaca",
    "enabled": true,
    "status": "connected",
    "config": { "api_key": "PKXXXXXXXX", "mode": "paper", "secret_key": "***" }
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
- 在现有 `TradeRequest` Pydantic 模型中新增可选字段 `gateway: str = "alpaca"`
- 现有的风险检查（`RiskGate`）、Telegram 确认流程、`record_loss()`、`_insert_pending()` 逻辑**全部保留不变**
- 仅将原来的 `alpaca_order_id = trade_svc.submit_order(...)` 替换为：
  ```python
  from api.services.gateway_manager import _manager  # 新增 import
  try:
      result = _manager.route_order(req.gateway, req.symbol.upper(), req.action, qty)
  except KeyError:
      raise HTTPException(status_code=400, detail=f"Unknown gateway: {req.gateway}")
  alpaca_order_id = result.order_id  # may be None for non-Alpaca gateways
  ```
- `AlpacaGateway.send_order()` 内部使用 `TradeService().submit_order()` 实现，保证返回非 None 的 `order_id`
- 非 Alpaca 网关的 `OrderResult.order_id` 可为 None，响应中 `order_id` 字段随之为 null（前端已有 null guard）
- 默认值 `"alpaca"` 保持向后兼容，现有调用无需修改

### 6. 新增依赖

在 `requirements.txt` 新增：
```
ccxt>=4.0.0
```

---

## 前端设计

### 页面路由

新增 `/settings` 页面（URL 路径为 `/settings`），侧边导航加入「设置」入口（`Settings` 图标，位于现有导航项末尾）。

### 文件结构

```
web/
├── app/settings/page.tsx
├── components/settings/
│   ├── GatewayList.tsx      ← 左侧接口列表（含状态圆点）
│   └── GatewayDetail.tsx    ← 右侧配置面板（含表单 + 连接/断开按钮）
├── lib/
│   ├── api.ts               ← 新增 gateway API 函数
│   └── types.ts             ← 新增 GatewayConfig interface
```

### 布局

侧边栏 + 详情面板（双栏布局）：
- 左栏（约 160px）：网关列表，每项显示状态圆点 + 名称
- 右栏：选中网关的配置表单 + 操作按钮

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

### 前端 API 函数（新增至 `web/lib/api.ts`）

| 函数名 | 对应端点 | 参数 | 返回类型 |
|--------|----------|------|----------|
| `fetchGateways()` | `GET /gateways` | — | `GatewayConfig[]` |
| `saveGateway(name, config, enabled)` | `PUT /gateways/{name}` | `name: string, config: Record<string,string>, enabled: boolean` | `GatewayConfig` |
| `connectGateway(name)` | `POST /gateways/{name}/connect` | `name: string` | `{status: string}` |
| `disconnectGateway(name)` | `POST /gateways/{name}/disconnect` | `name: string` | `{status: string}` |
| `fetchGatewayStatus(name)` | `GET /gateways/{name}/status` | `name: string` | `{name: string, status: string}` |

### 交互流程

1. 页面加载 → `fetchGateways()` → 渲染左侧列表（含 skeleton 加载态）
2. 点击左侧某接口 → 右侧显示对应配置表单
3. 填写字段 → 点「保存」→ `saveGateway()` → toast 成功/失败
4. 点「连接」→ `connectGateway()` → 刷新状态圆点
5. 点「断开」→ `disconnectGateway()` → 刷新状态圆点
6. 连接/断开操作期间，按钮显示 loading 状态，禁用点击

### 各网关表单字段

| 网关 | 字段 | 说明 |
|------|------|------|
| Alpaca | API Key、Secret Key、模式（paper/live 下拉） | |
| Binance | API Key、API Secret | |
| Futu | Host、Port | 显示提示：需运行 FutuOpenD |
| IB | Host、Port | 显示提示：需运行 TWS/IB Gateway |

Secret 字段（`secret_key`、`api_secret`）：写入时发送明文，读取时后端返回 `"***"`，前端 input 显示 placeholder `「已保存，输入新值可更新」`（值为空）。

---

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| 连接失败（API key 错误、网络不通） | 右侧面板显示红色错误信息，状态圆点变红（error） |
| Futu/IB stub 调用 | 连接时返回明确错误消息，界面显示安装提示 |
| 保存配置失败 | shadcn toast 通知 |
| `/trade` 传入无效 gateway 名称 | 返回 400，前端 toast 显示 |
| 网关名称不存在 | PUT/connect/disconnect/status 返回 404 |
| 连接/断开操作中 | 按钮显示 loading，禁止重复点击 |
| 页面加载中 | 左侧列表显示 skeleton 加载态 |

---

## 测试计划

### 后端（pytest）

**`tests/test_gateways_route.py`：**
- `GET /gateways` 返回 200 及正确结构（4 个网关）
- `GET /gateways` secret 字段已脱敏（返回 `"***"`）
- `PUT /gateways/{name}` 保存配置成功
- `PUT /gateways/{name}` 无效 name 返回 404
- `POST /gateways/{name}/connect` 成功场景（mock `_manager.connect`）
- `POST /gateways/{name}/connect` 失败场景（connect 抛出异常，返回 error status）
- `POST /gateways/{name}/disconnect` 成功
- `GET /gateways/{name}/status` 返回正确状态
- `GET /gateways/{name}/status` 无效 name 返回 404

**`tests/test_gateway_manager.py`：**
- `load_from_db()` 从 DB 正确加载配置
- `save_config()` 写入 DB 并可读回
- `route_order()` 路由到正确适配器
- `route_order()` 未知 gateway 抛出 `KeyError`
- `connect()` 成功后 status 持久化到 DB
- `connect()` 失败后 status 写为 `'error'`

**`tests/test_alpaca_gateway.py`：**
- `connect()` / `send_order()` 单测（mock HTTP）

**`tests/test_binance_gateway.py`：**
- `connect()` 成功（mock ccxt）
- `send_order()` 返回正确 `OrderResult`（mock ccxt）

**`tests/test_trade_route.py`（修改现有文件）：**
- 现有测试中将 `mock TradeService.submit_order` 替换为 `mock _manager.route_order`
- 新增：`POST /trade` 不传 `gateway` 参数，默认使用 Alpaca（向后兼容）
- 新增：`POST /trade` 传入 `gateway="binance"`，路由到 Binance 适配器
- 新增：`POST /trade` 传入无效 `gateway`，返回 400

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
- `tests/test_binance_gateway.py`

**修改：**
- `db/schema.py` — 新增 `gateway_configs` 表及初始数据
- `api/main.py` — 注册 gateways router，lifespan 中调用 `_manager.load_from_db(DEFAULT_DB_PATH)`
- `api/routes/trade.py` — `TradeRequest` 新增 `gateway` 字段，`submit_order` 调用改为 `_manager.route_order()`
- `tests/test_trade_route.py` — 更新现有 mock，新增 3 个测试
- `web/lib/api.ts` — 新增 5 个 gateway API 函数
- `web/lib/types.ts` — 新增 `GatewayConfig` interface
- `web/components/layout/Sidebar.tsx` — 新增「设置」导航项
- `requirements.txt` — 新增 `ccxt>=4.0.0`

## 前端设计

### 页面路由

新增 `/settings` 页面（URL 路径为 `/settings`），侧边导航加入「设置」入口（`Settings` 图标，位于现有导航项末尾）。

### 文件结构

```
web/
├── app/settings/page.tsx
├── components/settings/
│   ├──