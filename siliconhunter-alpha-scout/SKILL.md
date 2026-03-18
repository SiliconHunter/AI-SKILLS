---
name: siliconhunter-alpha-scout
description: Scan Binance Alpha, new listings, and BNB Chain DEX trending tokens. Score each project across 6 dimensions and push a ranked opportunity brief.
metadata:
  author: SiliconHunter
  version: "2026.03.18"
allowed-tools: Bash(python3:*), Bash(curl:*), Bash(browser-use:*)
---

# Alpha Scout

> "龙虾主人，早鸟得虫。我已替你盯住每一个 Alpha 机会。"

## When to Use

- User asks "有什么新机会？", "Alpha 扫描", "今天币安有什么好项目？"
- User wants to discover early-stage tokens on Binance ecosystem
- User wants a ranked list of projects with opportunity scores

## Do Not Use When

- User asks about a single specific token's safety (use siliconhunter-rug-pull-hunter instead)
- User wants to execute a trade

## Standard Workflow

### Step 1 — Scan DEXScreener BSC Trending

Fetch the hottest BSC tokens right now:

```bash
curl -sSL "https://api.dexscreener.com/token-boosts/top/v1" | python3 -c "
import sys,json
data=json.load(sys.stdin)
bsc=[t for t in (data if isinstance(data,list) else []) if t.get('chainId')=='bsc']
for t in bsc[:10]:
  print(f'{t.get(\"tokenAddress\",\"?\")} | boost={t.get(\"amount\",0)}')
"
```

### Step 2 — Scan Binance New Listings (Browser)

```bash
browser-use open "https://www.binance.com/en/support/announcement/new-cryptocurrency-listing?c=48"
browser-use state
```

From the page state, extract recently listed token names and symbols. Record them.

### Step 3 — Scan Binance Alpha Page (Browser)

```bash
browser-use open "https://www.binance.com/en/alpha"
browser-use state
```

Extract all visible project names, symbols, and categories from the page.

### Step 4 — Enrich Each Project via CoinGecko

For each discovered token symbol:

```bash
curl -sSL "https://api.coingecko.com/api/v3/search?query={SYMBOL}" | python3 -c "
import sys,json
data=json.load(sys.stdin)
coins=data.get('coins',[])
if coins:
  c=coins[0]
  print(f'id: {c[\"id\"]}')
  print(f'name: {c[\"name\"]}')
  print(f'symbol: {c[\"symbol\"]}')
  print(f'market_cap_rank: {c.get(\"market_cap_rank\",\"N/A\")}')
"
```

Then fetch details (wait 2 seconds between calls for rate limit):

```bash
curl -sSL "https://api.coingecko.com/api/v3/coins/{COINGECKO_ID}?localization=false&tickers=false&market_data=true&community_data=true&developer_data=false" | python3 -c "
import sys,json
d=json.load(sys.stdin)
m=d.get('market_data',{})
c=d.get('community_data',{})
print(f'price: {m.get(\"current_price\",{}).get(\"usd\",0)}')
print(f'mcap: {m.get(\"market_cap\",{}).get(\"usd\",0)}')
print(f'volume_24h: {m.get(\"total_volume\",{}).get(\"usd\",0)}')
print(f'change_24h: {m.get(\"price_change_percentage_24h\",0)}')
print(f'twitter_followers: {c.get(\"twitter_followers\",0)}')
print(f'telegram_members: {c.get(\"telegram_channel_user_count\",0)}')
"
```

### Step 5 — Fetch Binance 24h Ticker

```bash
curl -sSL "https://api.binance.com/api/v3/ticker/24hr?symbol={SYMBOL}USDT" | python3 -c "
import sys,json
d=json.load(sys.stdin)
if 'lastPrice' in d:
  print(f'price: {d[\"lastPrice\"]}')
  print(f'volume: {d[\"quoteVolume\"]}')
  print(f'change: {d[\"priceChangePercent\"]}%')
"
```

### Step 6 — Score Each Project

| Dimension | /Max | Logic |
|-----------|------|-------|
| Binance Ecosystem Tie | /25 | Alpha=25, Launchpad=25, Launchpool=22, NewListing=20, DEX only=10 |
| Market Momentum | /20 | 24h change >20%→10, >5%→7, >0%→4. Volume >$50M→10, >$10M→7, >$1M→4 |
| On-chain Heat | /20 | BSC liquidity >$1M→10, >$200K→7, >$50K→4. Trending boost >0→up to 10 |
| Community Quality | /15 | Twitter >200K→8, >50K→6, >10K→4. Telegram >50K→5, >10K→3 |
| Fundamentals | /10 | Mcap >$100M→8, >$10M→6, CoinGecko listed→+2 |
| Time Window Edge | /10 | ≤7 days=10, ≤30d=7, ≤90d=4, >90d=1 |

**Rating:** ≥75 = 🟢 Top Pick | 50-74 = 🟡 Track | <50 = ⚪ Skip

### Step 7 — Output Report

Sort by total score descending, then output:

```
╔══════════════════════════════════════════════╗
║  🦅 ALPHA SCOUT — 机会简报                   ║
║  扫描时间: {time}  |  候选: {n} 个            ║
╠══════════════════════════════════════════════╣

  #1  {Name} ({SYMBOL})        {🟢/🟡} {score}/100
      来源: {source}  |  24h: {change}%
      市值: ${mcap}  |  流动性: ${liq}
      亮点: {highlight}
      风险: {risk}

  #2  ...

╠══════════════════════════════════════════════╣
  排名  代币        总分   币安  动量  链上  社区
  ─────────────────────────────────────────────
  1  🟢 XXX        82.3    25   15    17    10
  ...
╚══════════════════════════════════════════════╝
🦞 SiliconHunter × Alpha Scout
⚠️ 本报告仅供参考，不构成投资建议。
```

## Rules

1. This skill is **read-only** — never execute trades.
2. Wait 2 seconds between CoinGecko API calls (free tier = 30 req/min).
3. For Top Picks (≥75), include both highlights AND risks.
4. If Binance pages require login, skip and note in report.

## Failure Handling

- CoinGecko 429 → Skip remaining enrichments, note partial data
- Binance page not loadable → Fall back to DEXScreener trending only
- DEXScreener empty → Report "无 BSC 热门代币" and exit

## References

| Topic | Description | Link |
|-------|-------------|------|
| DEXScreener Boost API | BSC trending tokens (free) | https://docs.dexscreener.com |
| CoinGecko API | Fundamentals & community data (30 req/min free) | https://docs.coingecko.com |
| Binance Public API | 24h ticker (6000 weight/min, no key) | https://api.binance.com |
