#!/usr/bin/env python3
"""
Alpha Scout — opportunity_scorer.py
币安 Alpha 项目机会综合评分引擎

用法:
    python opportunity_scorer.py [--top 5] [--min-score 50] [--output report.md]

依赖:
    pip install requests python-dotenv tabulate colorama
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import requests

try:
    from colorama import Fore, Style, init
    init(autoreset=True)
    GREEN  = Fore.GREEN
    YELLOW = Fore.YELLOW
    RED    = Fore.RED
    CYAN   = Fore.CYAN
    MAGENTA = Fore.MAGENTA
    BOLD   = Style.BRIGHT
    RESET  = Style.RESET_ALL
except ImportError:
    GREEN = YELLOW = RED = CYAN = MAGENTA = BOLD = RESET = ""

BINANCE_BASE = "https://api.binance.com"
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
DEXSCREENER_BASE = "https://api.dexscreener.com/latest"

# ─── 数据结构 ────────────────────────────────────────────────────────────────

@dataclass
class ProjectScore:
    binance_ecosystem:   float = 0.0  # 满分 25
    market_momentum:     float = 0.0  # 满分 20
    onchain_heat:        float = 0.0  # 满分 20
    community_quality:   float = 0.0  # 满分 15
    fundamentals:        float = 0.0  # 满分 10
    time_window_edge:    float = 0.0  # 满分 10

    @property
    def total(self) -> float:
        return (self.binance_ecosystem + self.market_momentum + self.onchain_heat +
                self.community_quality + self.fundamentals + self.time_window_edge)

    @property
    def grade(self) -> str:
        t = self.total
        if t >= 75:   return "🟢 重点关注"
        elif t >= 50: return "🟡 保持跟踪"
        else:         return "⚪ 暂不关注"

@dataclass
class AlphaProject:
    symbol: str
    name: str = ""
    source: str = "Unknown"          # Alpha / Launchpool / NewListing / DEX
    category: str = ""
    coingecko_id: str = ""

    # 市场数据
    price_usd: float = 0.0
    market_cap: float = 0.0
    volume_24h: float = 0.0
    price_change_24h: float = 0.0
    price_change_7d: float = 0.0
    volume_change_pct: float = 0.0

    # 链上数据
    bsc_liquidity: float = 0.0
    bsc_txns_1h: int = 0
    trending_score: float = 0.0

    # 社区数据
    twitter_followers: int = 0
    twitter_age_days: int = 0
    telegram_members: int = 0
    coingecko_score: float = 0.0

    # 时间窗口
    listing_date: Optional[datetime] = None
    days_since_listing: int = 999

    # 评分
    score: ProjectScore = field(default_factory=ProjectScore)
    highlights: list = field(default_factory=list)
    risks: list = field(default_factory=list)

# ─── 数据获取 ────────────────────────────────────────────────────────────────

def fetch_binance_ticker_24h(symbol: str) -> dict:
    """从币安获取 24h 行情数据"""
    try:
        symbol_upper = symbol.upper()
        for quote in ["USDT", "BNB", "BUSD"]:
            url = f"{BINANCE_BASE}/api/v3/ticker/24hr"
            resp = requests.get(url, params={"symbol": f"{symbol_upper}{quote}"}, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                if "lastPrice" in data:
                    return data
    except Exception:
        pass
    return {}

def fetch_binance_new_listings() -> list:
    """获取币安近期新上线代币（通过公告 API）"""
    print(f"{CYAN}🔍 扫描币安新币上线公告...{RESET}")
    url = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query"
    params = {
        "type": 1,
        "pageNo": 1,
        "pageSize": 10,
        "catalogId": "48"  # New Listings category
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; AlphaScout/1.0)",
        "Content-Type": "application/json"
    }
    projects = []
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        data = resp.json()
        articles = data.get("data", {}).get("articles", []) or []
        for article in articles[:5]:
            title = article.get("title", "")
            # 从标题中提取代币符号，如 "Binance Will List XYZ (XYZ)"
            import re
            match = re.search(r'\(([A-Z]{2,10})\)', title)
            if match:
                symbol = match.group(1)
                projects.append(AlphaProject(
                    symbol=symbol,
                    name=title[:50],
                    source="Binance NewListing"
                ))
    except Exception as e:
        print(f"{YELLOW}  ⚠ 公告 API 请求失败: {e}{RESET}")
    return projects

def fetch_coingecko_data(project: AlphaProject) -> AlphaProject:
    """从 CoinGecko 获取项目基本面数据"""
    try:
        # 先搜索 coingecko_id
        search_url = f"{COINGECKO_BASE}/search"
        resp = requests.get(search_url, params={"query": project.symbol}, timeout=10)
        if resp.status_code == 200:
            results = resp.json().get("coins", [])
            if results:
                project.coingecko_id = results[0]["id"]
                project.name = project.name or results[0]["name"]

        # 获取详细数据
        if project.coingecko_id:
            detail_url = f"{COINGECKO_BASE}/coins/{project.coingecko_id}"
            params = {
                "localization": "false",
                "tickers": "false",
                "market_data": "true",
                "community_data": "true",
                "developer_data": "false"
            }
            time.sleep(1.5)  # CoinGecko 限速
            resp = requests.get(detail_url, params=params, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                market = data.get("market_data", {})
                community = data.get("community_data", {})
                project.price_usd        = market.get("current_price", {}).get("usd", 0) or 0
                project.market_cap       = market.get("market_cap", {}).get("usd", 0) or 0
                project.volume_24h       = market.get("total_volume", {}).get("usd", 0) or 0
                project.price_change_24h = market.get("price_change_percentage_24h", 0) or 0
                project.price_change_7d  = market.get("price_change_percentage_7d", 0) or 0
                project.twitter_followers = community.get("twitter_followers", 0) or 0
                project.telegram_members  = community.get("telegram_channel_user_count", 0) or 0
                project.coingecko_score   = data.get("coingecko_score", 0) or 0
                # 上线时间
                genesis = data.get("genesis_date")
                if genesis:
                    listing_date = datetime.strptime(genesis, "%Y-%m-%d")
                    project.listing_date = listing_date
                    project.days_since_listing = (datetime.now() - listing_date).days
    except Exception as e:
        pass
    return project

def fetch_dexscreener_trending() -> list:
    """获取 BSC 链上近期最热代币"""
    print(f"{CYAN}🔍 扫描 BNB Chain 链上热度...{RESET}")
    url = f"{DEXSCREENER_BASE}/dex/search?q=bsc"
    trending = []
    try:
        # DEXScreener trending endpoint
        resp = requests.get(
            "https://api.dexscreener.com/token-boosts/top/v1",
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            for item in (data if isinstance(data, list) else [])[:20]:
                if item.get("chainId") == "bsc":
                    token_addr = item.get("tokenAddress", "")
                    # 获取代币信息
                    token_resp = requests.get(
                        f"{DEXSCREENER_BASE}/dex/tokens/{token_addr}",
                        timeout=8
                    )
                    if token_resp.status_code == 200:
                        pairs = token_resp.json().get("pairs", [])
                        if pairs:
                            base = pairs[0].get("baseToken", {})
                            symbol = base.get("symbol", "")
                            if symbol and len(symbol) <= 10:
                                p = AlphaProject(
                                    symbol=symbol,
                                    name=base.get("name", symbol),
                                    source="BSC Trending"
                                )
                                p.bsc_liquidity = float(
                                    pairs[0].get("liquidity", {}).get("usd", 0) or 0
                                )
                                p.trending_score = float(item.get("amount", 0))
                                trending.append(p)
    except Exception as e:
        print(f"{YELLOW}  ⚠ DEXScreener 请求失败: {e}{RESET}")
    return trending[:10]

# ─── 评分引擎 ────────────────────────────────────────────────────────────────

def score_project(project: AlphaProject, binance_ticker: dict) -> AlphaProject:
    score = ProjectScore()

    # ─ 1. 币安生态关联度 (25分) ─
    source_bonus = {
        "Binance Alpha": 25,
        "Binance Launchpad": 25,
        "Binance Launchpool": 22,
        "Binance NewListing": 20,
        "BSC Trending": 10,
        "Unknown": 5
    }
    score.binance_ecosystem = source_bonus.get(project.source, 5)
    if "Binance" in project.source:
        project.highlights.append(f"✨ 已获得币安官方背书（{project.source}）")

    # ─ 2. 市场动量 (20分) ─
    momentum = 0
    if binance_ticker:
        price_change = float(binance_ticker.get("priceChangePercent", 0))
        volume = float(binance_ticker.get("quoteVolume", 0))
        # 价格动量
        if price_change > 20:
            momentum += 10
            project.highlights.append(f"📈 24h 涨幅 +{price_change:.1f}%，强劲上涨")
        elif price_change > 5:
            momentum += 7
        elif price_change > 0:
            momentum += 4
        elif price_change > -10:
            momentum += 2
        else:
            project.risks.append(f"📉 24h 跌幅 {price_change:.1f}%，短期趋势偏弱")
        # 成交量
        if volume > 50_000_000:    momentum += 10
        elif volume > 10_000_000:  momentum += 7
        elif volume > 1_000_000:   momentum += 4
        elif volume > 100_000:     momentum += 2
        project.price_change_24h = price_change
        project.volume_24h = volume
    else:
        # 用 CoinGecko 数据作为备选
        ch = project.price_change_24h
        if ch > 15:    momentum += 10
        elif ch > 5:   momentum += 7
        elif ch > 0:   momentum += 4
        elif ch > -10: momentum += 2
        vol = project.volume_24h
        if vol > 50_000_000:   momentum += 10
        elif vol > 10_000_000: momentum += 7
        elif vol > 1_000_000:  momentum += 4
        elif vol > 100_000:    momentum += 2
    score.market_momentum = min(20, momentum)

    # ─ 3. 链上热度 (20分) ─
    onchain = 0
    liq = project.bsc_liquidity
    if liq > 1_000_000:    onchain += 10
    elif liq > 200_000:    onchain += 7
    elif liq > 50_000:     onchain += 4
    elif liq > 10_000:     onchain += 2
    else:
        if liq < 10_000 and liq > 0:
            project.risks.append(f"⚠️  BSC 流动性偏低 (${liq:,.0f})")
    if project.trending_score > 0:
        onchain += min(10, int(project.trending_score / 100))
        project.highlights.append(f"🔥 BSC DEX 热度榜上榜（推广分值 {project.trending_score:.0f}）")
    score.onchain_heat = min(20, onchain)

    # ─ 4. 社区真实性 (15分) ─
    community = 0
    followers = project.twitter_followers
    if followers > 200_000:   community += 8
    elif followers > 50_000:  community += 6
    elif followers > 10_000:  community += 4
    elif followers > 2_000:   community += 2
    else:
        if followers == 0:
            project.risks.append("⚠️  未找到 Twitter 社区数据")
    tg = project.telegram_members
    if tg > 50_000:    community += 5
    elif tg > 10_000:  community += 3
    elif tg > 1_000:   community += 1
    # CoinGecko 评分
    if project.coingecko_score > 50:   community += 2
    elif project.coingecko_score > 30: community += 1
    score.community_quality = min(15, community)

    # ─ 5. 基本面 (10分) ─
    fundamentals = 5  # 基础分
    if project.market_cap > 100_000_000:
        fundamentals += 3
        project.highlights.append(f"💰 市值 ${project.market_cap/1e6:.0f}M，规模可观")
    elif project.market_cap > 10_000_000:
        fundamentals += 2
    elif project.market_cap < 1_000_000 and project.market_cap > 0:
        fundamentals -= 2
        project.risks.append("⚠️  市值极小，流动性和价格操控风险较高")
    if project.coingecko_id:
        fundamentals += 2  # 有 CoinGecko 收录 = 基本透明度
    score.fundamentals = max(0, min(10, fundamentals))

    # ─ 6. 时间窗口优势 (10分) ─
    days = project.days_since_listing
    if days <= 7:
        score.time_window_edge = 10
        project.highlights.append(f"⏰ 上线仅 {days} 天，处于黄金窗口期")
    elif days <= 30:
        score.time_window_edge = 7
    elif days <= 90:
        score.time_window_edge = 4
    elif days <= 365:
        score.time_window_edge = 2
    else:
        score.time_window_edge = 1

    project.score = score
    return project

# ─── 报告生成 ────────────────────────────────────────────────────────────────

def generate_report(projects: list, min_score: float = 0) -> str:
    # 过滤和排序
    filtered = [p for p in projects if p.score.total >= min_score]
    filtered.sort(key=lambda x: x.score.total, reverse=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    top_picks = [p for p in filtered if p.score.total >= 75]

    lines = [
        f"",
        f"{'╔' + '═'*54 + '╗'}",
        f"║{'🦅 ALPHA SCOUT — 币安机会简报':^52}║",
        f"║{'  扫描时间: ' + now:^52}║",
        f"║{'  候选项目: ' + str(len(filtered)) + ' 个  |  重点关注: ' + str(len(top_picks)) + ' 个':^52}║",
        f"{'╠' + '═'*54 + '╣'}",
    ]

    if top_picks:
        lines.append(f"║{'  🏆 TOP PICKS（得分 ≥ 75）':^52}║")
        lines.append(f"{'╠' + '═'*54 + '╣'}")

        for i, p in enumerate(top_picks[:5], 1):
            s = p.score
            lines += [
                f"",
                f"  #{i}  {p.name} ({p.symbol})  {s.grade}",
                f"       综合得分  : {s.total:.1f}/100",
                f"       来源      : {p.source}",
                f"       价格      : ${p.price_usd:.6f}" if p.price_usd else "",
                f"       市值      : ${p.market_cap/1e6:.2f}M" if p.market_cap > 0 else "",
                f"       24h涨跌   : {p.price_change_24h:+.1f}%",
                f"       24h量     : ${p.volume_24h/1e6:.2f}M" if p.volume_24h > 0 else "",
            ]
            if p.highlights:
                lines.append(f"       ✨ 亮点:")
                for h in p.highlights[:3]:
                    lines.append(f"          {h}")
            if p.risks:
                lines.append(f"       ⚠️  风险:")
                for r in p.risks[:2]:
                    lines.append(f"          {r}")
            lines.append(f"       {'─'*46}")

    # 完整得分表
    lines += [
        f"",
        f"{'╠' + '═'*54 + '╣'}",
        f"║{'  📊 完整评分榜单':^52}║",
        f"{'╠' + '═'*54 + '╣'}",
        f"  {'排名':<4} {'代币':<12} {'总分':>6} {'币安':<6} {'动量':<6} {'链上':<6} {'社区':<6}",
        f"  {'─'*54}",
    ]

    for i, p in enumerate(filtered, 1):
        s = p.score
        grade_icon = "🟢" if s.total >= 75 else ("🟡" if s.total >= 50 else "⚪")
        lines.append(
            f"  {i:<4} {grade_icon} {p.symbol:<10} {s.total:>5.1f}  "
            f"{s.binance_ecosystem:>4.0f}  {s.market_momentum:>4.0f}  "
            f"{s.onchain_heat:>4.0f}  {s.community_quality:>4.0f}"
        )

    lines += [
        f"",
        f"{'╔' + '═'*54 + '╗'}",
        f"║{'🦞 Alpha Scout × OpenClaw × Binance':^54}║",
        f"║{'⚠️  本报告仅供参考，不构成投资建议':^52}║",
        f"{'╚' + '═'*54 + '╝'}",
        f""
    ]

    return "\n".join(l for l in lines)

def save_markdown_report(projects: list, filepath: str):
    """保存 Markdown 格式报告（适合 Telegram/Discord 分享）"""
    filtered = [p for p in projects if p.score.total >= 50]
    filtered.sort(key=lambda x: x.score.total, reverse=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    md = f"""# 🦅 Alpha Scout — 币安机会简报
**扫描时间**: {now} | **候选项目**: {len(filtered)} 个

---

## 🏆 Top Picks

"""
    for i, p in enumerate(filtered[:5], 1):
        s = p.score
        md += f"""### #{i} {p.name} ({p.symbol}) — {s.grade}

| 指标 | 数值 |
|------|------|
| 综合得分 | **{s.total:.1f}/100** |
| 来源 | {p.source} |
| 当前价格 | ${p.price_usd:.6f} |
| 市值 | ${p.market_cap/1e6:.2f}M |
| 24h涨跌 | {p.price_change_24h:+.1f}% |
| 24h交易量 | ${p.volume_24h/1e6:.2f}M |

**评分明细**: 币安关联 {s.binance_ecosystem:.0f} | 市场动量 {s.market_momentum:.0f} | 链上热度 {s.onchain_heat:.0f} | 社区 {s.community_quality:.0f}

"""
        if p.highlights:
            md += "**亮点**:\n"
            for h in p.highlights:
                md += f"- {h}\n"
        if p.risks:
            md += "\n**风险提示**:\n"
            for r in p.risks:
                md += f"- {r}\n"
        md += "\n---\n\n"

    md += "\n> 🦞 *Powered by Alpha Scout × OpenClaw × Binance | 本报告仅供参考，DYOR!*\n"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"{GREEN}✅ Markdown 报告已保存: {filepath}{RESET}")

# ─── 主程序 ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Alpha Scout — 币安机会评分引擎")
    parser.add_argument("--symbols", default="", help="指定代币符号列表，逗号分隔（空=自动扫描）")
    parser.add_argument("--top", type=int, default=10, help="显示前 N 个项目（默认10）")
    parser.add_argument("--min-score", type=float, default=0, help="最低得分过滤（默认0）")
    parser.add_argument("--output", default="", help="保存 Markdown 报告到文件")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = parser.parse_args()

    print(f"\n{BOLD}{CYAN}{'='*56}")
    print(f"  🦅 ALPHA SCOUT — 币安早鸟猎手")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*56}{RESET}\n")

    all_projects: list = []

    if args.symbols:
        # 用户指定代币
        for sym in args.symbols.split(","):
            sym = sym.strip().upper()
            if sym:
                all_projects.append(AlphaProject(symbol=sym, source="Manual"))
    else:
        # 自动扫描
        all_projects.extend(fetch_binance_new_listings())
        all_projects.extend(fetch_dexscreener_trending())

    if not all_projects:
        print(f"{YELLOW}⚠️  未找到候选项目，请检查网络连接或手动指定 --symbols{RESET}")
        sys.exit(1)

    # 去重（按 symbol）
    seen = set()
    unique_projects = []
    for p in all_projects:
        if p.symbol not in seen:
            seen.add(p.symbol)
            unique_projects.append(p)
    all_projects = unique_projects

    print(f"{CYAN}📊 开始分析 {len(all_projects)} 个候选项目...{RESET}\n")

    # 数据丰富 + 评分
    scored_projects = []
    for i, project in enumerate(all_projects):
        print(f"  [{i+1}/{len(all_projects)}] 分析 {project.symbol}...", end="", flush=True)
        try:
            # 获取 CoinGecko 数据
            project = fetch_coingecko_data(project)
            # 获取币安行情
            ticker = fetch_binance_ticker_24h(project.symbol)
            # 评分
            project = score_project(project, ticker)
            scored_projects.append(project)
            grade = project.score.grade
            print(f" {grade} ({project.score.total:.1f})")
        except Exception as e:
            print(f" {YELLOW}跳过 ({e}){RESET}")
        time.sleep(0.5)  # 避免过度请求

    # 输出
    if args.json:
        output = []
        for p in sorted(scored_projects, key=lambda x: x.score.total, reverse=True)[:args.top]:
            output.append({
                "symbol": p.symbol,
                "name": p.name,
                "source": p.source,
                "score": {
                    "total": round(p.score.total, 1),
                    "grade": p.score.grade,
                    "binance_ecosystem": p.score.binance_ecosystem,
                    "market_momentum": p.score.market_momentum,
                    "onchain_heat": p.score.onchain_heat,
                    "community_quality": p.score.community_quality,
                    "fundamentals": p.score.fundamentals,
                    "time_window_edge": p.score.time_window_edge,
                },
                "price_usd": p.price_usd,
                "market_cap": p.market_cap,
                "volume_24h": p.volume_24h,
                "price_change_24h": p.price_change_24h,
                "highlights": p.highlights,
                "risks": p.risks,
            })
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        report = generate_report(scored_projects, min_score=args.min_score)
        print(report)

    if args.output:
        save_markdown_report(scored_projects, args.output)


if __name__ == "__main__":
    main()
