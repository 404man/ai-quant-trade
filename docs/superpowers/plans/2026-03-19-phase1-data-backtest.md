# Phase 1: 数据层 + 回测基础 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建可工作的数据采集 + SQLite 缓存 + vectorbt 回测系统，通过 FastAPI 暴露 `/backtest` 和 `/data` 端点，返回含 Sharpe/最大回撤/年化收益的回测结果。

**Architecture:** FastAPI 作为入口，`data_service` 负责从 Polygon（或 yfinance 备用）拉取历史行情并缓存到 SQLite，`backtest_service` 调用 vectorbt 运行 RSI/MA 策略并返回指标，两个策略文件各自定义信号逻辑。

**Tech Stack:** Python 3.11, FastAPI, uvicorn, vectorbt, pandas-ta, yfinance, requests, sqlite3 (stdlib), pytest, httpx

---

## 文件结构

```
stock/
├── api/
│   ├── main.py                   # FastAPI app，注册路由
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── data.py               # GET /data/price
│   │   └── backtest.py           # GET /backtest
│   └── services/
│       ├── __init__.py
│       ├── data_service.py       # 数据拉取 + SQLite 缓存
│       └── backtest_service.py   # vectorbt 封装，返回指标
├── strategies/
│   ├── __init__.py
│   ├── rsi_strategy.py           # RSI(14) 信号生成
│   └── ma_crossover_strategy.py  # MA(10/30) 信号生成
├── db/
│   └── schema.py                 # SQLite 建表 + 连接工具
├── tests/
│   ├── __init__.py
│   ├── test_data_service.py
│   ├── test_backtest_service.py
│   ├── test_rsi_strategy.py
│   ├── test_ma_strategy.py
│   └── test_api_routes.py
├── data/                         # SQLite 文件存放（.gitignore）
├── .env.example
├── .gitignore
└── requirements.txt
```

---

## Task 0: 项目初始化

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`

- [ ] **Step 1: 验证 Python 版本**

```bash
python3 --version
```
Expected: Python 3.11.x 或更高

- [ ] **Step 2: 创建 requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
vectorbt==0.26.2
pandas-ta==0.3.14b0
yfinance==0.2.40
requests==2.32.3
httpx==0.27.0
pytest==8.3.0
pytest-asyncio==0.23.8
python-dotenv==1.0.1
```

- [ ] **Step 3: 安装依赖**

```bash
pip install -r requirements.txt
```

Expected: 全部安装成功，无报错

- [ ] **Step 4: 创建 .env.example**

```
# Polygon.io API Key（免费注册：https://polygon.io）
POLYGON_API_KEY=your_polygon_key_here

# 数据源：polygon 或 yfinance
DATA_SOURCE=yfinance

# 本地 API Key（用于 OpenClaw 认证，Phase 3 启用）
LOCAL_API_KEY=change_me_before_phase3
```

- [ ] **Step 5: 创建 .gitignore**

```
.env
data/
logs/
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
dist/
```

- [ ] **Step 6: 验证 Polygon 免费套餐数据范围**

```python
# 在终端快速验证（替换为你的 key）
import requests
r = requests.get(
    "https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/2020-01-01/2020-01-10",
    params={"apiKey": "YOUR_KEY"}
)
print(r.status_code, r.json().get("resultsCount"))
```

Expected: status 200，resultsCount > 0

如果 status 403 或 resultsCount = 0，在 `.env.example` 中将 `DATA_SOURCE` 默认改为 `yfinance`。

- [ ] **Step 7: 创建目录结构**

```bash
mkdir -p api/routes api/services strategies db tests data logs
touch api/__init__.py api/routes/__init__.py api/services/__init__.py
touch strategies/__init__.py tests/__init__.py db/__init__.py
```

- [ ] **Step 8: 初始化 git 仓库并首次提交**

```bash
git init
git add requirements.txt .env.example .gitignore
git commit -m "chore: project scaffold and dependencies"
```

---

## Task 1: SQLite 数据库层

**Files:**
- Create: `db/schema.py`
- Test: `tests/test_db_schema.py`

### 背景

`db/schema.py` 负责两件事：提供数据库连接，建立 `price_cache` 表（存 OHLCV 数据）。所有其他模块通过这里的函数访问数据库。

- [ ] **Step 1: 写失败测试**

Create `tests/test_db_schema.py`:

```python
import sqlite3
import tempfile
import os
import pytest
from db.schema import get_connection, init_db


def test_init_db_creates_price_cache_table():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='price_cache'"
        )
        assert cursor.fetchone() is not None
        conn.close()
    finally:
        os.unlink(db_path)


def test_price_cache_has_required_columns():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA table_info(price_cache)")
        columns = {row[1] for row in cursor.fetchall()}
        assert {"symbol", "date", "open", "high", "low", "close", "volume"}.issubset(columns)
        conn.close()
    finally:
        os.unlink(db_path)


def test_get_connection_returns_connection():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        init_db(db_path)
        conn = get_connection(db_path)
        assert isinstance(conn, sqlite3.Connection)
        conn.close()
    finally:
        os.unlink(db_path)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_db_schema.py -v
```

Expected: FAILED（ImportError: cannot import name 'get_connection'）

- [ ] **Step 3: 实现 db/schema.py**

```python
import sqlite3
import os

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "cache.db")


def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    dir_name = os.path.dirname(db_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    conn = get_connection(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS price_cache (
            symbol  TEXT NOT NULL,
            date    TEXT NOT NULL,
            open    REAL NOT NULL,
            high    REAL NOT NULL,
            low     REAL NOT NULL,
            close   REAL NOT NULL,
            volume  INTEGER NOT NULL,
            PRIMARY KEY (symbol, date)
        )
    """)
    conn.commit()
    conn.close()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_db_schema.py -v
```

Expected: 3 PASSED

- [ ] **Step 5: 提交**

```bash
git add db/schema.py tests/test_db_schema.py
git commit -m "feat: SQLite schema with price_cache table"
```

---

## Task 2: 数据服务（yfinance + SQLite 缓存）

**Files:**
- Create: `api/services/data_service.py`
- Test: `tests/test_data_service.py`

### 背景

`data_service.py` 负责：先查 SQLite 缓存，缓存命中则直接返回；缓存未命中则从 yfinance（或 Polygon）拉取，写入缓存，再返回。返回格式是 `list[dict]`，每条记录包含 `date, open, high, low, close, volume`。

- [ ] **Step 1: 写失败测试**

Create `tests/test_data_service.py`:

```python
import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock
import pandas as pd
from db.schema import init_db
from api.services.data_service import DataService


@pytest.fixture
def tmp_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return db_path


def make_mock_yf_data():
    """返回模拟的 yfinance DataFrame"""
    dates = pd.date_range("2024-01-02", periods=3, freq="B")
    df = pd.DataFrame({
        "Open": [185.0, 186.0, 187.0],
        "High": [187.0, 188.0, 189.0],
        "Low":  [184.0, 185.0, 186.0],
        "Close": [186.0, 187.0, 188.0],
        "Volume": [50000000, 51000000, 52000000],
    }, index=dates)
    df.index.name = "Date"
    return df


def test_fetch_returns_list_of_dicts(tmp_db):
    svc = DataService(db_path=tmp_db)
    with patch("api.services.data_service.yf.download", return_value=make_mock_yf_data()):
        result = svc.fetch("AAPL", "2024-01-01", "2024-01-05")
    assert isinstance(result, list)
    assert len(result) == 3
    assert set(result[0].keys()) == {"date", "open", "high", "low", "close", "volume"}


def test_fetch_caches_result(tmp_db):
    svc = DataService(db_path=tmp_db)
    with patch("api.services.data_service.yf.download", return_value=make_mock_yf_data()) as mock_dl:
        svc.fetch("AAPL", "2024-01-01", "2024-01-05")
        svc.fetch("AAPL", "2024-01-01", "2024-01-05")
    # 第二次应从缓存读取，不再调用 yfinance
    assert mock_dl.call_count == 1


def test_fetch_returns_sorted_by_date(tmp_db):
    svc = DataService(db_path=tmp_db)
    with patch("api.services.data_service.yf.download", return_value=make_mock_yf_data()):
        result = svc.fetch("AAPL", "2024-01-01", "2024-01-05")
    dates = [r["date"] for r in result]
    assert dates == sorted(dates)


def test_fetch_empty_date_range_returns_empty_list(tmp_db):
    svc = DataService(db_path=tmp_db)
    with patch("api.services.data_service.yf.download", return_value=pd.DataFrame()):
        result = svc.fetch("AAPL", "2024-01-01", "2024-01-01")
    assert result == []
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_data_service.py -v
```

Expected: FAILED（ImportError）

- [ ] **Step 3: 实现 api/services/data_service.py**

```python
import yfinance as yf
import pandas as pd
from db.schema import get_connection, init_db, DEFAULT_DB_PATH


class DataService:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        init_db(db_path)

    def fetch(self, symbol: str, start: str, end: str) -> list[dict]:
        """
        返回 symbol 在 [start, end] 日期范围内的日线数据。
        优先从 SQLite 缓存读取，缓存未命中时从 yfinance 拉取并写入缓存。
        """
        cached = self._read_cache(symbol, start, end)
        if cached:
            return cached

        raw = self._fetch_yfinance(symbol, start, end)
        if raw:
            self._write_cache(symbol, raw)
        return raw

    def _read_cache(self, symbol: str, start: str, end: str) -> list[dict]:
        conn = get_connection(self.db_path)
        cursor = conn.execute(
            "SELECT date, open, high, low, close, volume FROM price_cache "
            "WHERE symbol = ? AND date >= ? AND date <= ? ORDER BY date",
            (symbol, start, end),
        )
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def _fetch_yfinance(self, symbol: str, start: str, end: str) -> list[dict]:
        df = yf.download(symbol, start=start, end=end, progress=False, auto_adjust=True)
        if df.empty:
            return []
        # yfinance >= 0.2.18 returns MultiIndex columns for single ticker downloads
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.reset_index()
        records = []
        for _, row in df.iterrows():
            records.append({
                "date": str(row["Date"])[:10],
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"]),
            })
        return records

    def _write_cache(self, symbol: str, records: list[dict]) -> None:
        conn = get_connection(self.db_path)
        conn.executemany(
            "INSERT OR REPLACE INTO price_cache "
            "(symbol, date, open, high, low, close, volume) VALUES (?,?,?,?,?,?,?)",
            [
                (symbol, r["date"], r["open"], r["high"], r["low"], r["close"], r["volume"])
                for r in records
            ],
        )
        conn.commit()
        conn.close()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_data_service.py -v
```

Expected: 4 PASSED

- [ ] **Step 5: 提交**

```bash
git add api/services/data_service.py tests/test_data_service.py
git commit -m "feat: data service with yfinance fetch and SQLite cache"
```

---

## Task 3: RSI 策略信号

**Files:**
- Create: `strategies/rsi_strategy.py`
- Test: `tests/test_rsi_strategy.py`

### 背景

`rsi_strategy.py` 接收价格 DataFrame，返回 buy/sell/hold 信号 Series。规则：RSI(14) < 30 → buy，RSI(14) > 70 → sell，其余 → hold。持仓超 10 日强制平仓的逻辑在 `backtest_service` 中处理，不在这里。

- [ ] **Step 1: 写失败测试**

Create `tests/test_rsi_strategy.py`:

```python
import pytest
import pandas as pd
import numpy as np
from strategies.rsi_strategy import generate_signals


def make_price_series(values: list[float]) -> pd.Series:
    return pd.Series(values, name="close")


def test_returns_series_with_signal_values():
    prices = make_price_series([100.0] * 30)
    signals = generate_signals(prices)
    assert isinstance(signals, pd.Series)
    assert set(signals.unique()).issubset({"buy", "sell", "hold"})


def test_oversold_generates_buy():
    # 构造持续下跌序列使 RSI 低于 30
    prices = make_price_series([100 - i * 2 for i in range(30)])
    signals = generate_signals(prices)
    # 后段应出现 buy 信号
    assert "buy" in signals.values


def test_overbought_generates_sell():
    # 构造持续上涨序列使 RSI 高于 70
    prices = make_price_series([100 + i * 2 for i in range(30)])
    signals = generate_signals(prices)
    # 后段应出现 sell 信号
    assert "sell" in signals.values


def test_insufficient_data_returns_hold():
    # RSI(14) 需要至少 15 个数据点
    prices = make_price_series([100.0] * 10)
    signals = generate_signals(prices)
    assert (signals == "hold").all()


def test_output_length_matches_input():
    prices = make_price_series([100.0] * 50)
    signals = generate_signals(prices)
    assert len(signals) == len(prices)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_rsi_strategy.py -v
```

Expected: FAILED（ImportError）

- [ ] **Step 3: 实现 strategies/rsi_strategy.py**

```python
import pandas as pd
import talib


def generate_signals(prices: pd.Series) -> pd.Series:
    """
    输入: 收盘价 Series（至少 15 个数据点才能计算 RSI(14)）
    输出: 同长度 Series，值为 "buy" / "sell" / "hold"
    规则: RSI < 30 → buy，RSI > 70 → sell，其余 → hold
    """
    signals = pd.Series("hold", index=prices.index)

    if len(prices) < 15:
        return signals

    rsi = talib.RSI(prices.values, timeperiod=14)
    rsi_series = pd.Series(rsi, index=prices.index)

    signals[rsi_series < 30] = "buy"
    signals[rsi_series > 70] = "sell"

    return signals
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_rsi_strategy.py -v
```

Expected: 5 PASSED

- [ ] **Step 5: 提交**

```bash
git add strategies/rsi_strategy.py tests/test_rsi_strategy.py
git commit -m "feat: RSI(14) signal generator"
```

---

## Task 4: MA 双线交叉策略信号

**Files:**
- Create: `strategies/ma_crossover_strategy.py`
- Test: `tests/test_ma_strategy.py`

### 背景

`ma_crossover_strategy.py` 接收收盘价 Series，返回信号 Series。规则：MA(10) 上穿 MA(30)（金叉）→ buy，MA(10) 下穿 MA(30)（死叉）→ sell，其余 → hold。

- [ ] **Step 1: 写失败测试**

Create `tests/test_ma_strategy.py`:

```python
import pytest
import pandas as pd
from strategies.ma_crossover_strategy import generate_signals


def test_returns_series_with_valid_values():
    prices = pd.Series([float(100 + i % 5) for i in range(50)])
    signals = generate_signals(prices)
    assert isinstance(signals, pd.Series)
    assert set(signals.unique()).issubset({"buy", "sell", "hold"})


def test_golden_cross_generates_buy():
    # 先下跌（死叉状态），再上涨（产生金叉）
    down = [100 - i for i in range(30)]
    up = [70 + i for i in range(20)]
    prices = pd.Series(down + up)
    signals = generate_signals(prices)
    assert "buy" in signals.values


def test_death_cross_generates_sell():
    # 先上涨（让金叉稳定建立），再大幅下跌（产生死叉）
    # 需要足够长的下跌段（40 个点）确保 MA(10) 能穿越 MA(30)
    up = [100 + i for i in range(40)]
    down = [140 - i * 2 for i in range(40)]
    prices = pd.Series(up + down)
    signals = generate_signals(prices)
    assert "sell" in signals.values


def test_insufficient_data_returns_hold():
    # MA(30) 需要至少 30 个数据点
    prices = pd.Series([100.0] * 25)
    signals = generate_signals(prices)
    assert (signals == "hold").all()


def test_output_length_matches_input():
    prices = pd.Series([float(i) for i in range(60)])
    signals = generate_signals(prices)
    assert len(signals) == len(prices)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_ma_strategy.py -v
```

Expected: FAILED（ImportError）

- [ ] **Step 3: 实现 strategies/ma_crossover_strategy.py**

```python
import pandas as pd


def generate_signals(prices: pd.Series) -> pd.Series:
    """
    输入: 收盘价 Series（至少 30 个数据点才能计算 MA(30)）
    输出: 同长度 Series，值为 "buy" / "sell" / "hold"
    规则: MA(10) 上穿 MA(30) → buy（金叉），MA(10) 下穿 MA(30) → sell（死叉）
    """
    signals = pd.Series("hold", index=prices.index)

    if len(prices) < 30:
        return signals

    ma_fast = prices.rolling(10).mean()
    ma_slow = prices.rolling(30).mean()

    # 金叉：fast 从下方穿越 slow
    golden_cross = (ma_fast > ma_slow) & (ma_fast.shift(1) <= ma_slow.shift(1))
    # 死叉：fast 从上方穿越 slow
    death_cross = (ma_fast < ma_slow) & (ma_fast.shift(1) >= ma_slow.shift(1))

    signals[golden_cross] = "buy"
    signals[death_cross] = "sell"

    return signals
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_ma_strategy.py -v
```

Expected: 5 PASSED

- [ ] **Step 5: 提交**

```bash
git add strategies/ma_crossover_strategy.py tests/test_ma_strategy.py
git commit -m "feat: MA(10/30) crossover signal generator"
```

---

## Task 5: 回测服务

**Files:**
- Create: `api/services/backtest_service.py`
- Test: `tests/test_backtest_service.py`

### 背景

`backtest_service.py` 接收价格数据（`list[dict]`）和策略名称，使用 vectorbt 运行回测，返回包含 Sharpe Ratio、最大回撤、年化收益、交易次数的字典。手续费：每笔 $1（固定），滑点：0.1%。RSI 策略额外支持持仓超 10 个交易日强制平仓（spec 要求）。

- [ ] **Step 1: 写失败测试**

Create `tests/test_backtest_service.py`:

```python
import pytest
from api.services.backtest_service import BacktestService


def make_price_data(n: int = 200) -> list[dict]:
    """生成 n 天的合成价格数据"""
    import random
    random.seed(42)
    price = 100.0
    records = []
    for i in range(n):
        change = random.uniform(-2, 2)
        price = max(10.0, price + change)
        records.append({
            "date": f"2020-{(i // 30 + 1):02d}-{(i % 28 + 1):02d}",
            "open": price - 0.1,
            "high": price + 0.5,
            "low": price - 0.5,
            "close": price,
            "volume": 1000000,
        })
    return records


def test_backtest_returns_required_keys():
    svc = BacktestService()
    result = svc.run(make_price_data(), strategy="rsi")
    assert set(result.keys()) >= {"sharpe_ratio", "max_drawdown", "annual_return", "trade_count"}


def test_backtest_sharpe_is_float():
    svc = BacktestService()
    result = svc.run(make_price_data(), strategy="rsi")
    assert isinstance(result["sharpe_ratio"], float)


def test_backtest_max_drawdown_is_negative_or_zero():
    svc = BacktestService()
    result = svc.run(make_price_data(), strategy="rsi")
    assert result["max_drawdown"] <= 0.0


def test_backtest_rsi_has_max_duration_exit():
    """RSI 策略：持仓超 10 日应强制出场（trade_count 应 > 0 且平均持仓 ≤ 10 天）"""
    svc = BacktestService()
    result = svc.run(make_price_data(n=200), strategy="rsi")
    # 有交易发生时，avg_holding_days 应 ≤ 10
    if result["trade_count"] > 0:
        assert result.get("avg_holding_days", 10) <= 10


def test_backtest_trade_count_is_non_negative():
    svc = BacktestService()
    result = svc.run(make_price_data(), strategy="rsi")
    assert result["trade_count"] >= 0


def test_backtest_supports_ma_strategy():
    svc = BacktestService()
    result = svc.run(make_price_data(), strategy="ma")
    assert "sharpe_ratio" in result


def test_backtest_raises_on_unknown_strategy():
    svc = BacktestService()
    with pytest.raises(ValueError, match="Unknown strategy"):
        svc.run(make_price_data(), strategy="unknown")


def test_backtest_requires_minimum_data():
    svc = BacktestService()
    result = svc.run(make_price_data(n=10), strategy="rsi")
    # 数据不足时 trade_count 为 0
    assert result["trade_count"] == 0
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_backtest_service.py -v
```

Expected: FAILED（ImportError）

- [ ] **Step 3: 实现 api/services/backtest_service.py**

```python
import pandas as pd
import numpy as np
import vectorbt as vbt
from strategies.rsi_strategy import generate_signals as rsi_signals
from strategies.ma_crossover_strategy import generate_signals as ma_signals

COMMISSION_PER_TRADE = 1.0  # $1 每笔
SLIPPAGE_PCT = 0.001         # 0.1%

STRATEGY_MAP = {
    "rsi": rsi_signals,
    "ma": ma_signals,
}

# RSI 策略：持仓超 10 个交易日强制平仓（spec 要求）
RSI_MAX_HOLDING_DAYS = 10


class BacktestService:
    def run(self, price_data: list[dict], strategy: str) -> dict:
        """
        运行回测，返回绩效指标。
        price_data: list of {date, open, high, low, close, volume}
        strategy: "rsi" 或 "ma"
        """
        if strategy not in STRATEGY_MAP:
            raise ValueError(f"Unknown strategy: {strategy}. Valid: {list(STRATEGY_MAP.keys())}")

        if len(price_data) < 30:
            return {
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "annual_return": 0.0,
                "trade_count": 0,
            }

        df = pd.DataFrame(price_data)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        close = df["close"]

        signal_fn = STRATEGY_MAP[strategy]
        signals = signal_fn(close)

        entries = signals == "buy"
        exits = signals == "sell"

        # RSI 策略：持仓超 10 个交易日强制平仓
        max_duration = RSI_MAX_HOLDING_DAYS if strategy == "rsi" else None

        # vectorbt Portfolio
        # fees 使用比例：固定 $1 手续费除以股价 ≈ 当笔交易的费率
        # 注意：这是每笔交易时按当前价格折算，近似处理
        pf = vbt.Portfolio.from_signals(
            close,
            entries=entries,
            exits=exits,
            fees=COMMISSION_PER_TRADE / close.mean(),  # 用均价折算为固定比例，避免逐 bar 计费
            slippage=SLIPPAGE_PCT,
            freq="D",
            max_duration=max_duration,  # None = 不限制；RSI 时 = 10 天
        )

        stats = pf.stats()

        sharpe = float(stats.get("Sharpe Ratio", 0.0) or 0.0)
        max_dd = float(stats.get("Max Drawdown [%]", 0.0) or 0.0) / -100.0
        total_return = float(stats.get("Total Return [%]", 0.0) or 0.0) / 100.0
        trade_count = int(stats.get("Total Trades", 0) or 0)

        # 年化收益（简单估算）
        n_days = len(close)
        annual_return = (1 + total_return) ** (252 / max(n_days, 1)) - 1

        return {
            "sharpe_ratio": round(sharpe, 4),
            "max_drawdown": round(max_dd, 4),
            "annual_return": round(annual_return, 4),
            "trade_count": trade_count,
            "avg_holding_days": round(float(pf.trades.duration.mean() or 0), 1),
        }
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_backtest_service.py -v
```

Expected: 7 PASSED

- [ ] **Step 5: 提交**

```bash
git add api/services/backtest_service.py tests/test_backtest_service.py
git commit -m "feat: vectorbt backtest service with RSI and MA strategies"
```

---

## Task 6: FastAPI 路由

**Files:**
- Create: `api/main.py`
- Create: `api/routes/data.py`
- Create: `api/routes/backtest.py`
- Test: `tests/test_api_routes.py`

### 背景

两个路由：
- `GET /data/price?symbol=AAPL&start=2024-01-01&end=2024-12-31` → 返回价格列表
- `GET /backtest?symbol=AAPL&strategy=rsi&start=2020-01-01&end=2023-12-31` → 返回回测指标

两个路由都在内部调用 service 层，不含业务逻辑。

- [ ] **Step 1: 写失败测试**

Create `tests/test_api_routes.py`:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from api.main import app

client = TestClient(app)

MOCK_PRICES = [
    {"date": "2024-01-02", "open": 185.0, "high": 187.0, "low": 184.0, "close": 186.0, "volume": 50000000},
    {"date": "2024-01-03", "open": 186.0, "high": 188.0, "low": 185.0, "close": 187.0, "volume": 51000000},
]

MOCK_BACKTEST = {
    "sharpe_ratio": 1.23,
    "max_drawdown": -0.15,
    "annual_return": 0.22,
    "trade_count": 42,
}


def test_data_price_returns_200():
    with patch("api.routes.data.DataService") as MockSvc:
        MockSvc.return_value.fetch.return_value = MOCK_PRICES
        resp = client.get("/data/price?symbol=AAPL&start=2024-01-01&end=2024-01-31")
    assert resp.status_code == 200


def test_data_price_returns_list():
    with patch("api.routes.data.DataService") as MockSvc:
        MockSvc.return_value.fetch.return_value = MOCK_PRICES
        resp = client.get("/data/price?symbol=AAPL&start=2024-01-01&end=2024-01-31")
    assert isinstance(resp.json(), list)
    assert len(resp.json()) == 2


def test_data_price_missing_params_returns_422():
    resp = client.get("/data/price?symbol=AAPL")
    assert resp.status_code == 422


def test_backtest_returns_200():
    with patch("api.routes.backtest.DataService") as MockData, \
         patch("api.routes.backtest.BacktestService") as MockBacktest:
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockBacktest.return_value.run.return_value = MOCK_BACKTEST
        resp = client.get("/backtest?symbol=AAPL&strategy=rsi&start=2020-01-01&end=2023-12-31")
    assert resp.status_code == 200


def test_backtest_returns_required_fields():
    with patch("api.routes.backtest.DataService") as MockData, \
         patch("api.routes.backtest.BacktestService") as MockBacktest:
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockBacktest.return_value.run.return_value = MOCK_BACKTEST
        resp = client.get("/backtest?symbol=AAPL&strategy=rsi&start=2020-01-01&end=2023-12-31")
    body = resp.json()
    assert {"sharpe_ratio", "max_drawdown", "annual_return", "trade_count"}.issubset(body.keys())


def test_backtest_invalid_strategy_returns_400():
    with patch("api.routes.backtest.DataService") as MockData:
        MockData.return_value.fetch.return_value = MOCK_PRICES
        resp = client.get("/backtest?symbol=AAPL&strategy=invalid&start=2020-01-01&end=2023-12-31")
    assert resp.status_code == 400


def test_health_check():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_api_routes.py -v
```

Expected: FAILED（ImportError: cannot import name 'app'）

- [ ] **Step 3: 创建 api/main.py 骨架（解除 ImportError）**

```python
from fastapi import FastAPI

app = FastAPI(title="AI Quant System", version="0.1.0")

@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 4: 运行测试，确认只剩路由 404（非 ImportError）**

```bash
pytest tests/test_api_routes.py -v
```

Expected: `test_health_check` PASSED，其余 FAILED（404 或 ImportError on routes）

- [ ] **Step 5: 实现 api/routes/data.py**

```python
from fastapi import APIRouter
from api.services.data_service import DataService

router = APIRouter()


@router.get("/data/price")
def get_price(symbol: str, start: str, end: str):
    svc = DataService()
    return svc.fetch(symbol.upper(), start, end)
```

- [ ] **Step 6: 实现 api/routes/backtest.py**

```python
from fastapi import APIRouter, HTTPException
from api.services.data_service import DataService
from api.services.backtest_service import BacktestService

router = APIRouter()


@router.get("/backtest")
def run_backtest(symbol: str, strategy: str, start: str, end: str):
    data_svc = DataService()
    backtest_svc = BacktestService()

    prices = data_svc.fetch(symbol.upper(), start, end)
    if not prices:
        raise HTTPException(status_code=404, detail=f"No price data for {symbol}")

    try:
        result = backtest_svc.run(prices, strategy=strategy)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "symbol": symbol.upper(),
        "strategy": strategy,
        "start": start,
        "end": end,
        **result,
    }
```

- [ ] **Step 7: 更新 api/main.py，注册路由**

```python
from fastapi import FastAPI
from api.routes.data import router as data_router
from api.routes.backtest import router as backtest_router

app = FastAPI(title="AI Quant System", version="0.1.0")

app.include_router(data_router)
app.include_router(backtest_router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 8: 运行测试确认通过**

```bash
pytest tests/test_api_routes.py -v
```

Expected: 7 PASSED

- [ ] **Step 9: 运行全部测试**

```bash
pytest tests/ -v
```

Expected: 全部 PASSED（~26 tests）

- [ ] **Step 10: 提交**

```bash
git add api/main.py api/routes/data.py api/routes/backtest.py tests/test_api_routes.py
git commit -m "feat: FastAPI routes for /data/price and /backtest"
```

---

## Task 7: 端到端冒烟测试

**Files:**（无新文件，手动验证）

- [ ] **Step 1: 启动服务**

```bash
uvicorn api.main:app --reload --port 8000
```

Expected: `INFO: Application startup complete.`

- [ ] **Step 2: 健康检查**

```bash
curl http://localhost:8000/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 3: 拉取真实数据**

```bash
curl "http://localhost:8000/data/price?symbol=AAPL&start=2024-01-01&end=2024-01-10"
```

Expected: JSON 数组，包含 2024 年 1 月初几个交易日的 OHLCV 数据

- [ ] **Step 4: 运行 RSI 回测（训练集）**

```bash
curl "http://localhost:8000/backtest?symbol=AAPL&strategy=rsi&start=2020-01-01&end=2023-12-31"
```

Expected: JSON 含 `sharpe_ratio`, `max_drawdown`, `annual_return`, `trade_count`，数值合理（trade_count > 0）

- [ ] **Step 5: 运行 RSI 回测（验证集）**

```bash
curl "http://localhost:8000/backtest?symbol=AAPL&strategy=rsi&start=2024-01-01&end=2024-12-31"
```

记录结果，与训练集对比。**如果验证集 Sharpe < 1.0，Phase 1 仍完成，但在 Phase 3 的 Go/No-Go 门需要特别关注。**

- [ ] **Step 6: 运行 MA 回测**

```bash
curl "http://localhost:8000/backtest?symbol=AAPL&strategy=ma&start=2020-01-01&end=2023-12-31"
```

- [ ] **Step 7: 最终提交**

```bash
git add .
git commit -m "chore: Phase 1 complete - data + backtest pipeline working"
```

---

## Phase 1 完成标准

- [ ] `pytest tests/ -v` 全部 PASSED
- [ ] `/health` 返回 200
- [ ] `/data/price` 返回真实 AAPL 价格数据
- [ ] `/backtest?strategy=rsi` 和 `/backtest?strategy=ma` 均返回合理回测指标
- [ ] `data/cache.db` 存在，第二次请求同一 symbol 不再调用 yfinance（从缓存读取）

---

## 下一步

Phase 1 完成后，继续执行 Phase 2 计划（AI 情绪分析）：`docs/superpowers/plans/2026-03-19-phase2-sentiment.md`（待写）
