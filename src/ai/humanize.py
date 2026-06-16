"""Convert grounded numeric facts into Chinese decision-language for prompts."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

JARGON_PATTERNS = [
    re.compile(r"\b[a-z]+_[a-z0-9_]+\b", re.IGNORECASE),
    re.compile(r"\b(position|score|flag|inflow|diffusion|trend|sector|state|facts)\s*=", re.IGNORECASE),
    re.compile(r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*"),
]

LABELS = {
    "sector": "行业",
    "state": "状态",
    "trend_days": "趋势持续",
    "pct_chg": "今日涨跌",
    "main_net_inflow": "今日主力资金",
    "inflow_5d": "5日主力资金",
    "inflow_10d": "10日主力资金",
    "cum_inflow_20d": "20日资金",
    "cum_inflow_60d": "60日资金",
    "diffusion": "上涨扩散",
    "turning_point": "拐点预警",
    "top_leaders": "龙头",
    "children": "细分板块",
    "stock_count": "成分股数",
    "position_in_box": "箱体位置",
    "midterm_trend": "中期趋势",
    "ignition_flag": "启动迹象",
    "ignition_score": "启动分",
    "historical_win_rate": "历史样本外胜率",
    "median_remaining_positive_days": "历史中位还能走",
    "valuation_pct": "估值分位",
    "hedge_score": "对冲度",
    "hedge_penalty": "对冲惩罚",
    "guarantee_ratio": "担保比",
    "score": "综合分",
    "reasons": "理由",
    "ranked_directions": "方向排序",
    "mainline": "当前主线",
    "mainline_trend_days": "主线持续",
    "mainline_inflow_10d": "主线10日资金",
    "candidates": "候选篮子",
    "hedge_pairs": "对冲对",
    "avoid_directions": "回避方向",
    "market_context": "市场佐证",
    "holdings": "当前持仓",
    "today_watch": "今日观察",
    "cycle": "周期结构",
    "ignition": "启动结构",
    "historical_analogy": "历史类比",
    "rotation_flow": "资金接力",
    "valuation_guard": "估值护栏",
    "leader_linkage": "龙头联动",
    "rotation_label": "接力状态",
    "label": "结论",
    "net_inflow": "净流入",
    "sample_count": "历史样本数",
    "level": "状态",
    "message": "提示",
}

MONEY_KEYS = {
    "main_net_inflow",
    "inflow_5d",
    "inflow_10d",
    "cum_inflow_20d",
    "cum_inflow_60d",
    "mainline_inflow_10d",
    "net_inflow",
    "fund_net_inflow",
    "net_buy_amount",
}


def humanize_facts(facts: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for key, value in facts.items():
        if value is None:
            continue
        if key == "ranked_directions":
            lines.extend(_ranked_directions(value))
        elif key == "hedge_pairs":
            lines.extend(_hedge_pairs(value))
        elif key == "holdings":
            lines.extend(_holdings(value))
        elif isinstance(value, dict):
            nested = "；".join(_inline_item(k, v) for k, v in value.items() if v is not None)
            if nested:
                lines.append(f"{_label(key)}：{nested}")
        elif isinstance(value, list):
            lines.append(f"{_label(key)}：{_join(value)}")
        else:
            lines.append(_inline_item(key, value))
    return [line for line in lines if line]


def assert_no_jargon(text: str) -> None:
    for pattern in JARGON_PATTERNS:
        if pattern.search(text):
            raise ValueError(f"AI 输出含变量名或等号: {pattern.pattern}")


def conclusion_first_instruction(limit: int = 200) -> str:
    return (
        f"先写一句“结论：”，这一句不超过{limit}字；后面再分点。"
        "禁止出现任何英文变量名、字段名、等号或代码写法，只能用中文短句和带单位数字。"
    )


def _ranked_directions(value: Any) -> list[str]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, dict)):
        return [f"方向排序：{value}"]
    lines = ["综合方向排序："]
    for index, item in enumerate(list(value)[:6], start=1):
        if not isinstance(item, dict):
            lines.append(f"{index}. {item}")
            continue
        sector = item.get("sector", "未知方向")
        score = _format_number(item.get("score"), digits=2)
        reasons = _join(item.get("reasons") or [])
        children = _join(item.get("children") or [], limit=5)
        suffix = f"，细分含{children}" if children else ""
        reason_text = f"，理由：{reasons}" if reasons else ""
        lines.append(f"{index}. {sector}，综合分{score}{suffix}{reason_text}")
    return lines


def _holdings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return [f"当前持仓：{value}"]
    items = []
    for item in value:
        if not isinstance(item, dict):
            items.append(str(item))
            continue
        name = item.get("name", "未知")
        sector = item.get("sector", "未知行业")
        state = item.get("state", "未知状态")
        items.append(f"{name}，{sector}，{state}")
    return [f"当前持仓：{'；'.join(items)}"] if items else []


def _hedge_pairs(value: Any) -> list[str]:
    if not isinstance(value, list):
        return [f"对冲对：{value}"]
    pairs = []
    for pair in value:
        if isinstance(pair, (list, tuple)) and len(pair) >= 2:
            pairs.append(f"{pair[0]}↔{pair[1]}")
        else:
            pairs.append(str(pair))
    return [f"对冲对：{'、'.join(pairs)}"] if pairs else []


def _inline_item(key: str, value: Any) -> str:
    return f"{_label(key)}：{_format_value(key, value)}"


def _label(key: str) -> str:
    return LABELS.get(str(key), "补充事实")


def _format_value(key: str, value: Any) -> str:
    if key in MONEY_KEYS:
        return _money_yi(value)
    if key in {"pct_chg"}:
        return f"{_num(value):+.2f}%"
    if key in {"diffusion", "historical_win_rate", "valuation_pct", "hedge_score", "hedge_penalty"}:
        return f"{_num(value):.0%}"
    if key == "position_in_box":
        number = _num(value)
        if number >= 0.9:
            return "顶部(已高位，追高需谨慎)"
        if number >= 0.65:
            return "偏高"
        if number <= 0.25:
            return "底部"
        return "中部"
    if key == "ignition_flag":
        return "已出现" if bool(value) else "未出现"
    if key == "turning_point":
        return "有" if bool(value) else "无"
    if key == "midterm_trend":
        number = _num(value)
        if number > 0:
            return "向上"
        if number < 0:
            return "向下"
        return "震荡"
    if key in {"trend_days", "mainline_trend_days"}:
        return f"{int(_num(value))}天"
    if key == "median_remaining_positive_days":
        return f"{_num(value):.0f}天"
    if key == "score" or key.endswith("_score"):
        return _format_number(value, digits=2)
    if key == "children":
        return _join(value)
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (list, tuple, set)):
        return _join(value)
    return str(value)


def _money_yi(value: Any) -> str:
    number = _num(value)
    yi = number / 100_000_000 if abs(number) >= 1_000_000 else number
    return f"{yi:+.1f}亿"


def _join(value: Any, limit: int = 6) -> str:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, dict)):
        return str(value)
    return "、".join(str(item) for item in list(value)[:limit])


def _format_number(value: Any, digits: int = 2) -> str:
    return f"{_num(value):.{digits}f}"


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
