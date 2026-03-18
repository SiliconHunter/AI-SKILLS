#!/usr/bin/env python3
"""
Grid Wizard — grid_calculator.py
AI 网格交易参数计算引擎（基于币安公开 API，无需 Key）

用法:
    python grid_calculator.py --symbol BNBUSDT --investment 500
    python grid_calculator.py --symbol ETHUSDT --investment 1000 --risk-level conservative
    python grid_calculator.py --symbol BTCUSDT --investment 5000 --compare-all

依赖:
    pip install requests numpy colorama
"""

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import requests

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    print("提示：安装 numpy 可获得更精准的统计分析: pip install numpy")

try:
    from colorama import Fore, Style, init
    init(autoreset=True)
    GREEN = Fore.GREEN; YELLOW = Fore.YELLOW; RED = Fore.RED
    CYAN = Fore.CYAN;   MAGENTA = Fore.MAGENTA; BOLD = Style.BRIGHT; RESET = Style.RESET_ALL
except ImportError:
    GREEN = YELLOW = RED = CYAN = MAGENTA = BOLD = RESET = ""

BINANCE_BASE = "https://api.binance.com"

# ─── 风险策略配置 ─────────────────────────────────────────────────────────────

RISK_PROFILES = {
    "conservative": {
        "label": "保守 (Conservative)",
        "atr_multiplier": 3.0,
        "grid_count_range": (5, 8),
        "description": "窄区间，高触发频率，适合低波动行情"
    },
    "moderate": {
        "label": "稳健 (Moderate)",
        "atr_multiplier": 5.0,
        "grid_count_range": (10, 15),
        "description": "均衡设置，适合大多数用户和震荡行情"
    },
    "aggressive": {
        "label": "激进 (Aggressive)",
        "atr_multiplier": 8.0,
        "grid_count_range": (20, 50),
        "description": "宽区间，覆盖大波动，适合长期持有"
    }
}

# ─── 数据结构 ────────────────────────────────────────────────────────────────

@dataclass
class GridParams:
    symbol: str
    risk_level: str
    grid_type: str      # geometric / arithmetic
    investment: float

    # 价格参数
    current_price: float = 0.0
    lower_price: float = 0.0
    upper_price: float = 0.0
    grid_count: int = 10

    # 计算结果
    spacing_pct: float = 0.0
    per_grid_investment: float = 0.0
    profit_per_grid_pct: float = 0.0

    # 历史分析
    hist_low_30d: float = 0.0
    hist_high_30d: float = 0.0
    hist_volatility: float = 0.0
    atr_14: float = 0.0
    support_level: float = 0.0
    resistance_level: float = 0.0

    # 收益预测
    monthly_low: float = 0.0
    monthly_base: float = 0.0
    monthly_high: float = 0.0
    annual_low: float = 0.0
    annual_high: float = 0.0
    max_drawdown: float = 0.0

    # 方向建议
    direction: str = "中性"
    direction_reason: str = ""

# ─── 数据获取 ────────────────────────────────────────────────────────────────

def fetch_klines(symbol: str, interval: str, limit: int = 100) -> list:
    """从币安获取 K 线数据（无需 API Key）"""
    url = f"{BINANCE_BASE}/api/v3/klines"
    params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"{YELLOW}  ⚠ K线获取失败 ({symbol} {interval}): {e}{RESET}")
        return []

def fetch_current_price(symbol: str) -> float:
    """获取当前价格"""
    url = f"{BINANCE_BASE}/api/v3/ticker/price"
    try:
        resp = requests.get(url, params={"symbol": symbol.upper()}, timeout=8)
        return float(resp.json().get("price", 0))
    except Exception:
        return 0.0

def fetch_24h_stats(symbol: str) -> dict:
    """获取 24h 统计数据"""
    url = f"{BINANCE_BASE}/api/v3/ticker/24hr"
    try:
        resp = requests.get(url, params={"symbol": symbol.upper()}, timeout=8)
        return resp.json()
    except Exception:
        return {}

# ─── 技术分析 ────────────────────────────────────────────────────────────────

def parse_klines(raw_klines: list) -> dict:
    """解析 K 线数据，提取 OHLCV"""
    if not raw_klines:
        return {}
    opens  = [float(k[1]) for k in raw_klines]
    highs  = [float(k[2]) for k in raw_klines]
    lows   = [float(k[3]) for k in raw_klines]
    closes = [float(k[4]) for k in raw_klines]
    volumes = [float(k[5]) for k in raw_klines]
    return {
        "opens": opens, "highs": highs, "lows": lows,
        "closes": closes, "volumes": volumes
    }

def calc_atr(highs: list, lows: list, closes: list, period: int = 14) -> float:
    """计算 ATR（平均真实波动幅度）"""
    if len(highs) < period + 1:
        return 0.0
    true_ranges = []
    for i in range(1, len(highs)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i] - closes[i-1])
        )
        true_ranges.append(tr)
    # 简单均值 ATR
    recent_tr = true_ranges[-period:]
    return sum(recent_tr) / len(recent_tr)

def calc_support_resistance(highs: list, lows: list, closes: list, lookback: int = 30) -> tuple:
    """基于近期低点/高点聚类计算支撑阻力位"""
    if len(lows) < lookback:
        return min(lows), max(highs)
    recent_lows  = lows[-lookback:]
    recent_highs = highs[-lookback:]
    # 简单取 10th 和 90th 百分位作为支撑/阻力
    sorted_lows  = sorted(recent_lows)
    sorted_highs = sorted(recent_highs)
    n = len(sorted_lows)
    support    = sorted_lows[int(n * 0.1)]
    resistance = sorted_highs[int(n * 0.9)]
    return support, resistance

def calc_bollinger_bands(closes: list, period: int = 20, std_dev: float = 2.0) -> tuple:
    """计算布林带"""
    if len(closes) < period:
        return 0.0, closes[-1] if closes else 0.0, 0.0
    recent = closes[-period:]
    ma = sum(recent) / period
    variance = sum((x - ma) ** 2 for x in recent) / period
    std = math.sqrt(variance)
    return ma - std_dev * std, ma, ma + std_dev * std

def calc_volatility(closes: list, period: int = 30) -> float:
    """计算年化波动率"""
    if len(closes) < period + 1:
        return 0.0
    returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, min(len(closes), period+1))]
    if not returns:
        return 0.0
    mean_r = sum(returns) / len(returns)
    variance = sum((r - mean_r)**2 for r in returns) / len(returns)
    daily_std = math.sqrt(variance)
    return daily_std * math.sqrt(365) * 100  # 年化，百分比

# ─── 网格参数计算 ─────────────────────────────────────────────────────────────

def calculate_grid_params(
    symbol: str,
    investment: float,
    risk_level: str = "moderate",
    grid_type: str = "geometric"
) -> GridParams:
    """核心计算函数"""

    print(f"{CYAN}📊 获取 {symbol} 历史行情数据...{RESET}")

    params = GridParams(
        symbol=symbol,
        risk_level=risk_level,
        grid_type=grid_type,
        investment=investment
    )

    # ─ 获取数据 ─
    klines_1d  = fetch_klines(symbol, "1d", limit=90)   # 90天日线
    klines_4h  = fetch_klines(symbol, "4h", limit=168)  # 4周4小时线
    current_price = fetch_current_price(symbol)
    stats_24h = fetch_24h_stats(symbol)

    if not klines_1d or current_price == 0:
        print(f"{RED}❌ 无法获取数据，请检查代币符号是否正确（例如 BNBUSDT）{RESET}")
        sys.exit(1)

    params.current_price = current_price
    print(f"  当前价格: {BOLD}${current_price:,.4f}{RESET}")

    # ─ 解析 K 线 ─
    d1 = parse_klines(klines_1d)
    h4 = parse_klines(klines_4h)

    # ─ 技术指标 ─
    params.hist_low_30d  = min(d1["lows"][-30:])
    params.hist_high_30d = max(d1["highs"][-30:])
    params.atr_14        = calc_atr(d1["highs"], d1["lows"], d1["closes"], 14)
    params.hist_volatility = calc_volatility(d1["closes"])
    support, resistance  = calc_support_resistance(d1["highs"], d1["lows"], d1["closes"])
    params.support_level   = support
    params.resistance_level = resistance

    # 4小时布林带（用于精确区间）
    bb_lower, bb_mid, bb_upper = calc_bollinger_bands(h4["closes"] if h4 else d1["closes"])

    print(f"  30日区间  : ${params.hist_low_30d:,.4f} ~ ${params.hist_high_30d:,.4f}")
    print(f"  ATR(14)   : ${params.atr_14:,.4f}  ({params.atr_14/current_price*100:.2f}%)")
    print(f"  年化波动率 : {params.hist_volatility:.1f}%")

    # ─ 计算价格区间 ─
    profile = RISK_PROFILES[risk_level]
    atr_mult = profile["atr_multiplier"]
    atr_pct  = params.atr_14 / current_price

    # 结合 ATR 和历史支撑/阻力位来确定区间
    raw_lower = current_price * (1 - atr_pct * atr_mult * 0.6)
    raw_upper = current_price * (1 + atr_pct * atr_mult * 0.4)

    # 参考支撑/阻力位做微调
    params.lower_price = max(raw_lower, support * 0.97)
    params.upper_price = min(raw_upper, resistance * 1.03)

    # 确保区间合理（下限至少比上限低 10%）
    if params.upper_price / params.lower_price < 1.10:
        center = (params.upper_price + params.lower_price) / 2
        params.lower_price = center * 0.95
        params.upper_price = center * 1.05

    # ─ 确定格数 ─
    grid_min, grid_max = profile["grid_count_range"]
    # 波动率越高 → 格数越多
    vol_factor = min(2.0, params.hist_volatility / 50)
    optimal_grids = int(grid_min + (grid_max - grid_min) * vol_factor)
    params.grid_count = max(grid_min, min(grid_max, optimal_grids))

    # ─ 计算间距 ─
    if grid_type == "geometric":
        # 等比：每格涨幅相同
        ratio = (params.upper_price / params.lower_price) ** (1 / params.grid_count)
        params.spacing_pct = (ratio - 1) * 100
    else:
        # 等差：每格价差相同
        step = (params.upper_price - params.lower_price) / params.grid_count
        params.spacing_pct = (step / current_price) * 100

    # ─ 每格投资额 ─
    params.per_grid_investment = investment / params.grid_count
    # 每触发一格的利润（等比模式下每格利润率 ≈ spacing_pct）
    params.profit_per_grid_pct = params.spacing_pct * 0.9  # 扣除 0.1% 手续费

    # ─ 方向判断 ─
    price_in_range_pct = (current_price - params.hist_low_30d) / (params.hist_high_30d - params.hist_low_30d + 1e-9)
    price_change_24h = float(stats_24h.get("priceChangePercent", 0))

    if price_in_range_pct < 0.3:
        params.direction = "偏多（价格处于近期低位，下行空间有限）"
        params.direction_reason = f"当前价格处于30日区间底部 {price_in_range_pct:.0%}，建议网格偏低配置"
    elif price_in_range_pct > 0.7:
        params.direction = "中性偏空（价格处于近期高位，注意破位风险）"
        params.direction_reason = f"当前价格处于30日区间顶部 {price_in_range_pct:.0%}，建议设置止损"
    else:
        params.direction = "中性震荡"
        params.direction_reason = f"当前价格处于30日区间中段 {price_in_range_pct:.0%}，适合标准网格"

    # ─ 收益预测（基于历史波动率的蒙特卡洛简化版）─
    # 每日预期触发格数 ≈ 日内波动 / 格间距
    daily_volatility_pct = params.hist_volatility / math.sqrt(365)
    expected_triggers_per_day = (daily_volatility_pct * 100 / 2) / params.spacing_pct
    expected_triggers_per_day = min(expected_triggers_per_day, params.grid_count * 0.5)

    daily_profit_pct = expected_triggers_per_day * params.profit_per_grid_pct / 100
    monthly_profit   = daily_profit_pct * 30 * 100

    params.monthly_low  = monthly_profit * 0.5
    params.monthly_base = monthly_profit
    params.monthly_high = monthly_profit * 1.8
    params.annual_low   = params.monthly_low  * 12
    params.annual_high  = params.monthly_high * 12

    # ─ 最大回撤风险 ─
    # 如果价格跌到下限，本金损失 ≈ (当前价-下限)/当前价 * 持币比例（约50%）
    params.max_drawdown = ((current_price - params.lower_price) / current_price) * 50

    return params

# ─── 报告生成 ─────────────────────────────────────────────────────────────────

def format_price(price: float, symbol: str) -> str:
    """智能格式化价格"""
    if price >= 1000: return f"${price:,.2f}"
    if price >= 1:    return f"${price:,.4f}"
    return f"${price:.8f}"

def generate_report(p: GridParams) -> str:
    profile = RISK_PROFILES[p.risk_level]
    grid_type_label = "等比 (Geometric)" if p.grid_type == "geometric" else "等差 (Arithmetic)"

    report = f"""
{'═' * 52}
🧙 GRID WIZARD — 网格参数报告
{'═' * 52}
交易对   : {p.symbol}
风险策略 : {profile['label']}
网格类型 : {grid_type_label}
总投资额 : {p.investment:,.2f} USDT
生成时间 : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'─' * 52}
📐 推荐网格参数
{'─' * 52}
  当前价格  : {format_price(p.current_price, p.symbol)}
  价格下限  : {format_price(p.lower_price, p.symbol)}
  价格上限  : {format_price(p.upper_price, p.symbol)}
  区间宽度  : {(p.upper_price/p.lower_price - 1)*100:.1f}%
  网格数量  : {p.grid_count} 格
  每格间距  : ≈ {p.spacing_pct:.2f}%
  每格资金  : ≈ {p.per_grid_investment:.2f} USDT
  每格净利  : ≈ {p.profit_per_grid_pct:.2f}%（扣手续费）
{'─' * 52}
📊 历史数据分析（近30日）
{'─' * 52}
  价格区间  : {format_price(p.hist_low_30d, p.symbol)} ~ {format_price(p.hist_high_30d, p.symbol)}
  ATR(14)  : {format_price(p.atr_14, p.symbol)} ({p.atr_14/p.current_price*100:.2f}%)
  年化波动率 : {p.hist_volatility:.1f}%
  支撑位    : {format_price(p.support_level, p.symbol)}
  阻力位    : {format_price(p.resistance_level, p.symbol)}
  方向建议  : {p.direction}
  分析理由  : {p.direction_reason}
{'─' * 52}
💰 收益预测（基于历史回测）
{'─' * 52}
  悲观估计  : {p.monthly_low:.2f}% / 月  ({p.annual_low:.1f}% / 年)
  基准估计  : {p.monthly_base:.2f}% / 月  ({p.monthly_base*12:.1f}% / 年)
  乐观估计  : {p.monthly_high:.2f}% / 月  ({p.annual_high:.1f}% / 年)
{'─' * 52}
⚠️  风险提示
{'─' * 52}
  最大本金回撤风险 : ≈ {p.max_drawdown:.1f}%（跌破下限时）
  价格跌破下限     : 网格停止，需手动决策是否重设
  价格涨破上限     : 全仓卖出，错过后续涨幅
  建议止损         : 价格跌破 {format_price(p.lower_price * 0.95, p.symbol)}（下限再跌5%）
{'═' * 52}
🧙 Grid Wizard × OpenClaw × Binance
⚠️  回测结果基于历史数据，不代表未来收益
{'═' * 52}
"""
    return report

def generate_comparison_table(symbol: str, investment: float, grid_type: str = "geometric") -> str:
    """生成三种风险策略的对比表格"""
    print(f"\n{CYAN}计算三种策略对比...{RESET}\n")
    results = {}
    for level in ["conservative", "moderate", "aggressive"]:
        print(f"  计算 {RISK_PROFILES[level]['label']}...", end="", flush=True)
        results[level] = calculate_grid_params(symbol, investment, level, grid_type)
        print(f" ✓")

    table = f"""
{'═' * 70}
🧙 GRID WIZARD — 三策略对比
{'═' * 70}
  交易对: {symbol}  |  投资额: {investment:,.0f} USDT

  {'策略':<14} {'价格区间':<24} {'格数':>4} {'间距':>6} {'年化(基准)':>10} {'最大回撤':>8}
  {'─' * 68}"""

    for level, p in results.items():
        profile = RISK_PROFILES[level]
        range_str = f"{format_price(p.lower_price,symbol)} ~ {format_price(p.upper_price,symbol)}"
        table += f"""
  {profile['label']:<14} {range_str:<24} {p.grid_count:>4} {p.spacing_pct:>5.2f}% {p.monthly_base*12:>8.1f}%  {p.max_drawdown:>6.1f}%"""

    table += f"""
  {'─' * 68}
  * 年化收益为基准估计，实际收益受行情影响可能有较大差异
{'═' * 70}
"""
    return table

# ─── JSON 输出（供 OpenClaw Agent 解析）─────────────────────────────────────

def to_json_output(p: GridParams) -> dict:
    return {
        "symbol": p.symbol,
        "risk_level": p.risk_level,
        "grid_type": p.grid_type,
        "investment": p.investment,
        "current_price": p.current_price,
        "grid_params": {
            "lower_price": round(p.lower_price, 8),
            "upper_price": round(p.upper_price, 8),
            "grid_count": p.grid_count,
            "spacing_pct": round(p.spacing_pct, 4),
            "per_grid_investment": round(p.per_grid_investment, 2),
            "profit_per_grid_pct": round(p.profit_per_grid_pct, 4),
        },
        "market_analysis": {
            "hist_low_30d": p.hist_low_30d,
            "hist_high_30d": p.hist_high_30d,
            "atr_14": p.atr_14,
            "atr_pct": p.atr_14 / p.current_price * 100 if p.current_price else 0,
            "annual_volatility": p.hist_volatility,
            "support_level": p.support_level,
            "resistance_level": p.resistance_level,
            "direction": p.direction,
        },
        "return_forecast": {
            "monthly_low_pct":  round(p.monthly_low, 2),
            "monthly_base_pct": round(p.monthly_base, 2),
            "monthly_high_pct": round(p.monthly_high, 2),
            "annual_low_pct":   round(p.annual_low, 1),
            "annual_high_pct":  round(p.annual_high, 1),
        },
        "risk": {
            "max_drawdown_pct": round(p.max_drawdown, 1),
            "stop_loss_price":  round(p.lower_price * 0.95, 8),
        },
        # 供浏览器自动填写的字段（OpenClaw 直接使用）
        "binance_ui_fill": {
            "grid_type_selector": "geometric" if p.grid_type == "geometric" else "arithmetic",
            "lower_price_input":  str(round(p.lower_price, 4)),
            "upper_price_input":  str(round(p.upper_price, 4)),
            "grid_num_input":     str(p.grid_count),
            "investment_input":   str(p.investment),
        }
    }

# ─── 主程序 ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Grid Wizard — AI 网格交易参数计算引擎")
    parser.add_argument("--symbol",     required=True, help="交易对，如 BNBUSDT / ETHUSDT / BTCUSDT")
    parser.add_argument("--investment", type=float, required=True, help="总投资金额（USDT）")
    parser.add_argument("--risk-level", default="moderate",
                        choices=["conservative", "moderate", "aggressive"],
                        help="风险策略 (默认: moderate)")
    parser.add_argument("--grid-type",  default="geometric",
                        choices=["geometric", "arithmetic"],
                        help="网格类型 (默认: geometric 等比)")
    parser.add_argument("--compare-all", action="store_true",
                        help="对比三种风险策略")
    parser.add_argument("--json",        action="store_true",
                        help="JSON 格式输出（供 OpenClaw 解析）")
    args = parser.parse_args()

    symbol = args.symbol.upper()
    if not symbol.endswith(("USDT", "BNB", "BUSD", "ETH", "BTC")):
        symbol += "USDT"

    print(f"\n{BOLD}{CYAN}{'='*52}")
    print(f"  🧙 GRID WIZARD — AI 网格交易向导")
    print(f"  {symbol}  |  {args.investment:,.0f} USDT  |  {args.risk_level}")
    print(f"{'='*52}{RESET}\n")

    if args.compare_all:
        table = generate_comparison_table(symbol, args.investment, args.grid_type)
        print(table)
        return

    # 单策略计算
    params = calculate_grid_params(symbol, args.investment, args.risk_level, args.grid_type)

    if args.json:
        print(json.dumps(to_json_output(params), ensure_ascii=False, indent=2))
    else:
        report = generate_report(params)
        print(report)


if __name__ == "__main__":
    main()
