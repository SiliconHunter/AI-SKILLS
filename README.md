# 🦞 SiliconHunter Skills — Binance AI Agent Suite

> **"Master Lobster, three AI Agents at your service — protecting assets, discovering opportunities, optimizing returns."**

Binance AI Contest Entry | **#AI BUILD WITH BINANCE**

[中文文档 / Chinese Documentation](./README_ZH.md)

---

## Installation

```bash
# Using Bun
bunx skills add SiliconHunter/AI-SKILLS

# Using NPM
npx skills add SiliconHunter/AI-SKILLS
```

If your AI assistant supports skill installation, you can also send:

> Install SiliconHunter skills at github.com/SiliconHunter/AI-SKILLS

**Note:** `npx skills` is the [Vercel open agent skills CLI](https://github.com/vercel-labs/skills) — it pulls directly from GitHub, no registry required.

---

## Skills

### 🔍 siliconhunter-rug-pull-hunter

BNB Chain token security scanner — input a contract address, get a red/yellow/green risk report with contract code analysis, liquidity health, holder concentration, and social sentiment.

**Trigger:** "rug check 0x..." · "Is this token safe?" · "检查合约 0x..."

### 🦅 siliconhunter-alpha-scout

Scan Binance Alpha, new listings, and BNB Chain DEX trending tokens. Score each project across 6 dimensions and push a ranked opportunity brief.

**Trigger:** "scan alpha" · "any new opportunities?" · "有什么新机会？"

### 🧙 siliconhunter-grid-wizard

AI grid trading parameter wizard — describe your intent in natural language, agent calculates optimal grid params from Binance historical data, then auto-fills the Binance grid trading UI.

**Trigger:** "set up a BNB grid with 500 USDT" · "compare 3 grid strategies" · "帮我设置网格"

---

## How It Works

All three skills run entirely through OpenClaw's browser automation — no Python, no API keys, no server required. The agent reads SKILL.md instructions, navigates to public websites (Etherscan, DEXScreener, Binance, CoinGecko, GoPlus), analyzes the page content with its LLM brain, and generates structured reports.

Optional Python scripts are included in each `scripts/` directory for users who want standalone CLI tools.

---

## Data Sources

| Source | Used By | API Key Required |
|--------|---------|-----------------|
| Etherscan API V2 (chainid=56) | Rug Pull Hunter | Optional (free) |
| NodeReal MegaNode | Rug Pull Hunter | Optional (free) |
| DEXScreener | Rug Pull Hunter, Alpha Scout | ❌ No |
| GoPlus Security | Rug Pull Hunter | ❌ No |
| CoinGecko | Alpha Scout | Optional (free) |
| Binance Public API | Grid Wizard, Alpha Scout | ❌ No |
| Binance Website | All skills (browser) | ❌ No |

---

## Project Structure

```
SiliconHunter/AI-SKILLS/
├── README.md
├── README_ZH.md
├── LICENSE
├── siliconhunter-rug-pull-hunter/
│   ├── SKILL.md
│   └── scripts/
│       └── analyze_contract.py
├── siliconhunter-alpha-scout/
│   ├── SKILL.md
│   └── scripts/
│       └── opportunity_scorer.py
└── siliconhunter-grid-wizard/
    ├── SKILL.md
    └── scripts/
        └── grid_calculator.py
```

---

## License

MIT

---

*🦞 SiliconHunter × OpenClaw × Binance | #AI BUILD WITH BINANCE*
