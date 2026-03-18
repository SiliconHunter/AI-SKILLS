#!/usr/bin/env python3
"""
Rug Pull Hunter — analyze_contract.py
BNB Chain 代币安全分析引擎

API 来源（BscScan 已弃用，已迁移至以下替代方案）：
  合约源码 / Token Info  → Etherscan API V2  (chainid=56，与 BscScan 参数格式兼容)
  持仓人数 / 链上数据    → NodeReal MegaNode Enhanced API  (JSON-RPC 2.0)
  流动性 / 交易量        → DEXScreener API  (无需 Key)
  蜜罐 / 安全风险        → GoPlus Security API  (无需 Key)

用法:
    python analyze_contract.py --address 0x... [--etherscan-key KEY] [--meganode-key KEY]

API Key 申请（均有免费 Tier）：
    Etherscan V2 : https://etherscan.io/myapikey   (同一个 Key 兼容 BSC)
    MegaNode     : https://dashboard.nodereal.io   (免费 150 CUPS/s)

依赖:
    pip install requests colorama
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Optional
import requests
from datetime import datetime

# ─── 颜色输出 ───────────────────────────────────────────────────────────────
try:
    from colorama import Fore, Style, init
    init(autoreset=True)
    GREEN  = Fore.GREEN
    YELLOW = Fore.YELLOW
    RED    = Fore.RED
    CYAN   = Fore.CYAN
    BOLD   = Style.BRIGHT
    RESET  = Style.RESET_ALL
except ImportError:
    GREEN = YELLOW = RED = CYAN = BOLD = RESET = ""

# ─── 已知危险函数特征库 ──────────────────────────────────────────────────────
DANGER_PATTERNS = {
    "blacklist": {
        "keywords": ["blacklist", "addToBlacklist", "isBlacklisted", "_isBlacklisted"],
        "severity": "critical",
        "description": "合约包含黑名单功能，开发者可禁止特定地址卖出代币"
    },
    "unlimited_mint": {
        "keywords": ["function mint(", "function _mint("],
        "severity": "critical",
        "description": "合约可能存在无限增发功能，需检查 mint 权限控制"
    },
    "hidden_fee": {
        "keywords": ["setTaxFee", "setLiquidityFee", "_taxFee", "reflectionFromToken"],
        "severity": "warning",
        "description": "合约包含可调节的税费机制，开发者可随时修改手续费"
    },
    "trading_pause": {
        "keywords": ["pause(", "unpause(", "tradingOpen", "_tradingOpen"],
        "severity": "warning",
        "description": "合约可以暂停交易，开发者可随时停止所有买卖操作"
    },
    "proxy_upgrade": {
        "keywords": ["upgradeTo", "upgradeToAndCall", "delegatecall", "_implementation"],
        "severity": "critical",
        "description": "可升级代理合约，合约逻辑随时可被替换，历史安全审计失效"
    },
    "anti_whale_bypass": {
        "keywords": ["excludeFromFee", "isExcludedFromFee", "_isExcludedFromFee"],
        "severity": "warning",
        "description": "部分地址被排除在交易限制/费率之外，可能用于团队套利"
    },
    "owner_renounced": {
        "keywords": ["renounceOwnership"],
        "severity": "safe",
        "description": "合约包含所有权放弃功能（需确认已实际调用）"
    }
}

KNOWN_SAFE_CONTRACTS = {
    "0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82": "CAKE (PancakeSwap)",
    "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c": "WBNB (Wrapped BNB)",
    "0x55d398326f99059ff775485246999027b3197955": "USDT (Tether)",
    "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d": "USDC",
    "0x1d2f0da169ceb9fc7b3144628db156f3f6c60dbe": "XRP (BSC-Pegged)",
}

# ─── 数据结构 ────────────────────────────────────────────────────────────────
@dataclass
class RiskScore:
    contract_security: int = 0   # /30
    liquidity_health:  int = 0   # /25
    holder_distribution: int = 0 # /20
    project_transparency: int = 0 # /15
    community_authenticity: int = 0 # /10

    @property
    def total(self) -> int:
        return (self.contract_security + self.liquidity_health +
                self.holder_distribution + self.project_transparency +
                self.community_authenticity)

    @property
    def grade(self) -> str:
        t = self.total
        if t >= 80:
            return f"{GREEN}🟢 相对安全{RESET}"
        elif t >= 50:
            return f"{YELLOW}🟡 谨慎对待{RESET}"
        else:
            return f"{RED}🔴 高危预警{RESET}"

    @property
    def grade_plain(self) -> str:
        t = self.total
        if t >= 80:   return "🟢 相对安全"
        elif t >= 50: return "🟡 谨慎对待"
        else:         return "🔴 高危预警"

@dataclass
class ContractAnalysis:
    address: str
    token_name: str = "Unknown"
    token_symbol: str = "???"
    is_verified: bool = False
    owner_renounced: bool = False
    danger_functions: list = field(default_factory=list)
    liquidity_usd: float = 0.0
    liquidity_locked: bool = False
    volume_24h: float = 0.0
    price_usd: float = 0.0
    market_cap: float = 0.0
    top_holder_pct: float = 0.0
    top10_holders_pct: float = 0.0
    total_holders: int = 0
    buy_count_1h: int = 0
    sell_count_1h: int = 0
    goplus_flags: list = field(default_factory=list)
    risk_score: RiskScore = field(default_factory=RiskScore)
    warnings: list = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# ─── API 配置 ─────────────────────────────────────────────────────────────────

# Etherscan V2：BSC chainid = 56，REST 风格，与 BscScan 参数兼容
ETHERSCAN_V2_BASE = "https://api.etherscan.io/v2/api"
ETHERSCAN_BSC_CHAIN_ID = "56"

# NodeReal MegaNode：JSON-RPC 2.0，POST 请求
# API Key 在 URL 路径中：https://bsc-mainnet.nodereal.io/v1/{KEY}
MEGANODE_BASE = "https://bsc-mainnet.nodereal.io/v1"
MEGANODE_FREE_KEY = "64a9df0874fb4a93b9d0a849b6c6cefd"  # NodeReal 公开演示 Key（限速）

def _meganode_url(api_key: str) -> str:
    key = api_key or MEGANODE_FREE_KEY
    return f"{MEGANODE_BASE}/{key}"

def _meganode_rpc(url: str, method: str, params: list) -> dict:
    """发送 JSON-RPC 2.0 请求到 MegaNode"""
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
        if "result" in data:
            return data["result"]
    except Exception:
        pass
    return {}

# ─── API 调用函数 ─────────────────────────────────────────────────────────────

def fetch_contract_sourcecode(address: str, etherscan_key: str) -> dict:
    """
    合约源码 → Etherscan API V2 (chainid=56 = BSC)
    接口格式与原 BscScan 完全兼容，只换了 Base URL + chainid 参数。
    费率：免费 Key 5 calls/s，无 Key 限速更严。
    """
    print(f"{CYAN}[1/6] 从 Etherscan V2 获取合约源码（chainid=56）...{RESET}")
    params = {
        "chainid": ETHERSCAN_BSC_CHAIN_ID,
        "module":  "contract",
        "action":  "getsourcecode",
        "address": address,
        "apikey":  etherscan_key or "YourApiKeyToken",
    }
    try:
        resp = requests.get(ETHERSCAN_V2_BASE, params=params, timeout=10)
        data = resp.json()
        if data.get("status") == "1" and data.get("result"):
            return data["result"][0]
        else:
            print(f"{YELLOW}  ⚠ Etherscan V2 返回: {data.get('message', '未知错误')}{RESET}")
    except Exception as e:
        print(f"{YELLOW}  ⚠ Etherscan V2 请求失败: {e}{RESET}")
    return {}

def fetch_token_info(address: str, etherscan_key: str) -> dict:
    """
    代币基本信息（名称/符号/精度/总供应量）→ Etherscan API V2
    接口格式与原 BscScan tokeninfo 完全兼容。
    """
    params = {
        "chainid":         ETHERSCAN_BSC_CHAIN_ID,
        "module":          "token",
        "action":          "tokeninfo",
        "contractaddress": address,
        "apikey":          etherscan_key or "YourApiKeyToken",
    }
    try:
        resp = requests.get(ETHERSCAN_V2_BASE, params=params, timeout=10)
        data = resp.json()
        if data.get("status") == "1" and data.get("result"):
            result = data["result"]
            return result[0] if isinstance(result, list) else result
    except Exception:
        pass
    return {}

def fetch_holder_count_meganode(address: str, meganode_key: str) -> int:
    """
    持仓人数 → MegaNode Enhanced API  nr_getTokenHolderCount
    JSON-RPC 2.0，POST 请求。
    CU 成本：~16 CU/次；免费 Tier 150 CUPS/s，月限 ~300M CU。
    """
    print(f"{CYAN}[2/6] 从 MegaNode 获取持仓人数...{RESET}")
    url = _meganode_url(meganode_key)
    # params: [tokenAddress, blockNumber("latest")]
    result = _meganode_rpc(url, "nr_getTokenHolderCount", [address, "latest"])
    if result:
        try:
            return int(result, 16) if isinstance(result, str) else int(result)
        except Exception:
            pass
    return 0

def fetch_top_holders_meganode(address: str, meganode_key: str, count: int = 20) -> list:
    """
    Top 持仓地址 → MegaNode Enhanced API  nr_getTokenHolders
    返回：[{account, balance, percentageOfTotal}, ...]
    """
    url = _meganode_url(meganode_key)
    # params: [tokenAddress, blockNumber, page(hex), offset(hex)]
    page   = hex(1)
    offset = hex(count)
    result = _meganode_rpc(url, "nr_getTokenHolders", [address, "latest", page, offset])
    if isinstance(result, list):
        return result
    return []

def fetch_dexscreener(address: str) -> dict:
    """从 DEXScreener 获取流动性和交易数据（无需 API Key）"""
    print(f"{CYAN}[3/6] 从 DEXScreener 获取流动性数据...{RESET}")
    url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        pairs = data.get("pairs", [])
        # 过滤 BSC 网络，选择流动性最高的交易对
        bsc_pairs = [p for p in pairs if p.get("chainId") == "bsc"]
        if bsc_pairs:
            # 按流动性排序，取最大的
            bsc_pairs.sort(key=lambda x: float(x.get("liquidity", {}).get("usd", 0) or 0), reverse=True)
            return bsc_pairs[0]
    except Exception as e:
        print(f"{YELLOW}  ⚠ DEXScreener 请求失败: {e}{RESET}")
    return {}

def fetch_goplus_security(address: str) -> dict:
    """从 GoPlus Security API 获取已知风险标记（无需 API Key）"""
    print(f"{CYAN}[4/6] 查询 GoPlus 安全数据库...{RESET}")
    url = f"https://api.gopluslabs.io/api/v1/token_security/56"  # 56 = BSC Chain ID
    params = {"contract_addresses": address}
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data.get("code") == 1:
            result = data.get("result", {})
            return result.get(address.lower(), {})
    except Exception as e:
        print(f"{YELLOW}  ⚠ GoPlus API 请求失败，跳过: {e}{RESET}")
    return {}

def scan_source_code(source_code: str) -> list:
    """扫描源码中的危险函数模式"""
    print(f"{CYAN}[5/6] 扫描合约源码危险特征...{RESET}")
    found = []
    if not source_code:
        return found
    for pattern_name, pattern_info in DANGER_PATTERNS.items():
        for keyword in pattern_info["keywords"]:
            if keyword.lower() in source_code.lower():
                found.append({
                    "pattern": pattern_name,
                    "keyword": keyword,
                    "severity": pattern_info["severity"],
                    "description": pattern_info["description"]
                })
                break  # 每个模式只记录一次
    return found

# ─── 评分引擎 ────────────────────────────────────────────────────────────────

def calculate_scores(analysis: ContractAnalysis, goplus: dict) -> ContractAnalysis:
    """根据所有收集到的数据计算风险评分"""
    print(f"{CYAN}[6/6] 计算综合风险评分...{RESET}")
    score = RiskScore()

    # ── 1. 合约安全 (满分 30) ──
    contract_score = 30
    for danger in analysis.danger_functions:
        if danger["severity"] == "critical":
            contract_score -= 15
            analysis.warnings.append(f"❌ 危险函数: {danger['description']}")
        elif danger["severity"] == "warning":
            contract_score -= 7
            analysis.warnings.append(f"⚠️  风险特征: {danger['description']}")
    if not analysis.is_verified:
        contract_score -= 20
        analysis.warnings.append("❌ 合约源码未验证，无法审计代码逻辑")
    # GoPlus 附加检查
    if goplus.get("is_honeypot") == "1":
        contract_score -= 20
        analysis.warnings.append("❌ GoPlus: 检测到蜜罐合约，无法卖出！")
    if goplus.get("cannot_sell_all") == "1":
        contract_score -= 15
        analysis.warnings.append("❌ GoPlus: 无法卖出全部代币")
    if goplus.get("is_mintable") == "1":
        contract_score -= 10
        analysis.warnings.append("⚠️  GoPlus: 合约存在增发功能")
    if goplus.get("owner_change_balance") == "1":
        contract_score -= 15
        analysis.warnings.append("❌ GoPlus: 所有者可以修改持仓余额")
    score.contract_security = max(0, contract_score)

    # ── 2. 流动性健康度 (满分 25) ──
    liq = analysis.liquidity_usd
    if liq >= 500_000:
        score.liquidity_health = 25
    elif liq >= 100_000:
        score.liquidity_health = 20
    elif liq >= 50_000:
        score.liquidity_health = 15
    elif liq >= 10_000:
        score.liquidity_health = 8
    else:
        score.liquidity_health = 2
        analysis.warnings.append(f"❌ 流动性过低 (${liq:,.0f})，大额交易将面临极高滑点")
    if analysis.liquidity_locked:
        score.liquidity_health = min(25, score.liquidity_health + 5)
    else:
        score.liquidity_health = max(0, score.liquidity_health - 5)
        analysis.warnings.append("⚠️  流动性未锁定，开发者可随时撤池")
    # 买卖比异常（pump and dump 信号）
    total_trades = analysis.buy_count_1h + analysis.sell_count_1h
    if total_trades > 0:
        buy_ratio = analysis.buy_count_1h / total_trades
        if buy_ratio > 0.85:
            analysis.warnings.append(f"⚠️  买卖比异常 ({buy_ratio:.0%} 为买入)，可能有人为拉盘")

    # ── 3. 持仓集中度 (满分 20) ──
    top10 = analysis.top10_holders_pct
    top1  = analysis.top_holder_pct
    if top10 <= 20:
        score.holder_distribution = 20
    elif top10 <= 35:
        score.holder_distribution = 15
    elif top10 <= 50:
        score.holder_distribution = 10
    else:
        score.holder_distribution = 3
        analysis.warnings.append(f"❌ 持仓高度集中，Top10 持有 {top10:.1f}%")
    if top1 > 15:
        score.holder_distribution = max(0, score.holder_distribution - 5)
        analysis.warnings.append(f"⚠️  单一地址持有 {top1:.1f}%，鲸鱼风险")

    # ── 4. 项目透明度 (满分 15) ──
    transparency_score = 0
    if analysis.is_verified:
        transparency_score += 8
    if analysis.owner_renounced:
        transparency_score += 4
    if goplus.get("is_open_source") == "1":
        transparency_score += 3
    score.project_transparency = transparency_score

    # ── 5. 社区真实性 (满分 10，基础分，视频演示中通过浏览器实时获取) ──
    score.community_authenticity = 6  # 默认中性分，由 Agent 浏览器分析补充

    analysis.risk_score = score
    return analysis

# ─── 报告生成 ────────────────────────────────────────────────────────────────

def generate_report(analysis: ContractAnalysis) -> str:
    score = analysis.risk_score

    # 信号图标
    def sig(val, good_thresh, warn_thresh):
        if val >= good_thresh: return "✅"
        if val >= warn_thresh: return "⚠️ "
        return "❌"

    contract_sig  = sig(score.contract_security,  24, 15)
    liq_sig       = sig(score.liquidity_health,    20, 10)
    holder_sig    = sig(score.holder_distribution, 16,  8)
    transp_sig    = sig(score.project_transparency, 12,  6)
    community_sig = sig(score.community_authenticity, 8, 4)

    report = f"""
{'═' * 56}
🔍 RUG PULL HUNTER — 安全分析报告
{'═' * 56}
代币地址  : {analysis.address}
代币名称  : {analysis.token_name} ({analysis.token_symbol})
分析时间  : {analysis.timestamp}
{'─' * 56}
🚦 综合风险评级 : {score.grade_plain}
   综合得分     : {score.total}/100
{'─' * 56}
📊 各维度得分详情:

  {contract_sig}  合约安全       [{score.contract_security:2d}/30]
  {liq_sig}  流动性健康度   [{score.liquidity_health:2d}/25]
  {holder_sig}  持仓分布       [{score.holder_distribution:2d}/20]
  {transp_sig}  项目透明度     [{score.project_transparency:2d}/15]
  {community_sig}  社区真实性     [{score.community_authenticity:2d}/10]
{'─' * 56}
💰 市场数据:
  价格          : ${analysis.price_usd:.8f}
  市值          : ${analysis.market_cap:,.0f}
  流动性池      : ${analysis.liquidity_usd:,.0f}  {'✅ 已锁定' if analysis.liquidity_locked else '❌ 未锁定'}
  24h 交易量    : ${analysis.volume_24h:,.0f}
  1h 买/卖单数  : {analysis.buy_count_1h} / {analysis.sell_count_1h}
  持有人数量    : {analysis.total_holders:,}
  Top10 持仓占比: {analysis.top10_holders_pct:.1f}%
{'─' * 56}"""

    if analysis.warnings:
        report += "\n⚠️  风险预警清单:\n"
        for w in analysis.warnings:
            report += f"   {w}\n"
    else:
        report += "\n✅ 未发现明显风险点\n"

    report += f"""{'─' * 56}
💡 操作建议:"""

    total = score.total
    if total >= 80:
        report += """
  ✅ 该代币通过了主要安全检测，风险相对较低。
  • 仍建议小额分批建仓，DYOR（自主研究）
  • 定期检查合约状态和流动性变化
  • 设置合理止损以规避黑天鹅风险"""
    elif total >= 50:
        report += """
  ⚠️  存在若干风险信号，建议：
  • 仅用可以承受损失的资金参与
  • 详细阅读项目白皮书和审计报告
  • 密切关注流动性和大户动向"""
    else:
        report += """
  ❌ 检测到多项高危特征，强烈建议：
  • 暂勿买入或立即止损离场
  • 不要因 FOMO 忽视安全风险
  • 将此合约信息分享给社区以保护他人"""

    report += f"""
{'═' * 56}
🦞 Rug Pull Hunter × OpenClaw × Binance
⚠️  本报告仅供参考，不构成投资建议。DYOR!
{'═' * 56}
"""
    return report

# ─── 主程序 ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Rug Pull Hunter — BNB Chain 代币安全分析")
    parser.add_argument("--address",       required=True, help="代币合约地址 (0x...)")
    parser.add_argument("--etherscan-key", default="",    help="Etherscan API Key（免费申请：etherscan.io/myapikey，兼容 BSC）")
    parser.add_argument("--meganode-key",  default="",    help="NodeReal MegaNode API Key（免费申请：dashboard.nodereal.io）")
    parser.add_argument("--json",          action="store_true", help="JSON 格式输出（供 OpenClaw Agent 解析）")
    args = parser.parse_args()

    address = args.address.lower().strip()

    # 检查是否为已知安全合约
    if address in KNOWN_SAFE_CONTRACTS:
        print(f"{GREEN}✅ 已知安全合约: {KNOWN_SAFE_CONTRACTS[address]}{RESET}")

    analysis = ContractAnalysis(address=address)

    # ── 数据收集 ──

    # 1. Etherscan V2 合约源码（替代原 BscScan getsourcecode）
    contract_data = fetch_contract_sourcecode(address, args.etherscan_key)
    if contract_data:
        analysis.token_name      = contract_data.get("ContractName", "Unknown")
        analysis.is_verified     = contract_data.get("ABI", "") != "Contract source code not verified"
        source_code              = contract_data.get("SourceCode", "")
        analysis.owner_renounced = "renounceOwnership" in source_code
        if analysis.is_verified:
            analysis.danger_functions = scan_source_code(source_code)

    # 2. Etherscan V2 代币基本信息（替代原 BscScan tokeninfo）
    token_info = fetch_token_info(address, args.etherscan_key)
    if token_info:
        analysis.token_name   = token_info.get("tokenName",  analysis.token_name)
        analysis.token_symbol = token_info.get("symbol",     "???")
        # Etherscan V2 没有 holdersCount，改用 MegaNode 获取

    # 3. MegaNode Enhanced API 持仓人数 + Top Holders（替代原 BscScan tokenholderlist）
    holder_count = fetch_holder_count_meganode(address, args.meganode_key)
    if holder_count:
        analysis.total_holders = holder_count

    top_holders = fetch_top_holders_meganode(address, args.meganode_key, count=20)
    if top_holders:
        # 计算持仓集中度
        # MegaNode 返回 percentageOfTotal 字段（字符串，如 "12.34"）
        pcts = []
        for h in top_holders[:10]:
            pct_str = h.get("percentageOfTotal", h.get("percentage", "0"))
            try:
                pcts.append(float(pct_str))
            except Exception:
                pass
        if pcts:
            analysis.top_holder_pct    = pcts[0]
            analysis.top10_holders_pct = sum(pcts)

    # 4. DEXScreener 流动性（无需 Key，保持不变）
    dex_data = fetch_dexscreener(address)
    if dex_data:
        liq = dex_data.get("liquidity", {})
        analysis.liquidity_usd    = float(liq.get("usd", 0) or 0)
        analysis.liquidity_locked = dex_data.get("info", {}).get("liquidityLocked", False)
        analysis.price_usd        = float(dex_data.get("priceUsd", 0) or 0)
        analysis.market_cap       = float(dex_data.get("marketCap", 0) or 0)
        volume = dex_data.get("volume", {})
        analysis.volume_24h       = float(volume.get("h24", 0) or 0)
        txns = dex_data.get("txns", {}).get("h1", {})
        analysis.buy_count_1h     = int(txns.get("buys", 0) or 0)
        analysis.sell_count_1h    = int(txns.get("sells", 0) or 0)
        if analysis.token_name == "Unknown":
            base = dex_data.get("baseToken", {})
            analysis.token_name   = base.get("name", "Unknown")
            analysis.token_symbol = base.get("symbol", "???")

    # 5. GoPlus Security（无需 Key，保持不变）
    goplus = fetch_goplus_security(address)

    # ── 评分计算 ──
    analysis = calculate_scores(analysis, goplus)

    # ── 输出 ──
    if args.json:
        output = {
            "address": analysis.address,
            "token_name": analysis.token_name,
            "token_symbol": analysis.token_symbol,
            "is_verified": analysis.is_verified,
            "owner_renounced": analysis.owner_renounced,
            "liquidity_usd": analysis.liquidity_usd,
            "liquidity_locked": analysis.liquidity_locked,
            "volume_24h": analysis.volume_24h,
            "price_usd": analysis.price_usd,
            "market_cap": analysis.market_cap,
            "top_holder_pct": analysis.top_holder_pct,
            "top10_holders_pct": analysis.top10_holders_pct,
            "total_holders": analysis.total_holders,
            "danger_functions": analysis.danger_functions,
            "warnings": analysis.warnings,
            "api_sources": {
                "contract_source": "Etherscan API V2 (chainid=56)",
                "token_info":      "Etherscan API V2 (chainid=56)",
                "holder_data":     "NodeReal MegaNode Enhanced API (nr_getTokenHolderCount / nr_getTokenHolders)",
                "liquidity":       "DEXScreener API (no key)",
                "security_scan":   "GoPlus Security API (no key)"
            },
            "scores": {
                "contract_security":    analysis.risk_score.contract_security,
                "liquidity_health":     analysis.risk_score.liquidity_health,
                "holder_distribution":  analysis.risk_score.holder_distribution,
                "project_transparency": analysis.risk_score.project_transparency,
                "community_authenticity": analysis.risk_score.community_authenticity,
                "total": analysis.risk_score.total,
                "grade": analysis.risk_score.grade_plain
            },
            "goplus_flags": [k for k, v in goplus.items() if v == "1"]
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        report = generate_report(analysis)
        print(report)

    return 0 if analysis.risk_score.total >= 80 else (1 if analysis.risk_score.total >= 50 else 2)


if __name__ == "__main__":
    sys.exit(main())
