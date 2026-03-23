# 日常运维手册

## 启动服务

```bash
# 后端（端口 8000）
python -m uvicorn api.main:app --reload
# python -m uvicorn api.main:app --reload > /tmp/uvicorn.log 2>&1 &
echo "PID: $!"

# 前端（端口 3000）
cd web && npm run dev
```
##排查服务日
```bash
tail -f /tmp/uvicorn.log | grep -i "error\|exception\|traceback\|critical\|warning"
# & echo "Monitor PID: $!"
```


访问：`http://localhost:3000`

---

## 停止服务

```bash
# 查找占用端口的进程
lsof -i :8000 -t   # 后端
lsof -i :3000 -t   # 前端

# 杀掉进程（替换 <PID>）
kill <PID>
# kill 6178 64012 69035 && sleep 1 && python -m uvicorn api.main:app --reload > /tmp/uvicorn.log 2>&1 & echo "PID: $!"

```

---

## 环境变量

复制 `.env.example` 为 `.env`，按需填写：

| 变量 | 说明 | 必填 |
|------|------|------|
| `LOCAL_API_KEY` | Bearer Token，不设则跳过认证（开发模式） | 否 |
| `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` | Alpaca 纸交易 | 接入交易时 |
| `ANTHROPIC_API_KEY` | Claude AI 情绪分析 | 使用情绪模块时 |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Telegram 交易确认 | 使用 Telegram 时 |
| `OPENCLAW_HOOK_URL` / `OPENCLAW_HOOK_TOKEN` | OpenClaw Webhook | 使用 OpenClaw 时 |

---

## 数据库

SQLite，位于 `api/cache.db`。

```bash
# 查看价格缓存情况
python3 -c "
from db.schema import get_connection, DEFAULT_DB_PATH
conn = get_connection(DEFAULT_DB_PATH)
rows = conn.execute('SELECT symbol, MIN(date), MAX(date), COUNT(*) FROM price_cache GROUP BY symbol').fetchall()
for r in rows: print(r)
conn.close()
"

# 清空某只股票缓存（强制重新拉取）
python3 -c "
from db.schema import get_connection, DEFAULT_DB_PATH
conn = get_connection(DEFAULT_DB_PATH)
conn.execute('DELETE FROM price_cache WHERE symbol = ?', ('AAPL',))
conn.commit()
conn.close()
print('done')
"
```

---

## 数据源（Yahoo Finance）限流

Yahoo Finance 对高频请求限流（429）。缓解方法：

1. **优先使用已缓存数据**（系统已自动缓存历史数据）
2. **开启 VPN 全局模式**，切换出口 IP
3. 确认 Python 走代理：

```bash
# 检查系统代理端口（一般为 7897）
scutil --proxy | grep -E "HTTPProxy|HTTPPort"

# 验证 Python 是否走代理
export HTTPS_PROXY=http://127.0.0.1:7897
python3 -c "import yfinance as yf; df = yf.download('AAPL', start='2025-01-01', end='2025-03-01', progress=False); print(df.shape)"
```

4. 若需要持久生效，在 `.env` 中添加：
```
HTTPS_PROXY=http://127.0.0.1:7897
HTTP_PROXY=http://127.0.0.1:7897
```

---

## 运行测试

```bash
python -m pytest tests/ -q
```

当前：195 个测试，全部通过。

---

## 日志

后端日志输出到终端（`--reload` 模式），也可重定向到文件：

```bash
python -m uvicorn api.main:app --reload > /tmp/uvicorn.log 2>&1 &
tail -f /tmp/uvicorn.log
# 只看错误
tail -f /tmp/uvicorn.log | grep -i "error\|exception\|critical"
```

---

## 常见问题

**后端启动报 `Address already in use`**
```bash
kill $(lsof -i :8000 -t)
```

**回测 / 信号接口返回 404 `No price data`**
- 先确认缓存里是否已有该股票数据（见数据库章节）
- 若没有，需要通过 VPN 拉取（见数据源章节）

**前端报跨域错误**
- 不应该出现，前端通过 `/api/*` 代理转发请求，不直接访问 `:8000`
- 确认前端 `lib/api.ts` 的 `BASE_URL` 是 `/api`（非 `http://localhost:8000`）

**Gateway 连接报错 `'api_key'`**
- 正常提示：Alpaca 未配置 API Key
- 在设置页面填入 `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` 后重试

---

## 构建 & 部署

```bash
# 检查前端构建
cd web && npm run build

# 生产启动（不带 --reload）
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
cd web && npm start
```
