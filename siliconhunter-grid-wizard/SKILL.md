---
name: siliconhunter-grid-wizard
description: AI grid trading parameter wizard — user describes intent in natural language, agent calculates optimal grid params from Binance historical data, then auto-fills the Binance grid trading UI.
metadata:
  author: SiliconHunter
  version: "2026.03.18"
allowed-tools: Bash(python3:*), Bash(curl:*), Bash(browser-use:*)
---

# Grid Wizard

> "龙虾主人，告诉我你的想法，我来替你把网格调到最优。"

## When to Use

- User wants to set up grid trading on Binance, e.g. "帮我设置 BNB 的网格"
- User describes trading intent: "我想用 500 USDT 做稳健网格"
- User asks "网格参数怎么设？" or wants parameter recommendations
- User wants to compare grid strategies (conservative / moderate / aggressive)

## Do Not Use When

- User wants to trade spot or futures manually (not grid)
- User wants a fully automated bot that clicks "Create" without confirmation

## Standard Workflow

### Step 1 — Parse User Intent

Extract from natural language:
- **symbol**: trading pair (default: append USDT), e.g. "BNB" → "BNBUSDT"
- **investment**: amount in USDT
- **risk_level**: "conservative" / "moderate" (default) / "aggressive"
- **grid_type**: "geometric" (default) / "arithmetic"

If any critical parameter (symbol or investment) is missing, ask user.

### Step 2 — Fetch Historical Kline Data from Binance

Fetch 90-day daily klines (public API, no key needed):

```bash
curl -sSL "https://api.binance.com/api/v3/klines?symbol={SYMBOL}&interval=1d&limit=90" | python3 -c "
import sys,json,math
klines=json.load(sys.stdin)
highs=[float(k[2]) for k in klines]
lows=[float(k[3]) for k in klines]
closes=[float(k[4]) for k in klines]

current=closes[-1]
high_30d=max(highs[-30:])
low_30d=min(lows[-30:])

# ATR(14)
trs=[]
for i in range(1,len(highs)):
  tr=max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
  trs.append(tr)
atr=sum(trs[-14:])/14

# Volatility
rets=[(closes[i]-closes[i-1])/closes[i-1] for i in range(1,min(len(closes),31))]
mean_r=sum(rets)/len(rets)
var_r=sum((r-mean_r)**2 for r in rets)/len(rets)
annual_vol=math.sqrt(var_r)*math.sqrt(365)*100

print(f'current_price: {current:.4f}')
print(f'high_30d: {high_30d:.4f}')
print(f'low_30d: {low_30d:.4f}')
print(f'atr_14: {atr:.4f}')
print(f'atr_pct: {atr/current*100:.2f}')
print(f'annual_volatility: {annual_vol:.1f}')
"
```

### Step 3 — Calculate Optimal Grid Parameters

Use this logic:

```
Risk Profiles:
  conservative: atr_mult=3.0, grids=5-8
  moderate:     atr_mult=5.0, grids=10-15
  aggressive:   atr_mult=8.0, grids=20-50

lower_price = current × (1 - atr_pct × atr_mult × 0.6)
upper_price = current × (1 + atr_pct × atr_mult × 0.4)

Ensure upper/lower ratio ≥ 1.10 (minimum 10% range)

For geometric grid:
  spacing = (upper/lower)^(1/grid_count) - 1
  profit_per_grid = spacing - 0.001  (subtract 0.1% fee)

Monthly return estimate:
  daily_volatility = annual_volatility / sqrt(365)
  triggers_per_day = (daily_volatility / 2) / spacing
  monthly_return = triggers × profit_per_grid × 30

Max drawdown = (current - lower) / current × 50%
```

If user says "对比三种策略", calculate all three and present comparison table.

### Step 4 — Present Parameter Report

```
═══════════════════════════════════════
🧙 GRID WIZARD — 网格参数报告
═══════════════════════════════════════
交易对: {SYMBOL}  |  策略: {risk_level}
投资额: {amount} USDT  |  网格类型: {type}

📐 推荐参数
  价格区间  : {lower} ~ {upper}
  区间宽度  : {width}%
  网格数量  : {count} 格
  每格间距  : {spacing}%
  每格资金  : {per_grid} USDT
  每格净利  : {profit}%

📊 历史分析（近30日）
  价格区间  : {hist_low} ~ {hist_high}
  ATR(14)  : {atr} ({atr_pct}%)
  方向建议  : {direction}

💰 收益预测
  悲观: {low}%/月 | 基准: {base}%/月 | 乐观: {high}%/月

⚠️ 最大回撤: {drawdown}% | 建议止损: {stop_loss}
═══════════════════════════════════════
🦞 SiliconHunter × Grid Wizard
```

### Step 5 — Auto-fill Binance Grid Trading Page (Browser)

Open the Binance grid trading page and fill parameters:

```bash
browser-use open "https://www.binance.com/zh-CN/grid-trading"
browser-use state
```

Then select trading pair, switch to Custom mode, and fill each field:

```bash
browser-use input {search_box_index} "{SYMBOL_BASE}"
browser-use click {pair_result_index}
browser-use state
browser-use click {custom_tab_index}
browser-use input {lower_price_index} "{lower_price}"
browser-use input {upper_price_index} "{upper_price}"
browser-use input {grid_count_index} "{grid_count}"
browser-use input {investment_index} "{investment}"
browser-use screenshot grid_params_filled.png
```

Send screenshot to user and say: **"参数已填入，请核对后点击「创建网格」确认。"**

**NEVER click the Create/Submit button.** Always wait for user confirmation.

## Rules

1. **Never click "创建网格"** — only fill parameters. Final execution is the user's decision.
2. Always include risk warnings: max drawdown, stop-loss, and the note that grid trading works best in ranging markets.
3. If Binance page requires login, present parameters as text only and instruct user to enter manually.
4. Investment should not exceed 20-30% of total portfolio.

## Failure Handling

- Binance kline API error → Ask user for the current price range manually
- Browser cannot open Binance → Present parameters as text report only
- Trading pair not found → Suggest alternatives (e.g., try XYZBNB if XYZUSDT fails)

## References

| Topic | Description | Link |
|-------|-------------|------|
| Binance Public API | Klines endpoint, no key needed | https://api.binance.com |
| Binance Grid Trading | Official grid trading interface | https://www.binance.com/en/grid-trading |
| ATR Indicator | Average True Range calculation | https://www.investopedia.com/terms/a/atr.asp |
