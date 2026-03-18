# 🦞 SiliconHunter Skills — 币安 AI Agent 套件

> **"龙虾主人，三大 AI Agent 为您守护资产、发现机会、优化收益。"**

币安 AI 创意大赛参赛项目 | **#AI建设加密**

[English Documentation](./README.md)

---

## 安装

```bash
# 使用 Bun
bunx skills add SiliconHunter/AI-SKILLS

# 使用 NPM
npx skills add SiliconHunter/AI-SKILLS
```

如果你的 AI 助手支持技能安装，也可以直接发送：

> Install SiliconHunter skills at github.com/SiliconHunter/AI-SKILLS

**说明：** `npx skills` 是 [Vercel 开源的 Agent Skills CLI](https://github.com/vercel-labs/skills)，直接从 GitHub 拉取，无需发布到任何 registry。

---

## 技能列表

### 🔍 siliconhunter-rug-pull-hunter — 链上安全侦探

BNB Chain 代币安全扫描器 —— 输入合约地址，获得红🔴/黄🟡/绿🟢风险报告，涵盖合约代码分析、流动性健康度、持仓集中度和社区舆情。

**触发词：** "检查合约 0x..." · "这个币安不安全？" · "rug check 0x..."

### 🦅 siliconhunter-alpha-scout — 币安早鸟猎手

扫描币安 Alpha、新币上线公告、BNB Chain DEX 热度榜，从 6 个维度交叉评分，推送排行榜式的机会简报。

**触发词：** "有什么新机会？" · "Alpha 扫描" · "今天币安有什么好项目？"

### 🧙 siliconhunter-grid-wizard — AI 网格交易向导

用自然语言描述交易意图，Agent 自动从币安历史数据计算最优网格参数，并自动填入币安网格交易界面。AI 做数学，你做决策。

**触发词：** "帮我设置网格" · "我想用 500 USDT 做 BNB 网格" · "对比三种策略"

---

## 工作原理

三个技能完全通过 OpenClaw 的浏览器自动化运行 —— 不需要 Python 环境、不需要 API Key、不需要服务器。Agent 读取 SKILL.md 指令，自动访问公开网站（Etherscan、DEXScreener、Binance、CoinGecko、GoPlus），用 LLM 分析页面内容，生成结构化报告。

每个 `scripts/` 目录中包含可选的 Python 脚本，供需要独立命令行工具的用户使用。

---

## 数据来源

| 数据源 | 使用者 | 需要 API Key |
|--------|--------|-------------|
| Etherscan API V2 (chainid=56) | Rug Pull Hunter | 可选（免费） |
| NodeReal MegaNode | Rug Pull Hunter | 可选（免费） |
| DEXScreener | Rug Pull Hunter, Alpha Scout | ❌ 不需要 |
| GoPlus Security | Rug Pull Hunter | ❌ 不需要 |
| CoinGecko | Alpha Scout | 可选（免费） |
| Binance Public API | Grid Wizard, Alpha Scout | ❌ 不需要 |
| Binance 网页端 | 所有技能（浏览器） | ❌ 不需要 |

---

## 项目结构

```
SiliconHunter/AI-SKILLS/
├── README.md          ← 英文文档
├── README_ZH.md       ← 中文文档（本文件）
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

## 许可证

MIT

---

*🦞 SiliconHunter × OpenClaw × Binance | #AI建设加密*
