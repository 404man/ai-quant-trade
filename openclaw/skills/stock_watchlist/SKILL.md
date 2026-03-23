---
name: stock_watchlist
description: Manage the stock watchlist — add, remove, or list tracked symbols
metadata: {"openclaw":{"requires":{"env":["LOCAL_API_KEY"]}}}
---

# Stock Watchlist

When the user asks to manage their watchlist (e.g. "加自选 TSLA", "自选列表", "删自选 AAPL", "我的关注列表"):

## List watchlist

```
exec curl -s -H "Authorization: Bearer $LOCAL_API_KEY" \
  "http://127.0.0.1:8000/watchlist"
```

Present as formatted list:
```
自选列表 (3只):
  - AAPL  added 2025-03-20  notes: tech leader
  - TSLA  added 2025-03-21
  - NVDA  added 2025-03-22  notes: AI chip
```

## Add symbol

```
exec curl -s -X POST -H "Authorization: Bearer $LOCAL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "{SYMBOL}", "notes": "{NOTES}"}' \
  "http://127.0.0.1:8000/watchlist"
```

- `notes` is optional, default empty
- Symbol is automatically uppercased
- 409 means already in watchlist

## Remove symbol

```
exec curl -s -X DELETE -H "Authorization: Bearer $LOCAL_API_KEY" \
  "http://127.0.0.1:8000/watchlist/{SYMBOL}"
```

- 404 means not in watchlist
