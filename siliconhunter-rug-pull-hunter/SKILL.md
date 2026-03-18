---
name: siliconhunter-rug-pull-hunter
description: BNB Chain token security scanner — input a contract address, get a red/yellow/green risk report with contract code analysis, liquidity health, holder concentration, and social sentiment.
metadata:
  author: SiliconHunter
  version: "2026.03.18"
allowed-tools: Bash(python3:*), Bash(curl:*), Bash(browser-use:*)
---

# Rug Pull Hunter

> "龙虾主人，我将帮你识破每一个链上骗局。"

## When to Use

- User asks to check if a BNB Chain token is safe, e.g. "检查合约 0x..."
- User wants to know whether a project is a rug pull, scam, or honeypot
- User provides a BSC contract address and wants a risk assessment

## Do Not Use When

- The token is NOT on BNB Chain (BSC) — this skill is BSC-specific
- User only wants price or market data without security analysis

## Standard Workflow

### Step 1 — Parse Input

Extract the contract address from user message. Must be `0x` followed by 40 hex characters.
If user gives a token name instead of address, search CoinGecko:

```bash
curl -sSL "https://api.coingecko.com/api/v3/search?query={TOKEN_NAME}" | python3 -c "
import sys,json
data=json.load(sys.stdin)
for c in data.get('coins',[]):
  for p in c.get('platforms',{}).items():
    if 'binance' in p[0].lower():
      print(p[1]); break
"
```

### Step 2 — Fetch GoPlus Security Data

This is the **primary data source**. GoPlus provides honeypot detection, tax rates, ownership status, and all critical security flags in one call.

```bash
curl -sSL "https://api.gopluslabs.io/api/v1/token_security/56?contract_addresses={ADDRESS}" | python3 -c "
import sys,json
data=json.load(sys.stdin)
result=data.get('result',{})
token=result.get('{ADDRESS_LOWER}',{})
for k,v in sorted(token.items()):
  print(f'{k}: {v}')
"
```

Key fields to check:
- `is_honeypot`: "1" = 🔴 CRITICAL — users cannot sell
- `is_open_source`: "0" = 🔴 source code not verified
- `is_mintable`: "1" = 🟡 can mint new tokens
- `owner_change_balance`: "1" = 🔴 owner can modify balances
- `hidden_owner`: "1" = 🔴 hidden owner exists
- `is_proxy`: "1" = 🟡 upgradeable proxy contract
- `transfer_pausable`: "1" = 🟡 trading can be paused
- `is_blacklisted`: "1" = 🟡 blacklist function exists
- `slippage_modifiable`: "1" = 🟡 tax/slippage can be changed
- `can_take_back_ownership`: "1" = 🔴 ownership reclaimable
- `buy_tax` / `sell_tax`: >0.10 = 🔴 abnormal tax (>10%)
- `holder_count`: total holders
- `owner_address`: check if `0x000...000` or `0x000...dead` (renounced)

### Step 3 — Fetch DEXScreener Liquidity Data

```bash
curl -sSL "https://api.dexscreener.com/latest/dex/tokens/{ADDRESS}" | python3 -c "
import sys,json
data=json.load(sys.stdin)
pairs=[p for p in data.get('pairs',[]) if p.get('chainId')=='bsc']
pairs.sort(key=lambda x:float(x.get('liquidity',{}).get('usd',0) or 0),reverse=True)
if pairs:
  p=pairs[0]
  print(f'pair: {p[\"baseToken\"][\"symbol\"]}/{p[\"quoteToken\"][\"symbol\"]}')
  print(f'price: \${float(p.get(\"priceUsd\",0)):.8f}')
  print(f'liquidity: \${float(p.get(\"liquidity\",{}).get(\"usd\",0)):,.0f}')
  print(f'volume_24h: \${float(p.get(\"volume\",{}).get(\"h24\",0)):,.0f}')
  print(f'mcap: \${float(p.get(\"marketCap\",0) or p.get(\"fdv\",0)):,.0f}')
  txns=p.get('txns',{}).get('h1',{})
  print(f'1h_buys: {txns.get(\"buys\",0)}')
  print(f'1h_sells: {txns.get(\"sells\",0)}')
else:
  print('NO_BSC_PAIR_FOUND')
"
```

### Step 4 — Score and Generate Report

Apply this scoring framework:

**Contract Security (/30):** Start at 30. is_honeypot=-25, owner_change_balance=-15, hidden_owner=-10, can_take_back_ownership=-10, not open_source=-20, is_proxy=-10, transfer_pausable=-7, is_blacklisted=-7, slippage_modifiable=-7, is_mintable=-10, high_tax(>10%)=-10.

**Liquidity Health (/25):** ≥$500K=25, ≥$100K=20, ≥$50K=15, ≥$10K=8, <$10K=2, $0=0. Sell ratio >80% in 1h → -5.

**Holder Distribution (/20):** ≥10K holders=20, ≥5K=16, ≥1K=12, ≥100=8, <100=4, 0=2.

**Project Transparency (/15):** Open source +8, ownership renounced +4, open source bonus +3.

**Community (/10):** Baseline 6.

**Total = sum of 5 dimensions. ≥80 = 🟢 | 50-79 = 🟡 | <50 = 🔴**

Output the report in this format:

```
════════════════════════════════════════
🔍 RUG PULL HUNTER 安全报告
════════════════════════════════════════
代币：{name} | 网络：BSC | 时间：{now}

🚦 综合评级：{🟢/🟡/🔴} — {score}/100

  合约安全    [{n}/30] {findings}
  流动性      [{n}/25] {findings}
  持仓分布    [{n}/20] {findings}
  项目透明度  [{n}/15] {findings}
  社区真实性  [{n}/10] {findings}

⚠️ 风险点：
  • {each warning}

💡 建议：{advice based on grade}

📎 验证: BscScan | DEXScreener | GoPlus
════════════════════════════════════════
🦞 SiliconHunter × Rug Pull Hunter
⚠️ 本报告仅供参考，不构成投资建议。DYOR!
```

### Step 5 — (Optional) Browser Visual Verification

For high-score projects (≥70), optionally open browser for screenshots:

```bash
browser-use open "https://dexscreener.com/bsc/{ADDRESS}"
browser-use screenshot dexscreener.png
browser-use open "https://bscscan.com/address/{ADDRESS}"
browser-use screenshot bscscan.png
```

## Rules

1. This skill is **read-only** — never execute any transaction or approve any contract interaction.
2. Always include the disclaimer: "本报告仅供参考，不构成投资建议。DYOR!"
3. If GoPlus returns empty, note "GoPlus 无此代币数据" and score conservatively.
4. If DEXScreener returns no pair, note "BSC 无交易对" and set liquidity score to 0.

## Failure Handling

- GoPlus API 返回空 → 合约安全和持仓分布维度给最低分，报告注明数据不完整
- DEXScreener 无数据 → 流动性得分为 0，注明"无 DEX 交易对"
- curl 失败 → 重试一次，仍失败则跳过该数据源

## References

| Topic | Description | Link |
|-------|-------------|------|
| GoPlus Security API | Honeypot, tax, ownership flags (free, no key) | https://docs.gopluslabs.io |
| DEXScreener API | Liquidity, volume, price (free, no key) | https://docs.dexscreener.com |
| BscScan | BSC blockchain explorer | https://bscscan.com |
