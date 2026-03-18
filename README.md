# 🦞 SiliconHunter Skills — Binance AI Agent Suite

> **"龙虾主人，三大 AI Agent 为您守护资产、发现机会、优化收益。"**

币安 AI 创意大赛参赛项目 | **#AI BUILD WITH BINANCE**

---

## Installation

```bash
# Using Bun
bunx skills add SiliconHunter/skills

# Using NPM
npx skills add SiliconHunter/skills
```

If your AI assistant supports skill installation, you can also send:

> Install SiliconHunter skills at github.com/SiliconHunter/skills

---

## Skills

### 🔍 siliconhunter-rug-pull-hunter

BNB Chain token security scanner — input a contract address, get a red/yellow/green risk report with contract code analysis, liquidity health, holder concentration, and social sentiment.

**Trigger:** "检查合约 0x..." · "这个币安不安全？" · "rug check"

### 🦅 siliconhunter-alpha-scout

Scan Binance Alpha, new listings, and BNB Chain DEX trending tokens. Score each project across 6 dimensions and push a ranked opportunity brief.

**Trigger:** "有什么新机会？" · "Alpha 扫描" · "今天币安有什么好项目？"

### 🧙 siliconhunter-grid-wizard

AI grid trading parameter wizard — user describes intent in natural language, agent calculates optimal grid params from Binance historical data, then auto-fills the Binance grid trading UI.

**Trigger:** "帮我设置网格" · "我想用 500 USDT 做 BNB 网格" · "对比三种策略"

---

## How It Works

All three skills run **entirely through OpenClaw's browser automation** — no Python, no API keys, no server required. The agent reads SKILL.md instructions, navigates to public websites (Etherscan, DEXScreener, Binance, CoinGecko, GoPlus), analyzes the page content with its LLM brain, and generates structured reports.

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
SiliconHunter/skills/
├── README.md
├── AGENTS.md
├── CLAUDE.md → AGENTS.md
├── LICENSE
└── skills/
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
