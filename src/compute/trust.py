"""Trust labels for displayed market conclusions."""

from __future__ import annotations

from datetime import datetime
from typing import Any

TRUST_DISCLAIMER = "以上为数据归纳，非投资建议；样本外有效性见校准报告。"


def trust_badge(facts: dict[str, Any], as_of: str | None = None) -> dict[str, Any]:
    data_time = as_of or datetime.now().strftime("%Y-%m-%d %H:%M")
    stock_count = int(_num(facts.get("stock_count")))
    sample_label = "样本少，谨慎" if stock_count and stock_count < 20 else "样本充足"
    if stock_count <= 0:
        sample_label = "样本数未知"
    oos_rate = _oos_rate(facts)
    oos_label = "暂无样本外校准" if oos_rate is None else f"样本外胜率 {oos_rate:.0%}"
    summary = f"数据截至 {data_time} · 成分股 {stock_count or '-'} · {sample_label} · {oos_label}"
    return {
        "data_time": data_time,
        "stock_count": stock_count,
        "sample_label": sample_label,
        "oos_win_rate": oos_rate,
        "oos_label": oos_label,
        "summary": summary,
    }


def with_disclaimer(text: str) -> str:
    clean = str(text or "").strip()
    if TRUST_DISCLAIMER in clean:
        return clean
    return f"{clean}\n\n{TRUST_DISCLAIMER}" if clean else TRUST_DISCLAIMER


def _oos_rate(facts: dict[str, Any]) -> float | None:
    if facts.get("historical_win_rate") is not None:
        return _num(facts.get("historical_win_rate"))
    calibration = facts.get("calibration")
    if isinstance(calibration, dict):
        out_sample = calibration.get("out_sample")
        if isinstance(out_sample, dict) and out_sample.get("hit_rate") is not None:
            return _num(out_sample.get("hit_rate"))
    return None


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
