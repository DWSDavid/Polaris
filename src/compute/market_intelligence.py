"""Market interpretation helpers for sector rotation workflows."""

from __future__ import annotations

import pandas as pd

from src.compute.fundamentals import sector_valuation_snapshot

GROWTH_SECTORS = {"信息技术", "医药卫生", "电信业务"}
OLD_ECONOMY_SECTORS = {"金融", "能源", "公用事业", "房地产", "主要消费"}


def sector_diagnostics(
    sector_panel: pd.DataFrame,
    stock_panel: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    panel = sector_panel.copy()
    if "sector" not in panel.columns:
        panel = panel.reset_index(names="sector")
    valuation = sector_valuation_snapshot(stock_panel).set_index("sector")
    for sector in panel["sector"].tolist():
        sector_row = panel[panel["sector"] == sector].iloc[0].to_dict()
        stocks = stock_panel[stock_panel["sector"] == sector].copy()
        valuation_row = (
            valuation.loc[sector].to_dict() if sector in valuation.index else {}
        )
        leaders = stocks.sort_values("rank").head(3)
        fund_flow = float(sector_row.get("fund_flow") or 0.0)
        diffusion = float(sector_row.get("diffusion") or 0.0)
        leader_contrib = float(sector_row.get("leader_contrib") or 0.0)
        trend20 = int(sector_row.get("trend20") or 0)
        consecutive_up = int(sector_row.get("consecutive_up") or 0)
        leader_line = _leader_line(leaders)
        row = {
            **sector_row,
            "sector": sector,
            "sector_group": _sector_group(sector),
            "fund_flow_yi": round(fund_flow / 100_000_000, 1),
            "money_direction": _money_direction(fund_flow),
            "trend_label": _trend_label(trend20, consecutive_up),
            "split_label": _split_label(diffusion, leader_contrib),
            "median_pe_ttm": valuation_row.get("median_pe_ttm"),
            "median_pb": valuation_row.get("median_pb"),
            "valuation_coverage": valuation_row.get("valuation_coverage", 0.0),
            "valuation_label": valuation_row.get("valuation_label", "估值缺数据"),
            "leader_line": leader_line,
            "brief": _brief(
                sector,
                sector_row.get("state", "-"),
                fund_flow,
                diffusion,
                trend20,
                consecutive_up,
                leader_contrib,
                leader_line,
            ),
        }
        rows.append(row)
    out = pd.DataFrame(rows)
    return out.sort_values(["strength", "fund_flow_yi"], ascending=False).reset_index(
        drop=True
    )


def hedge_alerts(diagnostics: pd.DataFrame) -> list[dict]:
    growth = diagnostics[
        (diagnostics["sector_group"] == "growth")
        & (diagnostics["fund_flow_yi"].abs() >= 0.5)
    ]
    old = diagnostics[
        (diagnostics["sector_group"] == "old_economy")
        & (diagnostics["fund_flow_yi"].abs() >= 0.5)
    ]
    alerts = []
    for _, growth_row in growth.iterrows():
        for _, old_row in old.iterrows():
            if _sign(growth_row["fund_flow_yi"]) == _sign(old_row["fund_flow_yi"]):
                continue
            alerts.append(
                {
                    "growth_sector": growth_row["sector"],
                    "old_economy_sector": old_row["sector"],
                    "offset_risk": "high",
                    "message": (
                        f"{growth_row['sector']} {growth_row['money_direction']}"
                        f" {growth_row['fund_flow_yi']:+.1f}亿，"
                        f"{old_row['sector']} {old_row['money_direction']}"
                        f" {old_row['fund_flow_yi']:+.1f}亿：成长/老经济方向相反，"
                        "组合收益容易互相抵消。"
                    ),
                }
            )
    return alerts


def build_ai_context(diagnostics: pd.DataFrame, alerts: list[dict]) -> str:
    lines = [
        "请基于以下真实字段做A股板块轮动分析，不要编造未给出的数据。",
        "重点回答：大趋势、资金流入流出、1-3周持续性、分化、龙头联动、对冲风险。",
    ]
    for _, row in diagnostics.head(8).iterrows():
        lines.append(
            f"- {row['sector']}: {row['state']}，资金{row['fund_flow_yi']:+.1f}亿，"
            f"扩散{row['diffusion']:.0%}，趋势{row['trend_label']}，"
            f"分化{row['split_label']}，龙头{row['leader_line']}。"
        )
    if alerts:
        lines.append("对冲提醒：")
        lines.extend(f"- {alert['message']}" for alert in alerts)
    return "\n".join(lines)


def _sector_group(sector: str) -> str:
    if sector in GROWTH_SECTORS:
        return "growth"
    if sector in OLD_ECONOMY_SECTORS:
        return "old_economy"
    return "cyclical"


def _leader_line(leaders: pd.DataFrame) -> str:
    if leaders.empty:
        return "-"
    names = leaders["name"].dropna().astype(str).head(3).tolist()
    return " / ".join(names) if names else "-"


def _money_direction(value: float) -> str:
    if value > 0:
        return "净流入"
    if value < 0:
        return "净流出"
    return "持平"


def _trend_label(trend20: int, consecutive_up: int) -> str:
    if trend20 > 0 and consecutive_up >= 3:
        return "1-3周上行"
    if trend20 > 0:
        return "中期向上但短线需确认"
    if trend20 < 0:
        return "中期下行"
    return "趋势未确认"


def _split_label(diffusion: float, leader_contrib: float) -> str:
    if diffusion < 0.35:
        return "明显分化"
    if leader_contrib >= 0.75:
        return "龙头过度集中"
    if diffusion >= 0.65:
        return "温和分化"
    return "扩散一般"


def _brief(
    sector: str,
    state: str,
    fund_flow: float,
    diffusion: float,
    trend20: int,
    consecutive_up: int,
    leader_contrib: float,
    leader_line: str,
) -> str:
    return (
        f"{sector}处在{state}，资金{_money_direction(fund_flow)}"
        f"{fund_flow / 100_000_000:+.1f}亿，扩散{diffusion:.0%}，"
        f"{_trend_label(trend20, consecutive_up)}；Top3贡献{leader_contrib:.0%}，"
        f"先看{leader_line}是否继续带动中军。"
    )


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0
