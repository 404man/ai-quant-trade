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
